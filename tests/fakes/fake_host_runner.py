#!/usr/bin/env python3
"""
FakeHostRunner — CI-side simulator for a programming AI host.

Per V4.5.2_ARCHITECTURE.md §5.2: a process-isolated simulator that
replays host behavior in CI without needing a real IDE/LLM.

Behaviours (via ``behaviour`` parameter):
  - "success":  read marker, write success=True response with template.
  - "fail":     write success=False with given error.
  - "delay":    sleep delay_seconds before responding.
  - "timeout":  never respond (host is unresponsive).
  - "marker_corrupt": write half-truncated JSON to response.

Run standalone (used by multiprocessing.Process target):
    python tests/fakes/fake_host_runner.py <bridge_dir> <behaviour> [delay]

Or as a class:
    runner = FakeHostRunner(bridge_dir, behaviour="success")
    runner.run_forever()  # blocks until KeyboardInterrupt

Anti-Ghost: process actually opens / writes files; tests verify side effects.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

# Default poll interval for marker scan (must align with HostLLMBridge)
DEFAULT_POLL_INTERVAL = 0.2


class FakeHostRunner:
    """Simulate a host that scans the bridge directory and writes responses.

    Args:
        bridge_dir: Directory containing protocol.marker and request_*.json.
        behaviour: One of "success" | "fail" | "delay" | "timeout" |
            "marker_corrupt". Default "success".
        delay_seconds: Sleep before writing response (for "delay" behaviour).
        response_template: Optional output text for success path. If None,
            uses an echo of the request prompt.
        fail_error: Error string for "fail" behaviour. Default "mock_fail".
    """

    def __init__(
        self,
        bridge_dir: str,
        behaviour: str = "success",
        delay_seconds: float = 0.0,
        response_template: str | None = None,
        fail_error: str = "mock_fail",
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self.bridge_dir = bridge_dir
        self.behaviour = behaviour
        self.delay_seconds = delay_seconds
        self.response_template = response_template
        self.fail_error = fail_error
        self.poll_interval = poll_interval
        # Lazy import to avoid forcing host_llm_bridge path at module import
        from scripts.collaboration.host_llm_bridge import HostLLMBridge
        self._bridge = HostLLMBridge

    # ---- file helpers ----

    def _read_marker(self) -> dict[str, Any] | None:
        return self._bridge.read_marker(self.bridge_dir)

    def _read_request(self, request_id: str) -> dict[str, Any] | None:
        path = os.path.join(self.bridge_dir, f"request_{request_id}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.loads(f.read())
        except (OSError, json.JSONDecodeError):
            return None

    def _write_success(self, request_id: str, output: str) -> None:
        self._bridge.write_response(
            request_id=request_id,
            success=True,
            output=output,
            bridge_dir=self.bridge_dir,
        )

    def _write_failure(self, request_id: str, error: str) -> None:
        self._bridge.write_response(
            request_id=request_id,
            success=False,
            output="",
            error=error,
            bridge_dir=self.bridge_dir,
        )

    def _write_corrupt(self, request_id: str) -> None:
        """Write half-truncated JSON; tests expect retry-then-fail behaviour."""
        path = os.path.join(self.bridge_dir, f"response_{request_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"request_id": "x", "success": ')  # truncated

    # ---- main loop ----

    def process_one(self) -> bool:
        """Scan marker once, respond if present. Return True if processed.

        Used both by run_forever() and by direct test invocations.
        """
        marker = self._read_marker()
        if not marker:
            return False
        request_id = marker.get("request_id")
        if not request_id or not self._bridge.validate_request_id(request_id):
            # Clear invalid marker to avoid stuck loop
            self._bridge.clear_marker(self.bridge_dir)
            return False

        request = self._read_request(request_id)
        # Simulate optional delay before responding
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)

        if self.behaviour == "timeout":
            # Never respond — leave marker + request files in place
            return True

        if self.behaviour == "marker_corrupt":
            self._write_corrupt(request_id)
            return True

        if self.behaviour == "fail":
            self._write_failure(request_id, self.fail_error)
            return True

        # default: success
        if self.response_template is not None:
            output = self.response_template
        else:
            prompt = (request or {}).get("prompt", "")
            output = f"[FAKE HOST] Processed prompt ({len(prompt)} chars)"
        self._write_success(request_id, output)
        return True

    def run_forever(self, max_iterations: int | None = None) -> int:
        """Loop processing markers until KeyboardInterrupt or max_iterations.

        Returns:
            Number of iterations executed.
        """
        iterations = 0
        try:
            while True:
                if max_iterations is not None and iterations >= max_iterations:
                    return iterations
                self.process_one()
                iterations += 1
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            return iterations


# ---------------------------------------------------------------------------
# Module entry point (for multiprocessing.Process target)
# ---------------------------------------------------------------------------


def _main(bridge_dir: str, behaviour: str, delay_seconds: float = 0.0) -> None:
    """Standalone entry: process markers until killed or timeout."""
    runner = FakeHostRunner(
        bridge_dir=bridge_dir,
        behaviour=behaviour,
        delay_seconds=delay_seconds,
    )
    runner.run_forever()


if __name__ == "__main__":
    # CLI usage: python fake_host_runner.py <bridge_dir> <behaviour> [delay]
    if len(sys.argv) < 3:
        print("Usage: fake_host_runner.py <bridge_dir> <behaviour> [delay_seconds]",
              file=sys.stderr)
        sys.exit(2)
    _main(
        bridge_dir=sys.argv[1],
        behaviour=sys.argv[2],
        delay_seconds=float(sys.argv[3]) if len(sys.argv) > 3 else 0.0,
    )


__all__ = ["FakeHostRunner", "DEFAULT_POLL_INTERVAL"]
