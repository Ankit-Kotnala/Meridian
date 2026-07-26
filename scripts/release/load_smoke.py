"""Bounded read-only HTTP load/soak gate with machine-readable evidence."""

from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

_MAX_RESPONSE_BYTES = 1_048_576
_MAX_SAMPLES = 100_000


class LoadGateError(ValueError):
    """A safe load-gate configuration or threshold failure."""

    def __init__(
        self,
        message: str,
        *,
        report: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.report = report


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


def run_gate(
    *,
    base_url: str,
    paths: tuple[str, ...],
    concurrency: int,
    request_count: int | None,
    soak_seconds: int | None,
    timeout_seconds: float,
    maximum_p95_ms: float,
    maximum_error_rate: float,
    minimum_requests_per_second: float,
    target_requests_per_second: float | None,
    allow_http: bool,
) -> dict[str, object]:
    origin = _origin(base_url, allow_http=allow_http)
    validated_paths = tuple(_path(path) for path in paths)
    if not 1 <= concurrency <= 128:
        raise LoadGateError("concurrency must be between 1 and 128")
    if (request_count is None) == (soak_seconds is None):
        raise LoadGateError("exactly one of request_count or soak_seconds is required")
    if request_count is not None and not 1 <= request_count <= _MAX_SAMPLES:
        raise LoadGateError(f"request_count must be between 1 and {_MAX_SAMPLES}")
    if soak_seconds is not None and not 1 <= soak_seconds <= 3_600:
        raise LoadGateError("soak_seconds must be between 1 and 3600")
    if not 0.1 <= timeout_seconds <= 60:
        raise LoadGateError("timeout_seconds must be between 0.1 and 60")
    if not 1 <= maximum_p95_ms <= 120_000:
        raise LoadGateError("maximum_p95_ms must be between 1 and 120000")
    if not 0 <= maximum_error_rate <= 1:
        raise LoadGateError("maximum_error_rate must be between 0 and 1")
    if not 0 <= minimum_requests_per_second <= 100_000:
        raise LoadGateError("minimum_requests_per_second is invalid")
    if (
        target_requests_per_second is not None
        and not 1 <= target_requests_per_second <= 10_000
    ):
        raise LoadGateError("target_requests_per_second is invalid")

    opener = urllib.request.build_opener(_NoRedirect)
    durations: list[float] = []
    errors: dict[str, int] = {}
    statuses: dict[str, int] = {}
    lock = threading.Lock()
    pace_lock = threading.Lock()
    stop = threading.Event()
    started = time.perf_counter()
    next_request_at = started

    def one(index: int) -> None:
        nonlocal next_request_at
        if target_requests_per_second is not None:
            with pace_lock:
                scheduled_at = max(time.perf_counter(), next_request_at)
                next_request_at = scheduled_at + 1 / target_requests_per_second
            delay = scheduled_at - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
        path = validated_paths[index % len(validated_paths)]
        request = urllib.request.Request(
            urljoin(origin + "/", path.lstrip("/")),
            method="GET",
            headers={
                "Accept": "application/json,text/html;q=0.5",
                "User-Agent": "CareerOS-release-load-gate/1",
            },
        )
        request_started = time.perf_counter()
        status_key = "unavailable"
        error_key: str | None = None
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                status = int(response.status)
                status_key = str(status)
                body = response.read(_MAX_RESPONSE_BYTES + 1)
                if len(body) > _MAX_RESPONSE_BYTES:
                    error_key = "response_too_large"
                elif not 200 <= status < 300:
                    error_key = f"http_{status}"
        except urllib.error.HTTPError as exc:
            status_key = str(exc.code)
            error_key = f"http_{exc.code}"
        except (OSError, TimeoutError, urllib.error.URLError):
            error_key = "request_unavailable"
        elapsed_ms = (time.perf_counter() - request_started) * 1_000
        with lock:
            durations.append(elapsed_ms)
            statuses[status_key] = statuses.get(status_key, 0) + 1
            if error_key is not None:
                errors[error_key] = errors.get(error_key, 0) + 1
            if len(durations) >= _MAX_SAMPLES:
                stop.set()

    if request_count is not None:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            tuple(executor.map(one, range(request_count)))
    else:
        assert soak_seconds is not None
        deadline = started + soak_seconds

        def soak_worker(worker_index: int) -> None:
            request_index = worker_index
            while time.perf_counter() < deadline and not stop.is_set():
                one(request_index)
                request_index += concurrency

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            tuple(executor.map(soak_worker, range(concurrency)))

    elapsed_seconds = max(0.000_001, time.perf_counter() - started)
    completed = len(durations)
    if completed == 0:
        raise LoadGateError("load gate completed no requests")
    failures = sum(errors.values())
    error_rate = failures / completed
    sorted_durations = sorted(durations)
    p50 = _percentile(sorted_durations, 50)
    p95 = _percentile(sorted_durations, 95)
    p99 = _percentile(sorted_durations, 99)
    requests_per_second = completed / elapsed_seconds
    passed = (
        error_rate <= maximum_error_rate
        and p95 <= maximum_p95_ms
        and requests_per_second >= minimum_requests_per_second
    )
    report: dict[str, object] = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "targetOrigin": origin,
        "paths": list(validated_paths),
        "concurrency": concurrency,
        "completedRequests": completed,
        "failedRequests": failures,
        "errorRate": round(error_rate, 6),
        "elapsedSeconds": round(elapsed_seconds, 3),
        "requestsPerSecond": round(requests_per_second, 3),
        "targetRequestsPerSecond": target_requests_per_second,
        "latencyMs": {
            "p50": round(p50, 3),
            "p95": round(p95, 3),
            "p99": round(p99, 3),
            "maximum": round(max(sorted_durations), 3),
        },
        "statuses": dict(sorted(statuses.items())),
        "safeErrors": dict(sorted(errors.items())),
        "thresholds": {
            "maximumP95Ms": maximum_p95_ms,
            "maximumErrorRate": maximum_error_rate,
            "minimumRequestsPerSecond": minimum_requests_per_second,
        },
        "passed": passed,
    }
    if not passed:
        raise LoadGateError(
            "load gate failed thresholds: "
            f"p95={p95:.3f}ms error_rate={error_rate:.6f} "
            f"requests_per_second={requests_per_second:.3f}",
            report=report,
        )
    return report


