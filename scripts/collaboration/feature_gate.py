#!/usr/bin/env python3
"""FeatureGate — V4.9.0 P2-W4: live acceptance-coverage matrix gate.

Computes the "acceptance checklist × PASS" matrix from the gate's own real
command executions — never from worker/LLM coverage claims (anti-ghost,
same source discipline as D2). The checklist hash is anchored at load time
(pre-steps) and re-computed at evaluation time (Step 23.5); a rewrite in
between fails as ``checklist_tampered`` (D4 — no moving goalposts).

Checklist contract (schema v1, ``.devsquad/acceptance_checklist.json``)::

    {
        "schema_version": 1,
        "items": [
            {
                "id": "AC-001",
                "description": "login endpoint returns 200 for valid credentials",
                "verify": {"kind": "command", "command": "python -m pytest ..."},
                "waive_reason": null,
            }
        ],
    }

Design authority: ``docs/planning/V4.9.0_W4_feature-gate_DESIGN.md``.

Fail-closed boundaries (D10): missing file, unparsable JSON, unknown
schema_version, empty items, duplicate ids, missing ``verify``, unknown
``verify.kind`` — all FAIL with explicit violations. No silent pass, no
"no checklist = pass".

Command discipline (D11): commands come only from the human-written
checklist file (CI-config trust level); the gate never executes text
produced by workers/LLMs. Each command runs via ``subprocess.run`` with
``shell=True``, captured output tail-truncated to 2000 chars, and a
mandatory timeout (timeout = that item FAILs — inability to prove is a
failure). No environment injection is performed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_CHECKLIST_PATH",
    "DEFAULT_COMMAND_TIMEOUT_SECONDS",
    "OUTPUT_TAIL_CHARS",
    "SUPPORTED_SCHEMA_VERSION",
    "FeatureGate",
    "FeatureGateResult",
]

SUPPORTED_SCHEMA_VERSION = 1
OUTPUT_TAIL_CHARS = 2000
DEFAULT_CHECKLIST_PATH = ".devsquad/acceptance_checklist.json"
DEFAULT_COMMAND_TIMEOUT_SECONDS = 120


def _tail(text: str, limit: int = OUTPUT_TAIL_CHARS) -> str:
    """Truncate ``text`` to its last ``limit`` characters."""
    if len(text) <= limit:
        return text
    return text[-limit:]


@dataclass
class FeatureGateResult:
    """Outcome of one feature-gate evaluation (Step 23.5).

    ``verdict`` is ``"pass"`` iff every checklist entry is ``pass`` or
    ``waived``; any fail / missing / invalid / tamper verdict detail makes
    it ``"fail"`` (D6/D10). ``violations`` carries the fail-closed
    boundary details; ``entries`` is the live execution matrix.
    """

    verdict: str
    checklist_path: str
    anchored_sha256: str | None = None
    computed_sha256: str | None = None
    command_timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS
    entries: list[dict[str, Any]] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.verdict == "pass"

    def to_dict(self) -> dict[str, Any]:
        """Serialize for ``details["feature_gate"]`` / audit events (D4)."""
        counts = {"pass": 0, "fail": 0, "waived": 0}
        for entry in self.entries:
            status = entry.get("status")
            if status in counts:
                counts[status] += 1
        gaps = [
            {"id": entry.get("id"), "description": entry.get("description")}
            for entry in self.entries
            if entry.get("status") not in ("pass", "waived")
        ]
        waived = [
            {
                "id": entry.get("id"),
                "description": entry.get("description"),
                "waive_reason": entry.get("waive_reason"),
            }
            for entry in self.entries
            if entry.get("status") == "waived"
        ]
        return {
            "verdict": self.verdict,
            "checklist_path": self.checklist_path,
            "anchored_sha256": self.anchored_sha256,
            "computed_sha256": self.computed_sha256,
            "command_timeout_seconds": self.command_timeout_seconds,
            "summary": {"total": len(self.entries), **counts},
            "entries": [dict(entry) for entry in self.entries],
            "violations": list(self.violations),
            "gaps": gaps,
            "waived": waived,
            "error": self.error,
        }

    @classmethod
    def internal_error(cls, message: str, checklist_path: str = "unknown") -> FeatureGateResult:
        """Fail-closed result for gate-internal errors (never a silent pass)."""
        return cls(
            verdict="fail",
            checklist_path=checklist_path,
            error=message,
            violations=[f"gate_error: {message}"],
        )


def _validate_checklist(data: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate schema v1; return ``(normalized_items, violations)``.

    Any violation ⇒ non-empty ``violations`` (fail-closed, D10). Items are
    normalized: missing/blank ``waive_reason`` becomes ``None`` (mandatory
    execution); a non-empty string waives the entry (D9).
    """
    violations: list[str] = []
    if not isinstance(data, dict):
        return [], ["checklist_invalid: top-level JSON must be an object"]
    version = data.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        return [], [
            f"checklist_invalid: unsupported schema_version {version!r} (supported: {SUPPORTED_SCHEMA_VERSION})"
        ]
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return [], ["checklist_invalid: 'items' must be a non-empty list"]
    seen_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        prefix = f"item[{idx}]"
        if not isinstance(item, dict):
            violations.append(f"{prefix}: must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            violations.append(f"{prefix}: 'id' must be a non-empty string")
            item_id = None
        elif item_id in seen_ids:
            violations.append(f"{prefix}: duplicate id {item_id!r}")
        else:
            seen_ids.add(item_id)
        description = item.get("description")
        if not isinstance(description, str) or not description:
            violations.append(f"{prefix}: 'description' must be a non-empty string")
            description = ""
        verify = item.get("verify")
        if not isinstance(verify, dict):
            violations.append(f"{prefix}: 'verify' must be an object with kind/command")
            verify = None
        else:
            kind = verify.get("kind")
            if kind != "command":
                violations.append(f"{prefix}: unsupported verify.kind {kind!r} (v1 supports 'command' only)")
            command = verify.get("command")
            if not isinstance(command, str) or not command:
                violations.append(f"{prefix}: 'verify.command' must be a non-empty string")
        waive = item.get("waive_reason")
        if waive is not None and (not isinstance(waive, str) or not waive.strip()):
            waive = None
        normalized.append(
            {
                "id": item_id,
                "description": description,
                "verify": verify,
                "waive_reason": waive,
            }
        )
    return normalized, violations


class FeatureGate:
    """Live acceptance-coverage gate with SHA256 checklist anchoring.

    Usage inside the dispatch pipeline (design §4)::

        gate = FeatureGate()
        anchor = gate.anchor(".devsquad/acceptance_checklist.json")  # pre-steps
        result = gate.evaluate(anchor, timeout_seconds=120)  # Step 23.5
    """

    def anchor(self, path: str | Path) -> dict[str, Any]:
        """Anchor the checklist at load time (pre-steps, D4).

        Records the resolved absolute path, the file byte-hash, the parse
        status, and the item descriptions (consumed by the D8 cross-check
        injection). A missing or invalid file still anchors — the status
        records why — so the failure surfaces at Step 23.5 as a FAIL;
        anchoring never short-circuits the dispatch and never silently
        passes.
        """
        resolved = Path(path).resolve()
        anchor: dict[str, Any] = {
            "path": str(resolved),
            "sha256": None,
            "status": "ok",
            "violations": [],
            "descriptions": [],
        }
        try:
            raw = resolved.read_bytes()
        except OSError as exc:
            anchor["status"] = "missing"
            anchor["violations"] = [f"checklist_missing: cannot read {resolved}: {exc}"]
            return anchor
        anchor["sha256"] = hashlib.sha256(raw).hexdigest()
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            anchor["status"] = "invalid"
            anchor["violations"] = [f"checklist_invalid: {exc}"]
            return anchor
        items, violations = _validate_checklist(data)
        if violations:
            anchor["status"] = "invalid"
            anchor["violations"] = violations
        else:
            anchor["descriptions"] = [item["description"] for item in items]
        return anchor

    def evaluate(
        self,
        anchor: dict[str, Any],
        *,
        timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    ) -> FeatureGateResult:
        """Evaluate the coverage matrix: re-hash, compare, execute, aggregate.

        Runs at Step 23.5, after all workers finished, so the
        anchor→evaluate window covers the whole worker execution phase.
        Commands execute with the process CWD (the project root for CLI
        dispatch) and a mandatory timeout (D11).
        """
        path_str = str(anchor.get("path", "unknown"))
        result = FeatureGateResult(
            verdict="fail",
            checklist_path=path_str,
            anchored_sha256=anchor.get("sha256"),
            command_timeout_seconds=timeout_seconds,
        )
        # 1. Anchor-side failures (missing / invalid at load time, D10).
        if anchor.get("status", "ok") != "ok":
            result.violations = list(anchor.get("violations", []))
            return result
        # 2. Re-read + re-hash (tamper detection, D4).
        try:
            raw = Path(path_str).read_bytes()
        except OSError as exc:
            result.violations = [f"checklist_missing: cannot read {path_str}: {exc}"]
            return result
        result.computed_sha256 = hashlib.sha256(raw).hexdigest()
        if result.computed_sha256 != result.anchored_sha256:
            result.violations = [
                "checklist_tampered: checklist changed after anchoring "
                f"(anchored={result.anchored_sha256}, computed={result.computed_sha256})"
            ]
            return result
        # 3. Re-parse + re-validate (hash match guarantees byte equality,
        #    so this re-validation is defense-in-depth, not a second opinion).
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            result.violations = [f"checklist_invalid: {exc}"]
            return result
        items, violations = _validate_checklist(data)
        if violations:
            result.violations = violations
            return result
        # 4. Execute every non-waived entry (D11 discipline).
        for item in items:
            entry: dict[str, Any] = {
                "id": item["id"],
                "description": item["description"],
                "waive_reason": item["waive_reason"],
            }
            if item["waive_reason"]:
                entry["status"] = "waived"
                result.entries.append(entry)
                continue
            command = (item["verify"] or {}).get("command", "")
            entry["command"] = command
            try:
                proc = subprocess.run(
                    command,
                    # nosec B602 — D11: command text comes only from the human-authored
                    # acceptance checklist file (same trust level as CI config); design
                    # §9 security review (V4.9.0 W4) adjudicated shell=True acceptable.
                    shell=True,
                    capture_output=True,
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                entry["status"] = "fail"
                entry["timed_out"] = True
            except OSError as exc:
                entry["status"] = "fail"
                entry["error"] = f"command failed to start: {exc}"
            else:
                entry["exit_code"] = proc.returncode
                entry["stdout_tail"] = _tail(proc.stdout.decode("utf-8", "replace"))
                entry["stderr_tail"] = _tail(proc.stderr.decode("utf-8", "replace"))
                entry["status"] = "pass" if proc.returncode == 0 else "fail"
            result.entries.append(entry)
        # 5. Aggregate: pass iff every entry is pass or waived (D6).
        result.verdict = "pass" if all(entry["status"] in ("pass", "waived") for entry in result.entries) else "fail"
        return result
