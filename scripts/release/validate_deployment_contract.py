"""Fail-closed validation for owner-approved production deployment metadata."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

EXPECTED_MIGRATION_HEAD = "20260727_0019"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_EVIDENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{7,255}$")
_PLACEHOLDERS = (
    ".invalid",
    ".local",
    ".test",
    "change-me",
    "example.",
    "fictional",
    "localhost",
    "owner_decision_required",
    "replace-me",
    "tbd",
    "todo",
)
_FORBIDDEN_KEY_PARTS = (
    "apikey",
    "credential",
    "password",
    "privatekey",
    "secret",
    "token",
)
_IMAGES = ("api", "worker", "web", "web-edge")


class ContractError(ValueError):
    """A safe deployment-contract validation failure."""


def validate_contract(
    value: object,
    *,
    expected_release_sha: str,
    expected_change_ticket: str,
    expected_candidate_checksums: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> str:
    contract = _mapping(value, "contract")
    _reject_secret_fields(contract)
    _exact_keys(
        contract,
        {
            "version",
            "release",
            "topology",
            "recovery",
            "security",
            "privacy",
            "operations",
            "approvals",
        },
        "contract",
    )
    if contract["version"] != 1:
        raise ContractError("contract version must be 1")

    release = _mapping(contract["release"], "release")
    _exact_keys(
        release,
        {
            "releaseSha",
            "changeTicket",
            "migrationHead",
            "productionUrl",
            "candidateArchiveChecksums",
            "deploymentImageDigests",
            "rollbackImageDigests",
            "canaryPercent",
            "observationMinutes",
        },
        "release",
    )
    release_sha = _text(release["releaseSha"], "release.releaseSha")
    if not _SHA.fullmatch(release_sha) or release_sha != expected_release_sha:
        raise ContractError("release SHA does not match the approved workflow revision")
    change_ticket = _text(release["changeTicket"], "release.changeTicket")
    if change_ticket != expected_change_ticket:
        raise ContractError("change ticket does not match the workflow approval input")
    if release["migrationHead"] != EXPECTED_MIGRATION_HEAD:
        raise ContractError("migration head is not the release head")
    _production_https_url(release["productionUrl"], "release.productionUrl")
    candidate_checksums = _digest_map(
        release["candidateArchiveChecksums"],
        "release.candidateArchiveChecksums",
    )
    deployment_digests = _digest_map(
        release["deploymentImageDigests"],
        "release.deploymentImageDigests",
    )
    rollback_digests = _digest_map(
        release["rollbackImageDigests"],
        "release.rollbackImageDigests",
    )
    if deployment_digests == rollback_digests:
        raise ContractError("rollback image digests must identify the prior release")
    if expected_candidate_checksums is not None:
        normalized_expected = {
            name: _normalize_digest(digest, f"expected checksum for {name}")
            for name, digest in expected_candidate_checksums.items()
        }
        if candidate_checksums != normalized_expected:
            raise ContractError(
                "candidate archive checksums do not match the packaged release"
            )
    _bounded_int(release["canaryPercent"], "release.canaryPercent", 1, 25)
    _bounded_int(release["observationMinutes"], "release.observationMinutes", 15, 1_440)

    topology = _mapping(contract["topology"], "topology")
    _exact_keys(
        topology,
        {
            "provider",
            "region",
            "dataResidency",
            "runtime",
            "postgres",
            "objectStorage",
            "redis",
            "queue",
            "scanner",
            "trustedProxyCidrs",
        },
        "topology",
    )
    for field in (
        "provider",
        "region",
        "dataResidency",
        "runtime",
        "postgres",
        "objectStorage",
        "redis",
        "queue",
        "scanner",
    ):
        _production_text(topology[field], f"topology.{field}")
    cidrs = topology["trustedProxyCidrs"]
    if not isinstance(cidrs, list) or not cidrs:
        raise ContractError("topology.trustedProxyCidrs must be a non-empty list")
    for candidate in cidrs:
        try:
            network = ipaddress.ip_network(
                _text(candidate, "trusted proxy CIDR"), strict=False
            )
        except ValueError as exc:
            raise ContractError("trusted proxy CIDR is invalid") from exc
        if network.prefixlen == 0:
            raise ContractError("trusted proxy CIDR must not trust the entire internet")

    reference_time = now or datetime.now(UTC)
    recovery = _mapping(contract["recovery"], "recovery")
    _exact_keys(
        recovery,
        {
            "rpoMinutes",
            "rtoMinutes",
            "backupRetentionDays",
            "pointInTimeRecoveryEnabled",
            "lastRestoreEvidenceId",
            "lastRestoreVerifiedAt",
        },
        "recovery",
    )
    _bounded_int(recovery["rpoMinutes"], "recovery.rpoMinutes", 1, 10_080)
    _bounded_int(recovery["rtoMinutes"], "recovery.rtoMinutes", 1, 10_080)
    _bounded_int(
        recovery["backupRetentionDays"],
        "recovery.backupRetentionDays",
        1,
        3_650,
    )
    _true(recovery["pointInTimeRecoveryEnabled"], "recovery.pointInTimeRecoveryEnabled")
    _evidence(recovery["lastRestoreEvidenceId"], "recovery.lastRestoreEvidenceId")
    _recent_timestamp(
        recovery["lastRestoreVerifiedAt"],
        "recovery.lastRestoreVerifiedAt",
        reference_time,
        timedelta(days=90),
    )

    security = _mapping(contract["security"], "security")
    _exact_keys(
        security,
        {
            "operatorMfaEnforced",
            "criticalFindingsOpen",
            "highFindingsOpen",
            "penetrationReviewEvidenceId",
            "keyRotationEvidenceId",
            "alertRoutingEvidenceId",
        },
        "security",
    )
    _true(security["operatorMfaEnforced"], "security.operatorMfaEnforced")
    if security["criticalFindingsOpen"] != 0 or security["highFindingsOpen"] != 0:
        raise ContractError("critical and high release findings must be zero")
    for field in (
        "penetrationReviewEvidenceId",
        "keyRotationEvidenceId",
        "alertRoutingEvidenceId",
    ):
        _evidence(security[field], f"security.{field}")

    privacy = _mapping(contract["privacy"], "privacy")
    _exact_keys(
        privacy,
        {
            "policyVersion",
            "accountRetentionDays",
            "backupDeletionExpiryDays",
            "providerErasureEvidenceId",
        },
        "privacy",
    )
    _production_text(privacy["policyVersion"], "privacy.policyVersion")
    _bounded_int(
        privacy["accountRetentionDays"],
        "privacy.accountRetentionDays",
        0,
        3_650,
    )
    backup_expiry = _bounded_int(
        privacy["backupDeletionExpiryDays"],
        "privacy.backupDeletionExpiryDays",
        1,
        3_650,
    )
    retention = int(privacy["accountRetentionDays"])
    if backup_expiry < retention:
        raise ContractError("backup deletion expiry cannot precede account retention")
    _evidence(privacy["providerErasureEvidenceId"], "privacy.providerErasureEvidenceId")

    operations = _mapping(contract["operations"], "operations")
    _exact_keys(
        operations,
        {
            "loadEvidenceId",
            "monitoringEvidenceId",
            "onCallSchedule",
            "incidentRunbookVersion",
            "rollbackTestEvidenceId",
        },
        "operations",
    )
    for field in (
        "loadEvidenceId",
        "monitoringEvidenceId",
        "rollbackTestEvidenceId",
    ):
        _evidence(operations[field], f"operations.{field}")
    _production_text(operations["onCallSchedule"], "operations.onCallSchedule")
    _production_text(
        operations["incidentRunbookVersion"],
        "operations.incidentRunbookVersion",
    )

    approvals = _mapping(contract["approvals"], "approvals")
    _exact_keys(
        approvals,
        {
            "releaseManager",
            "securityOwner",
            "privacyOwner",
            "operationsOwner",
        },
        "approvals",
    )
    for field in approvals:
        _production_text(approvals[field], f"approvals.{field}")

    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ContractError(f"{field} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ContractError(
            f"{field} keys are invalid; missing={missing}; extra={extra}"
        )


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise ContractError(f"{field} must be bounded non-empty text")
    if any(not character.isprintable() for character in value):
        raise ContractError(f"{field} contains control characters")
    return value.strip()


def _production_text(value: object, field: str) -> str:
    text = _text(value, field)
    if len(text) < 3 or any(marker in text.casefold() for marker in _PLACEHOLDERS):
        raise ContractError(f"{field} contains a placeholder or local value")
    return text


def _production_https_url(value: object, field: str) -> str:
    text = _production_text(value, field)
    parsed = urlsplit(text)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.hostname.endswith((".invalid", ".local", ".test"))
    ):
        raise ContractError(f"{field} must be a credential-free HTTPS URL")
    return text


def _bounded_int(value: object, field: str, minimum: int, maximum: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not minimum <= value <= maximum
    ):
        raise ContractError(f"{field} must be between {minimum} and {maximum}")
    return value


def _true(value: object, field: str) -> None:
    if value is not True:
        raise ContractError(f"{field} must be true")


def _evidence(value: object, field: str) -> str:
    text = _production_text(value, field)
    if not _EVIDENCE.fullmatch(text):
        raise ContractError(f"{field} is not a stable evidence identifier")
    return text


def _digest_map(value: object, field: str) -> dict[str, str]:
    mapping = _mapping(value, field)
    _exact_keys(mapping, set(_IMAGES), field)
    return {
        name: _normalize_digest(mapping[name], f"{field}.{name}") for name in _IMAGES
    }


def _normalize_digest(value: object, field: str) -> str:
    text = _text(value, field)
    if not text.startswith("sha256:"):
        text = f"sha256:{text}"
    if not _DIGEST.fullmatch(text):
        raise ContractError(f"{field} must be a SHA-256 digest")
    return text


def _recent_timestamp(
    value: object,
    field: str,
    now: datetime,
    maximum_age: timedelta,
) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{field} must be an RFC 3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"{field} must include a timezone")
    normalized = parsed.astimezone(UTC)
    if normalized > now + timedelta(minutes=5) or normalized < now - maximum_age:
        raise ContractError(f"{field} is outside the allowed evidence window")
    return normalized


def _reject_secret_fields(value: object, path: str = "contract") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z]", "", str(key).casefold())
            if any(part in normalized for part in _FORBIDDEN_KEY_PARTS):
                raise ContractError(f"{path} must not contain secret field {key!r}")
            _reject_secret_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_fields(child, f"{path}[{index}]")


def _self_test_contract(now: datetime) -> dict[str, object]:
    digest = "sha256:" + "a" * 64
    rollback = "sha256:" + "b" * 64
    return {
        "version": 1,
        "release": {
            "releaseSha": "c" * 40,
            "changeTicket": "REL-2026-APPROVED-001",
            "migrationHead": EXPECTED_MIGRATION_HEAD,
            "productionUrl": "https://careeros.company.com",
            "candidateArchiveChecksums": {name: digest for name in _IMAGES},
            "deploymentImageDigests": {name: digest for name in _IMAGES},
            "rollbackImageDigests": {name: rollback for name in _IMAGES},
            "canaryPercent": 5,
            "observationMinutes": 30,
        },
        "topology": {
            "provider": "approved-cloud-provider",
            "region": "approved-region-1",
            "dataResidency": "approved-jurisdiction",
            "runtime": "approved-managed-runtime",
            "postgres": "approved-managed-postgres",
            "objectStorage": "approved-managed-object-storage",
            "redis": "approved-managed-redis",
            "queue": "approved-managed-queue",
            "scanner": "approved-isolated-scanner",
            "trustedProxyCidrs": ["10.42.0.0/24"],
        },
        "recovery": {
            "rpoMinutes": 15,
            "rtoMinutes": 60,
            "backupRetentionDays": 30,
            "pointInTimeRecoveryEnabled": True,
            "lastRestoreEvidenceId": "EVIDENCE/RESTORE/APPROVED-001",
            "lastRestoreVerifiedAt": now.isoformat(),
        },
        "security": {
            "operatorMfaEnforced": True,
            "criticalFindingsOpen": 0,
            "highFindingsOpen": 0,
            "penetrationReviewEvidenceId": "EVIDENCE/PENTEST/APPROVED-001",
            "keyRotationEvidenceId": "EVIDENCE/ROTATION/APPROVED-001",
            "alertRoutingEvidenceId": "EVIDENCE/ALERT/APPROVED-001",
        },
        "privacy": {
            "policyVersion": "approved-policy-v1",
            "accountRetentionDays": 30,
            "backupDeletionExpiryDays": 35,
            "providerErasureEvidenceId": "EVIDENCE/ERASURE/APPROVED-001",
        },
        "operations": {
            "loadEvidenceId": "EVIDENCE/LOAD/APPROVED-001",
            "monitoringEvidenceId": "EVIDENCE/MONITOR/APPROVED-001",
            "onCallSchedule": "approved-primary-and-secondary",
            "incidentRunbookVersion": "approved-runbook-v1",
            "rollbackTestEvidenceId": "EVIDENCE/ROLLBACK/APPROVED-001",
        },
        "approvals": {
            "releaseManager": "approved-release-owner",
            "securityOwner": "approved-security-owner",
            "privacyOwner": "approved-privacy-owner",
            "operationsOwner": "approved-operations-owner",
        },
    }


def _self_test() -> None:
    now = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    contract = _self_test_contract(now)
    checksum = "sha256:" + "a" * 64
    expected_checksums = {name: checksum for name in _IMAGES}
    fingerprint = validate_contract(
        contract,
        expected_release_sha="c" * 40,
        expected_change_ticket="REL-2026-APPROVED-001",
        expected_candidate_checksums=expected_checksums,
        now=now,
    )
    if len(fingerprint) != 64:
        raise AssertionError("valid contract did not return a fingerprint")

    unsafe = json.loads(json.dumps(contract))
    unsafe["security"]["operatorMfaEnforced"] = False
    try:
        validate_contract(
            unsafe,
            expected_release_sha="c" * 40,
            expected_change_ticket="REL-2026-APPROVED-001",
            now=now,
        )
    except ContractError:
        pass
    else:
        raise AssertionError("unsafe MFA policy was accepted")

    secret_bearing = json.loads(json.dumps(contract))
    secret_bearing["topology"]["apiToken"] = "must-not-be-here"
    try:
        validate_contract(
            secret_bearing,
            expected_release_sha="c" * 40,
            expected_change_ticket="REL-2026-APPROVED-001",
            now=now,
        )
    except ContractError:
        pass
    else:
        raise AssertionError("secret-bearing contract was accepted")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--file", type=Path)
    source.add_argument("--json-env")
    parser.add_argument("--expected-release-sha")
    parser.add_argument("--expected-change-ticket")
    parser.add_argument(
        "--expected-candidate-checksum",
        action="append",
        default=[],
        metavar="NAME=SHA256",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def _checksum_arguments(values: list[str]) -> dict[str, str] | None:
    if not values:
        return None
    result: dict[str, str] = {}
    for value in values:
        name, separator, digest = value.partition("=")
        if not separator or name not in _IMAGES or name in result:
            raise ContractError("expected candidate checksum arguments are invalid")
        result[name] = digest
    if set(result) != set(_IMAGES):
        raise ContractError("expected candidate checksums must cover every image")
    return result


def main() -> int:
    arguments = _arguments()
    try:
        if arguments.self_test:
            _self_test()
            print("deployment contract self-test passed")
            return 0
        if not arguments.expected_release_sha or not arguments.expected_change_ticket:
            raise ContractError("expected release SHA and change ticket are required")
        if arguments.file is not None:
            payload = arguments.file.read_text(encoding="utf-8")
        elif arguments.json_env:
            payload = os.environ.get(arguments.json_env, "")
            if not payload:
                raise ContractError("deployment contract environment value is absent")
        else:
            raise ContractError("a deployment contract source is required")
        contract = json.loads(payload)
        fingerprint = validate_contract(
            contract,
            expected_release_sha=arguments.expected_release_sha,
            expected_change_ticket=arguments.expected_change_ticket,
            expected_candidate_checksums=_checksum_arguments(
                arguments.expected_candidate_checksum
            ),
        )
    except (ContractError, json.JSONDecodeError, OSError) as exc:
        print(f"deployment contract rejected: {exc}", file=sys.stderr)
        return 2
    print(f"deployment contract accepted; fingerprint={fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
