#!/usr/bin/env python3
"""V4.5.15: Prometheus end-to-end scrape verification (AC-PM-1..3).

Chain under test:
  DevSquadMetrics.record_risk_store_stats(FileRiskStore.stats)
  -> prometheus_client exposition served over HTTP
  -> promtool check metrics (format lint) + promtool check config
  -> Prometheus scrapes the target (scrape_interval=1s)
  -> /api/v1/query returns a non-empty sample for the recorded series
  -> processes/temp dirs cleaned up

Honest status contract (AC-PM-1): every run reports exactly one of
  pass          - full chain verified
  fail          - chain broke (details in error)
  tool_missing  - prometheus/promtool binaries not found (valid evidence
                  that E2E could not run; never faked as PASS)

Usage:
    python3 scripts/verify_prometheus_e2e.py [--evidence-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

EVIDENCE_DIR = PROJECT_ROOT / "docs" / "e2e_evidence" / "V4.5.15_prometheus_e2e"
BREW_BIN_DIRS = ("/opt/homebrew/bin", "/usr/local/bin")
QUERY_SERIES = "devsquad_v4512_risk_store_cross_host_signals_total"
SCRAPE_INTERVAL = "1s"
SCRAPE_TIMEOUT_S = 15.0
PROMETHEUS_START_TIMEOUT_S = 20.0


def find_binaries() -> dict[str, str | None]:
    """Locate prometheus/promtool on PATH or common brew prefixes."""
    found: dict[str, str | None] = {}
    for name in ("prometheus", "promtool"):
        path = shutil.which(name)
        if path is None:
            for d in BREW_BIN_DIRS:
                cand = Path(d) / name
                if cand.is_file():
                    path = str(cand)
                    break
        found[name] = path
    return found


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class _ExpositionHandler(BaseHTTPRequestHandler):
    """Serve a fresh exposition snapshot on every scrape."""

    body_provider: Any = None  # set by serve_exposition()

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        body = _ExpositionHandler.body_provider()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: Any) -> None:  # silence scrape noise
        return


def build_exposition_provider() -> Any:
    """Record real FileRiskStore stats through DevSquadMetrics; return bytes fn."""
    import tempfile as _tf

    from scripts.collaboration.file_risk_store import FileRiskStore
    from scripts.collaboration.prometheus_metrics import get_metrics

    metrics = get_metrics()
    if not metrics.is_available():
        raise RuntimeError("prometheus_client not installed")

    tmp = _tf.mkdtemp(prefix="devsquad_prom_e2e_store_")
    store = FileRiskStore(root=Path(tmp))
    payload = {
        "version": 1,
        "register_id": "default",
        "items": [
            {"id": "R-1", "description": "e2e", "probability": 0.5, "impact": 0.5,
             "response_strategy": "accept", "owner": "architect", "status": "open",
             "category": "general"},
        ],
    }
    store.save("default", payload)
    store.stats.record_cross_host_signal()
    store.stats.record_slow_query(80.0)
    metrics.record_risk_store_stats(store.stats)

    def provider() -> bytes:
        raw = metrics.generate_metrics()
        return raw if isinstance(raw, bytes) else raw.encode("utf-8")

    return provider


def serve_exposition(provider: Any) -> tuple[HTTPServer, int]:
    port = _free_port()
    _ExpositionHandler.body_provider = provider
    server = HTTPServer(("127.0.0.1", port), _ExpositionHandler)
    import threading

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, port


def write_prometheus_config(workdir: Path, exposition_port: int, listen_port: int) -> Path:
    config = workdir / "prometheus.yml"
    config.write_text(
        "global:\n"
        f"  scrape_interval: {SCRAPE_INTERVAL}\n"
        "scrape_configs:\n"
        "  - job_name: devsquad_e2e\n"
        "    static_configs:\n"
        f"      - targets: ['127.0.0.1:{exposition_port}']\n",
        encoding="utf-8",
    )
    del listen_port
    return config


def _wait_prometheus_ready(base_url: str, deadline_s: float) -> None:
    deadline = time.monotonic() + deadline_s
    last_err = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/-/ready", timeout=2) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, OSError) as exc:
            last_err = str(exc)
        time.sleep(0.3)
    raise RuntimeError(f"prometheus /-/ready not reachable in {deadline_s}s: {last_err}")


def query_series(base_url: str, query: str, timeout_s: float) -> list[dict[str, Any]]:
    """Poll /api/v1/query until the series has a sample or timeout."""
    deadline = time.monotonic() + timeout_s
    url = f"{base_url}/api/v1/query?query={urllib.request.quote(query)}"
    last: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success":
                result = data.get("data", {}).get("result", [])
                if result:
                    return result
                last = result
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            last = [{"error": str(exc)}]
        time.sleep(0.5)
    return last


def run_e2e() -> dict[str, Any]:
    """Full chain; returns honest-status dict."""
    binaries = find_binaries()
    if not binaries["prometheus"] or not binaries["promtool"]:
        return {
            "status": "tool_missing",
            "error": (
                "prometheus/promtool not found; install with: brew install prometheus"
            ),
            "binaries": binaries,
        }

    result: dict[str, Any] = {"status": "fail", "binaries": binaries, "checks": {}}
    workdir = Path(tempfile.mkdtemp(prefix="devsquad_prom_e2e_"))
    server = None
    prom_proc = None
    try:
        provider = build_exposition_provider()
        exposition = provider()
        result["checks"]["exposition_bytes"] = len(exposition)

        server, exposition_port = serve_exposition(provider)
        listen_port = _free_port()
        config = write_prometheus_config(workdir, exposition_port, listen_port)
        result["checks"]["exposition_port"] = exposition_port

        # promtool: lint the exposition format itself (stdin)
        lint = subprocess.run(
            [binaries["promtool"], "check", "metrics"],
            input=exposition, capture_output=True, timeout=30,
        )
        result["checks"]["promtool_check_metrics_rc"] = lint.returncode
        if lint.returncode != 0:
            result["error"] = f"promtool check metrics failed: {lint.stderr.decode()[:500]}"
            return result

        # promtool: validate the scrape config
        cfg = subprocess.run(
            [binaries["promtool"], "check", "config", str(config)],
            capture_output=True, timeout=30,
        )
        result["checks"]["promtool_check_config_rc"] = cfg.returncode
        if cfg.returncode != 0:
            result["error"] = f"promtool check config failed: {cfg.stderr.decode()[:500]}"
            return result

        # launch prometheus and wait for readiness
        prom_proc = subprocess.Popen(
            [
                binaries["prometheus"],
                f"--config.file={config}",
                f"--storage.tsdb.path={workdir / 'tsdb'}",
                f"--web.listen-address=127.0.0.1:{listen_port}",
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        base_url = f"http://127.0.0.1:{listen_port}"
        _wait_prometheus_ready(base_url, PROMETHEUS_START_TIMEOUT_S)
        result["checks"]["prometheus_ready"] = True

        samples = query_series(base_url, QUERY_SERIES, SCRAPE_TIMEOUT_S)
        result["checks"]["query"] = samples
        if not samples or "error" in samples[0]:
            result["error"] = f"query returned no sample for {QUERY_SERIES}: {samples}"
            return result

        result["status"] = "pass"
        result["queried_series"] = QUERY_SERIES
        return result
    except Exception as exc:  # noqa: BLE001 - honest fail with reason
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    finally:
        if prom_proc is not None:
            prom_proc.terminate()
            try:
                prom_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                prom_proc.kill()
        if server is not None:
            server.shutdown()
            server.server_close()
        shutil.rmtree(workdir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V4.5.15 Prometheus E2E verifier")
    parser.add_argument("--evidence-dir", type=Path, default=EVIDENCE_DIR)
    args = parser.parse_args(argv)

    result = run_e2e()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    (args.evidence_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[prometheus-e2e] status: {result['status']}")
    if result["status"] != "pass":
        print(f"  error: {result.get('error', '')}")
        return 1
    print(f"  queried series: {result.get('queried_series')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
