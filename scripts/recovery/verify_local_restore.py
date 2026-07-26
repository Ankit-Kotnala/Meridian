"""Destructive-safe local PostgreSQL/MinIO backup and isolated restore proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

EXPECTED_MIGRATION_HEAD = "20260727_0019"
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_RESTORE_DATABASE_PREFIX = "careeros_restore_verify_"
_RESTORE_BUCKET_PREFIX = "careeros-restore-verify-"


class RecoveryError(RuntimeError):
    """A safe local recovery verification failure."""


def verify_local_restore(
    *,
    repository_root: Path,
    postgres_user: str,
    postgres_database: str,
    source_bucket: str,
    output: Path | None,
) -> dict[str, object]:
    root = repository_root.resolve(strict=True)
    _require_repository(root)
    _identifier(postgres_user, "PostgreSQL user")
    _identifier(postgres_database, "PostgreSQL database")
    _bucket(source_bucket, "source bucket")

    recovery_root = (root / ".data" / "recovery").resolve()
    recovery_root.mkdir(parents=True, exist_ok=True)
    if root not in recovery_root.parents:
        raise RecoveryError("recovery workspace escaped the repository")

    suffix = secrets.token_hex(6)
    restore_database = f"{_RESTORE_DATABASE_PREFIX}{suffix}"
    restore_bucket = f"{_RESTORE_BUCKET_PREFIX}{suffix}"
    _restore_database(restore_database)
    _restore_bucket(restore_bucket)
    started = time.perf_counter()
    database_created = False
    bucket_created = False

    with tempfile.TemporaryDirectory(prefix="run-", dir=recovery_root) as temporary:
        workspace = Path(temporary).resolve(strict=True)
        if recovery_root not in workspace.parents:
            raise RecoveryError(
                "temporary recovery workspace is outside the recovery root"
            )
        relative_workspace = workspace.relative_to(root).as_posix()
        dump_path = workspace / "postgres.dump"
        source_objects = workspace / "objects"
        restored_objects = workspace / "restored-objects"
        source_objects.mkdir()
        restored_objects.mkdir()
        try:
            _compose(root, "config", "--quiet")
            _postgres_dump(
                root,
                postgres_user,
                postgres_database,
                dump_path,
            )
            dump_digest = _sha256(dump_path)
            source_counts = _table_counts(root, postgres_user, postgres_database)
            source_head = _migration_head(root, postgres_user, postgres_database)
            if source_head != EXPECTED_MIGRATION_HEAD:
                raise RecoveryError(
                    "source database is not at the release migration head"
                )

            _object_backup(
                root,
                relative_workspace,
                source_bucket=source_bucket,
            )
            source_manifest = _object_manifest(source_objects)

            _postgres(
                root,
                "createdb",
                "-U",
                postgres_user,
                restore_database,
            )
            database_created = True
            _postgres_restore(
                root,
                postgres_user,
                restore_database,
                dump_path,
            )
            restored_counts = _table_counts(root, postgres_user, restore_database)
            restored_head = _migration_head(root, postgres_user, restore_database)
            if restored_head != EXPECTED_MIGRATION_HEAD:
                raise RecoveryError(
                    "restored database is not at the release migration head"
                )
            if restored_counts != source_counts:
                raise RecoveryError(
                    "restored PostgreSQL table counts differ from the source"
                )

            bucket_created = True
            _object_restore(
                root,
                relative_workspace,
                restore_bucket=restore_bucket,
            )
            restored_manifest = _object_manifest(restored_objects)
            if restored_manifest != source_manifest:
                raise RecoveryError(
                    "restored object bytes differ from the source snapshot"
                )

            elapsed = time.perf_counter() - started
            report: dict[str, object] = {
                "schemaVersion": 1,
                "generatedAt": datetime.now(UTC).isoformat(),
                "migrationHead": restored_head,
                "postgres": {
                    "archiveSha256": dump_digest,
                    "tableCount": len(restored_counts),
                    "rowCount": sum(restored_counts.values()),
                },
                "objectStorage": {
                    "objectCount": len(restored_manifest),
                    "totalBytes": sum(
                        int(item["sizeBytes"]) for item in restored_manifest.values()
                    ),
                    "contentManifestSha256": _manifest_digest(restored_manifest),
                },
                "elapsedSeconds": round(elapsed, 3),
                "isolatedRestore": True,
                "temporaryTargetsRemoved": True,
                "passed": True,
            }
        finally:
            if database_created:
                _drop_restore_database(root, postgres_user, restore_database)
            if bucket_created:
                _drop_restore_bucket(root, restore_bucket)

    if output is not None:
        target = output.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    return report


def _require_repository(root: Path) -> None:
    if not (root / "compose.yaml").is_file() or not (root / ".git").exists():
        raise RecoveryError("repository root is invalid")


def _identifier(value: str, field: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise RecoveryError(f"{field} is invalid")
    return value


def _bucket(value: str, field: str) -> str:
    if not _BUCKET.fullmatch(value) or ".." in value:
        raise RecoveryError(f"{field} is invalid")
    return value


def _restore_database(value: str) -> str:
    if not value.startswith(_RESTORE_DATABASE_PREFIX):
        raise RecoveryError("restore database prefix is invalid")
    return _identifier(value, "restore database")


def _restore_bucket(value: str) -> str:
    if not value.startswith(_RESTORE_BUCKET_PREFIX):
        raise RecoveryError("restore bucket prefix is invalid")
    return _bucket(value, "restore bucket")


def _run(
    root: Path,
    command: list[str],
    *,
    stdout: int | None = subprocess.PIPE,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            command,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise RecoveryError(f"required command is unavailable: {command[0]}") from exc
    if result.returncode != 0:
        safe_error = result.stderr.decode("utf-8", errors="replace")[-2_000:]
        raise RecoveryError(
            f"recovery command failed ({command[0]} exit {result.returncode}): {safe_error}"
        )
    return result


def _compose(root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return _run(root, ["docker", "compose", *arguments])


def _postgres(root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return _compose(root, "exec", "-T", "postgres", *arguments)


def _postgres_dump(
    root: Path,
    user: str,
    database: str,
    output: Path,
) -> None:
    with output.open("wb") as destination:
        _run(
            root,
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "-U",
                user,
                "-d",
                database,
            ],
            stdout=destination.fileno(),
        )
    if output.stat().st_size < 1_024:
        raise RecoveryError("PostgreSQL backup archive is unexpectedly small")


def _postgres_restore(
    root: Path,
    user: str,
    database: str,
    archive: Path,
) -> None:
    with archive.open("rb") as source:
        command = [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "pg_restore",
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            "-U",
            user,
            "-d",
            database,
        ]
        result = subprocess.run(
            command,
            cwd=root,
            stdin=source,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    if result.returncode != 0:
        safe_error = result.stderr.decode("utf-8", errors="replace")[-2_000:]
        raise RecoveryError(f"PostgreSQL restore failed: {safe_error}")


def _psql(root: Path, user: str, database: str, sql: str) -> str:
    result = _postgres(
        root,
        "psql",
        "-X",
        "--no-psqlrc",
        "--set",
        "ON_ERROR_STOP=1",
        "--tuples-only",
        "--no-align",
        "-U",
        user,
        "-d",
        database,
        "-c",
        sql,
    )
    return result.stdout.decode("utf-8", errors="strict").strip()


def _migration_head(root: Path, user: str, database: str) -> str:
    return _psql(root, user, database, "SELECT version_num FROM alembic_version;")


def _table_counts(root: Path, user: str, database: str) -> dict[str, int]:
    tables = _psql(
        root,
        user,
        database,
        (
            "SELECT tablename FROM pg_catalog.pg_tables "
            "WHERE schemaname = 'public' ORDER BY tablename;"
        ),
    ).splitlines()
    result: dict[str, int] = {}
    for table in tables:
        _identifier(table, "PostgreSQL table")
        raw_count = _psql(
            root,
            user,
            database,
            f'SELECT count(*) FROM "{table}";',
        )
        try:
            result[table] = int(raw_count)
        except ValueError as exc:
            raise RecoveryError("PostgreSQL table count is invalid") from exc
    if "alembic_version" not in result:
        raise RecoveryError("PostgreSQL schema does not contain alembic_version")
    return result


def _object_backup(
    root: Path,
    relative_workspace: str,
    *,
    source_bucket: str,
) -> None:
    script = (
        "set -eu; "
        'mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" '
        ">/dev/null; "
        'mc stat "local/$SOURCE_BUCKET" >/dev/null; '
        'mc mirror --overwrite "local/$SOURCE_BUCKET" /backup/objects >/dev/null'
    )
    _compose(
        root,
        "run",
        "--rm",
        "-T",
        "--no-deps",
        "--volume",
        f"{relative_workspace}:/backup",
        "--env",
        f"SOURCE_BUCKET={source_bucket}",
        "--entrypoint",
        "/bin/sh",
        "minio-init",
        "-c",
        script,
    )


def _object_restore(
    root: Path,
    relative_workspace: str,
    *,
    restore_bucket: str,
) -> None:
    script = (
        "set -eu; "
        'mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" '
        ">/dev/null; "
        'mc mb "local/$RESTORE_BUCKET" >/dev/null; '
        'mc mirror --overwrite /backup/objects "local/$RESTORE_BUCKET" >/dev/null; '
        'mc mirror --overwrite "local/$RESTORE_BUCKET" /backup/restored-objects >/dev/null'
    )
    _compose(
        root,
        "run",
        "--rm",
        "-T",
        "--no-deps",
        "--volume",
        f"{relative_workspace}:/backup",
        "--env",
        f"RESTORE_BUCKET={restore_bucket}",
        "--entrypoint",
        "/bin/sh",
        "minio-init",
        "-c",
        script,
    )


def _drop_restore_database(root: Path, user: str, restore_database: str) -> None:
    _restore_database(restore_database)
    _postgres(
        root,
        "dropdb",
        "--if-exists",
        "--force",
        "-U",
        user,
        restore_database,
    )


def _drop_restore_bucket(root: Path, restore_bucket: str) -> None:
    _restore_bucket(restore_bucket)
    script = (
        "set -eu; "
        'mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" '
        ">/dev/null; "
        'if mc stat "local/$RESTORE_BUCKET" >/dev/null 2>&1; then '
        'mc rb --force "local/$RESTORE_BUCKET" >/dev/null; fi'
    )
    _compose(
        root,
        "run",
        "--rm",
        "-T",
        "--no-deps",
        "--env",
        f"RESTORE_BUCKET={restore_bucket}",
        "--entrypoint",
        "/bin/sh",
        "minio-init",
        "-c",
        script,
    )


def _object_manifest(root: Path) -> dict[str, dict[str, object]]:
    manifest: dict[str, dict[str, object]] = {}
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        resolved = path.resolve(strict=True)
        if root.resolve(strict=True) not in resolved.parents:
            raise RecoveryError("object snapshot contains an unsafe path")
        relative = resolved.relative_to(root.resolve(strict=True)).as_posix()
        manifest[relative] = {
            "sizeBytes": resolved.stat().st_size,
            "sha256": _sha256(resolved),
        }
    return manifest


def _manifest_digest(manifest: dict[str, dict[str, object]]) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _self_test() -> None:
    _restore_database("careeros_restore_verify_0123456789ab")
    _restore_bucket("careeros-restore-verify-0123456789ab")
    for unsafe in ("careeros", "postgres", "careeros_restore_verify_bad-name"):
        try:
            _restore_database(unsafe)
        except RecoveryError:
            pass
        else:
            raise AssertionError("unsafe restore database was accepted")
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "nested").mkdir()
        (root / "nested" / "object.bin").write_bytes(b"fictional object")
        manifest = _object_manifest(root)
        if len(manifest) != 1 or len(_manifest_digest(manifest)) != 64:
            raise AssertionError("object manifest self-test failed")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-local-compose",
        action="store_true",
        help="Required acknowledgement that only temporary local restore targets are mutated.",
    )
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--postgres-user",
        default=os.environ.get("POSTGRES_USER", "careeros"),
    )
    parser.add_argument(
        "--postgres-database",
        default=os.environ.get("POSTGRES_DB", "careeros"),
    )
    parser.add_argument(
        "--source-bucket",
        default=os.environ.get("S3_BUCKET", "careeros-documents"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    try:
        if arguments.self_test:
            _self_test()
            print("local recovery verifier self-test passed")
            return 0
        if not arguments.confirm_local_compose:
            raise RecoveryError("--confirm-local-compose is required")
        report = verify_local_restore(
            repository_root=arguments.repository_root,
            postgres_user=arguments.postgres_user,
            postgres_database=arguments.postgres_database,
            source_bucket=arguments.source_bucket,
            output=arguments.output,
        )
    except (RecoveryError, OSError, UnicodeError) as exc:
        print(f"local recovery verification failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
