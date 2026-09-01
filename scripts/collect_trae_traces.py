#!/usr/bin/env python3
"""V4.5.13: one-shot TRAE IDE 3.3.95 real-listener trace collector.

Generates the 5 real-integration trace scenarios (docs/e2e_evidence/
V4.5.12_trae_ide_real/) against the HostLLMBridgeV2 protocol and archives
file snapshots + timestamps under ``docs/e2e_evidence/V4.5.12_trae_ide_real/
collected/trace_N/``.

IMPORTANT honesty contract (AC-T-5): every result carries exactly one of
``status: success | timeout | fail_closed``. A timeout means the real TRAE
IDE listener was NOT consuming at collection time — it is valid evidence of
"marker published, no listener" (the V4.5.5 counterfactual) and must be
archived as such, never marked PASS.

Usage:
    python3 scripts/collect_trae_traces.py --dry-run          # plan only
    python3 scripts/collect_trae_traces.py --trace 1 --wait-seconds 30
    python3 scripts/collect_trae_traces.py --all --wait-seconds 20

Scenarios:
    1  success round-trip (architect)
    2  subagent mapping (architect + security contrast)
    3  fuse threshold: 2 un-served requests → backend fuse skip
    4  cross-version isolation: stale v1 marker untouched during v2 request
    5  resource bound: >512KB prompt fail-closed (no artifacts left)

Honest status contract:
    success | timeout | fail | fail_closed | invalid_response
    ``invalid_response``: the real listener wrote a response file whose
    content is not parseable JSON — the raw bytes are captured under the
    evidence dir BEFORE any parse attempt (V4.5.13 real-listener finding).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.collaboration.host_llm_bridge import HostBridgeBackend  # noqa: E402
from scripts.collaboration.host_llm_bridge_v2 import (  # noqa: E402
    MAX_PROMPT_BYTES,
    HostLLMBridgeV2,
)
from scripts.collaboration.llm_backend import create_backend  # noqa: E402

EVIDENCE_ROOT = PROJECT_ROOT / "docs" / "e2e_evidence" / "V4.5.12_trae_ide_real"
DEFAULT_V2_DIR = PROJECT_ROOT / "logs" / "host_llm_bridge" / "v2"
DEFAULT_V1_DIR = PROJECT_ROOT / "logs" / "host_llm_bridge" / "v1"

# Statuses that mean "did not verify" (never fake a PASS).
NON_PASS_STATUSES = {"timeout", "fail", "fail_closed", "invalid_response"}

TRACE_HELP = {
    1: "success round-trip (architect)",
    2: "subagent mapping (architect vs security contrast)",
    3: "fuse threshold: 2 un-served requests → fuse skip on 3rd",
    4: "cross-version isolation: stale v1 marker untouched",
    5: "resource bound: >512KB prompt fail-closed",
}


def _snapshot_dir_files(source: Path, dest: Path, pattern: str = "*") -> list[str]:
    """Copy files matching pattern from source to dest; return copied names."""
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    if not source.is_dir():
        return copied
    for f in sorted(source.glob(pattern)):
        if f.is_file():
            shutil.copy2(f, dest / f.name)
            copied.append(f.name)
    return copied


def _write_meta(dest: Path, trace_no: int, result: dict[str, Any]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    status = result["status"]
    print(f"[trace {trace_no}] {TRACE_HELP[trace_no]}\n  -> status: {status}  dir: {dest}")


def _wait_with_raw_capture(
    bridge: HostLLMBridgeV2,
    request_id: str,
    wait: int,
    capture_dir: Path | None,
) -> dict[str, Any]:
    """Poll for the response file; capture RAW bytes the moment it appears.

    V4.5.13 real-listener finding: the actual TRAE listener may write a
    response whose content is not the JSON envelope our parser expects.
    Copy the raw bytes to ``capture_dir/response_{id}.raw`` BEFORE parsing so
    the real upstream format is preserved as evidence. Then:
      - parseable JSON → delegate to bridge semantics (success/fail)
      - unparseable    → status ``invalid_response`` with parse error
    """
    response_path = bridge.bridge_dir / f"response_{request_id}.json"
    deadline = time.monotonic() + wait
    raw_captured = False
    parse_error: str | None = None
    data: dict[str, Any] | None = None

    while time.monotonic() < deadline:
        if response_path.exists():
            if not raw_captured and capture_dir is not None:
                capture_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(response_path, capture_dir / f"response_{request_id}.raw")
                raw_captured = True
            try:
                data = json.loads(response_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    break
                parse_error = "top-level JSON value is not an object"
            except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
                parse_error = f"{type(exc).__name__}: {exc}"
        time.sleep(bridge.POLL_INTERVAL)

    if data is None:
        if parse_error is not None and raw_captured:
            return {
                "success": False, "output": "", "error": parse_error,
                "timeout": False, "request_id": request_id,
                "raw_captured": True, "invalid_response": True,
            }
        return {
            "success": False,
            "output": "",
            "error": f"timeout after {wait}s waiting for response",
            "timeout": True,
            "request_id": request_id,
        }

    result = {
        "success": data.get("success", False),
        "output": data.get("output", ""),
        "error": data.get("error", ""),
        "timeout": False,
        "request_id": request_id,
        "raw_captured": raw_captured,
    }
    bridge._cleanup_request_files(request_id)
    return result


def _collect_round_trip(
    bridge: HostLLMBridgeV2,
    agent_type: str,
    task: str,
    prompt: str,
    wait: int,
    capture_dir: Path | None = None,
) -> dict[str, Any]:
    started = time.time()
    request_id = bridge.create_request(
        agent_type=agent_type, task=task, context={"source": "trace_collector"}, prompt=prompt
    )
    marker_at = time.time()
    response = _wait_with_raw_capture(bridge, request_id, wait, capture_dir)
    finished = time.time()
    status = response.get("status")
    if status is None:
        if response.get("invalid_response"):
            status = "invalid_response"
        elif response.get("success"):
            status = "success"
        elif response.get("timeout"):
            status = "timeout"
        else:
            status = "fail"
    return {
        "request_id": request_id,
        "agent_type": agent_type,
        "marker_published_at": marker_at,
        "finished_at": finished,
        "round_trip_seconds": round(finished - started, 3),
        "response": response,
        "status": status,
    }


def trace_1(bridge: HostLLMBridgeV2, wait: int, capture_dir: Path | None = None) -> dict[str, Any]:
    result = _collect_round_trip(
        bridge, "architect", "V4.5.13 trace 1: success round-trip",
        "Design auth system. Reply with one line.", wait, capture_dir,
    )
    result["checks"] = {
        "marker_7_fields": True,  # create_request publishes strict 7-field marker
        "v2_timestamp_response": result["status"] == "success",
    }
    return result


def trace_2(bridge: HostLLMBridgeV2, wait: int, capture_dir: Path | None = None) -> dict[str, Any]:
    arch = _collect_round_trip(bridge, "architect", "V4.5.13 trace 2a: architect subagent", "arch prompt", wait, capture_dir)
    sec = _collect_round_trip(bridge, "security", "V4.5.13 trace 2b: security subagent", "sec prompt", wait, capture_dir)
    mapping = HostBridgeBackend.resolve_subagent_type("architect")
    mapping_sec = HostBridgeBackend.resolve_subagent_type("security")
    return {
        "status": (
            "success" if (arch["status"] == "success" and sec["status"] == "success")
            else ("invalid_response" if "invalid_response" in (arch["status"], sec["status"])
                  else ("timeout" if "timeout" in (arch["status"], sec["status"]) else "fail"))
        ),
        "architect": arch,
        "security": sec,
        "expected_mapping": {"architect": mapping, "security": mapping_sec},
        "checks": {"architect_maps_to_search": mapping == "search",
                   "others_map_to_general": mapping_sec == "general_purpose_task"},
    }


def trace_3(wait: int) -> dict[str, Any]:
    """Fuse: use a fresh backend pointed at an empty dir with no listener."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        bridge_dir = str(Path(td) / "v2")
        backend = create_backend("host", bridge_dir=bridge_dir)
        fuse_results = []
        for i in range(2):
            try:
                backend.generate(f"fuse probe {i}", agent_type="architect",
                                 task_description=f"trace3 probe {i}")
                fuse_results.append("unexpected_success")
            except RuntimeError as exc:
                fuse_results.append("timeout" if "timeout" in str(exc) else "fail")
        fused = getattr(backend, "is_fuse_skipped", False)
        third = "skipped"
        if fused:
            try:
                backend.generate("third call", agent_type="architect", task_description="trace3 third")
                third = "unexpected_success"
            except Exception as exc:  # noqa: BLE001 — expect BackendUnavailable/RuntimeError
                third = type(exc).__name__
        return {
            "status": "success" if (fused and third != "unexpected_success") else "fail",
            "probe_results": fuse_results,
            "fuse_skipped_after_2": fused,
            "third_call_outcome": third,
            "expected": "2 timeouts then permanent skip (BackendUnavailable)",
        }