def _origin(value: str, *, allow_http: bool) -> str:
    parsed = urlsplit(value)
    allowed_schemes = {"https", "http"} if allow_http else {"https"}
    if (
        parsed.scheme not in allowed_schemes
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise LoadGateError("base_url must be a credential-free allowed origin")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise LoadGateError("HTTP load targets are limited to the local host")
    return value.rstrip("/")


def _path(value: str) -> str:
    parsed = urlsplit(value)
    if (
        not value.startswith("/")
        or value.startswith("//")
        or parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or len(value) > 512
    ):
        raise LoadGateError("paths must be bounded same-origin absolute paths")
    return value


def _percentile(sorted_values: list[float], percentile: int) -> float:
    if not sorted_values:
        raise LoadGateError("percentile requires at least one sample")
    rank = max(1, math.ceil((percentile / 100) * len(sorted_values)))
    return sorted_values[rank - 1]


class _SelfTestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


def _self_test() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SelfTestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        report = run_gate(
            base_url=f"http://127.0.0.1:{server.server_port}",
            paths=("/health", "/ready"),
            concurrency=4,
            request_count=20,
            soak_seconds=None,
            timeout_seconds=2,
            maximum_p95_ms=2_000,
            maximum_error_rate=0,
            minimum_requests_per_second=1,
            target_requests_per_second=None,
            allow_http=True,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    if report["completedRequests"] != 20 or report["passed"] is not True:
        raise AssertionError("load gate self-test failed")
    if _percentile([1, 2, 3, 4, 5], 95) != 5:
        raise AssertionError("percentile calculation is invalid")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--concurrency", type=int, default=8)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--requests", type=int)
    mode.add_argument("--soak-seconds", type=int)
    parser.add_argument("--timeout-seconds", type=float, default=5)
    parser.add_argument("--max-p95-ms", type=float, default=1_000)
    parser.add_argument("--max-error-rate", type=float, default=0)
    parser.add_argument("--min-requests-per-second", type=float, default=1)
    parser.add_argument("--target-requests-per-second", type=float)
    parser.add_argument("--allow-http", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    if arguments.self_test:
        _self_test()
        print("load gate self-test passed")
        return 0
    try:
        if not arguments.base_url:
            raise LoadGateError("base_url is required")
        report = run_gate(
            base_url=arguments.base_url,
            paths=tuple(arguments.path or ["/health"]),
            concurrency=arguments.concurrency,
            request_count=arguments.requests,
            soak_seconds=arguments.soak_seconds,
            timeout_seconds=arguments.timeout_seconds,
            maximum_p95_ms=arguments.max_p95_ms,
            maximum_error_rate=arguments.max_error_rate,
            minimum_requests_per_second=arguments.min_requests_per_second,
            target_requests_per_second=arguments.target_requests_per_second,
            allow_http=arguments.allow_http,
        )
    except LoadGateError as exc:
        if exc.report is not None:
            encoded = json.dumps(exc.report, sort_keys=True, separators=(",", ":"))
            if arguments.output is not None:
                arguments.output.parent.mkdir(parents=True, exist_ok=True)
                arguments.output.write_text(encoded + "\n", encoding="utf-8")
            print(encoded)
        print(f"load gate rejected: {exc}", file=sys.stderr)
        return 2
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":"))
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