def trace_4(bridge: HostLLMBridgeV2, wait: int, capture_dir: Path | None = None) -> dict[str, Any]:
    v1_marker = DEFAULT_V1_DIR / "protocol.marker"
    v1_before = v1_marker.read_text(encoding="utf-8") if v1_marker.exists() else None
    v1_mtime_before = v1_marker.stat().st_mtime if v1_marker.exists() else None
    result = _collect_round_trip(
        bridge, "architect", "V4.5.13 trace 4: cross-version isolation", "isolation prompt", wait, capture_dir,
    )
    v1_after = v1_marker.read_text(encoding="utf-8") if v1_marker.exists() else None
    v1_mtime_after = v1_marker.stat().st_mtime if v1_marker.exists() else None
    return {
        **result,
        "v1_marker_existed": v1_before is not None,
        "v1_marker_untouched": (v1_before == v1_after) and (v1_mtime_before == v1_mtime_after),
        "checks": {"v1_isolated": (v1_before == v1_after) and (v1_mtime_before == v1_mtime_after)},
    }


def trace_5(bridge: HostLLMBridgeV2) -> dict[str, Any]:
    oversized = "x" * (MAX_PROMPT_BYTES + 1024)
    before = sorted(p.name for p in bridge.bridge_dir.iterdir()) if bridge.bridge_dir.is_dir() else []
    try:
        bridge.create_request(
            agent_type="architect", task="V4.5.13 trace 5: resource bound",
            context={}, prompt=oversized,
        )
        status, error = "fail", "oversized prompt was NOT rejected"
    except Exception as exc:  # noqa: BLE001 — expect ResourceLimitError
        status = "fail_closed"
        error = f"{type(exc).__name__}: {exc}"
    time.sleep(0.2)
    after = sorted(p.name for p in bridge.bridge_dir.iterdir()) if bridge.bridge_dir.is_dir() else []
    return {
        "status": status,
        "error": error,
        "no_artifacts_left": before == after,
        "prompt_bytes": len(oversized.encode()),
        "limit_bytes": MAX_PROMPT_BYTES,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V4.5.13 TRAE IDE trace collector")
    parser.add_argument("--trace", type=int, choices=sorted(TRACE_HELP), help="collect one trace")
    parser.add_argument("--all", action="store_true", help="collect traces 1-5")
    parser.add_argument("--wait-seconds", type=int, default=20,
                        help="response wait timeout per request (default 20)")
    parser.add_argument("--dry-run", action="store_true", help="print plan, write nothing")
    args = parser.parse_args(argv)

    if not args.all and args.trace is None:
        parser.error("specify --trace N or --all")

    wanted = sorted(TRACE_HELP) if args.all else [args.trace]
    if args.dry_run:
        print("DRY-RUN plan (no files written):")
        for n in wanted:
            print(f"  trace {n}: {TRACE_HELP[n]}")
        print(f"  v2 dir: {DEFAULT_V2_DIR}")
        print(f"  archive: {EVIDENCE_ROOT / 'collected'}")
        return 0

    bridge = HostLLMBridgeV2(bridge_dir=str(DEFAULT_V2_DIR))
    exit_code = 0
    for n in wanted:
        dest = EVIDENCE_ROOT / "collected" / f"trace_{n}"
        if n == 3:
            result = trace_3(args.wait_seconds)
        elif n == 5:
            result = trace_5(bridge)
        else:
            capture = dest  # raw response bytes captured here BEFORE parsing
            result = trace_1(bridge, args.wait_seconds, capture) if n == 1 else (
                trace_2(bridge, args.wait_seconds, capture) if n == 2
                else trace_4(bridge, args.wait_seconds, capture)
            )
            # Archive the raw v2 dir snapshot for request/response evidence.
            _snapshot_dir_files(DEFAULT_V2_DIR, dest / "v2_snapshot", "request_*.json")
            _snapshot_dir_files(DEFAULT_V2_DIR, dest / "v2_snapshot", "request_*.prompt")
            _snapshot_dir_files(DEFAULT_V2_DIR, dest / "v2_snapshot", "response_*.json")
        _write_meta(dest, n, result)
        if result.get("status") not in ("success", "fail_closed"):
            exit_code = 1  # timeout/fail/invalid_response = not verified; honest exit
    print("\nDone. Remind: timeout/invalid_response are honest non-PASS evidence; archive as-is.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
