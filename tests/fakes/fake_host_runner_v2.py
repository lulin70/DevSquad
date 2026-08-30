#!/usr/bin/env python3
"""
FakeHostRunnerV2 — CI-side simulator for a programming AI host (v2 protocol).

V4.5.10 (G-δ): process-isolated simulator for the hardened HostLLMBridgeV2
protocol. Listens ONLY on the v2 version dir + protocol.v2.marker; never
reads v1 files.

Behaviours (via ``behaviour`` parameter):
  - "success":  read v2 marker, write success=True response.
  - "fail":     write success=False with given error.
  - "delay":    sleep delay_seconds before responding.
  - "timeout":  never respond (host is unresponsive).

Run standalone (used by subprocess/multiprocessing):
    python tests/fakes/fake_host_runner_v2.py <bridge_dir> <behaviour> [delay]
"""

from __future__ import annotations

import sys
import time
from typing import Any

from tests.fakes.fake_host_runner import DEFAULT_POLL_INTERVAL


class FakeHostRunnerV2:
    """Simulate a v2 host: scans protocol.v2.marker and writes responses.

    The response file uses the v2 ``timestamp`` field (not v1's
    ``completed_at``), so a successful round-trip proves the subprocess
    actually spoke the v2 protocol.
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
        from scripts.collaboration.host_llm_bridge_v2 import HostLLMBridgeV2

        self.bridge_dir = bridge_dir
        self.behaviour = behaviour
        self.delay_seconds = delay_seconds
        self.response_template = response_template
        self.fail_error = fail_error
        self.poll_interval = poll_interval
        self._bridge = HostLLMBridgeV2

    def _read_marker(self) -> dict[str, Any] | None:
        return self._bridge.read_marker(self.bridge_dir)

    def _read_prompt(self, request_id: str) -> str:
        path = f"{self.bridge_dir}/request_{request_id}.prompt"
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def process_one(self) -> bool:
        """Scan the v2 marker once; respond if present and valid."""
        marker = self._read_marker()
        if not marker:
            return False
        request_id = marker.get("request_id", "")
        if not request_id or not self._bridge.validate_request_id(request_id):
            self._bridge.clear_marker(self.bridge_dir)
            return False

        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)

        if self.behaviour == "timeout":
            return True

        if self.behaviour == "fail":
            self._bridge.write_response(
                request_id=request_id,
                success=False,
                output="",
                error=self.fail_error,
                bridge_dir=self.bridge_dir,
            )
            return True

        if self.response_template is not None:
            output = self.response_template
        else:
            prompt = self._read_prompt(request_id)
            output = f"[FAKE HOST V2] Processed prompt ({len(prompt)} chars)"
        self._bridge.write_response(
            request_id=request_id,
            success=True,
            output=output,
            bridge_dir=self.bridge_dir,
        )
        return True

    def run_forever(self, max_iterations: int | None = None) -> int:
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


def _main(bridge_dir: str, behaviour: str, delay_seconds: float = 0.0) -> None:
    runner = FakeHostRunnerV2(
        bridge_dir=bridge_dir,
        behaviour=behaviour,
        delay_seconds=delay_seconds,
    )
    runner.run_forever()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: fake_host_runner_v2.py <bridge_dir> <behaviour> [delay_seconds]",
            file=sys.stderr,
        )
        sys.exit(2)
    _main(
        bridge_dir=sys.argv[1],
        behaviour=sys.argv[2],
        delay_seconds=float(sys.argv[3]) if len(sys.argv) > 3 else 0.0,
    )


__all__ = ["FakeHostRunnerV2"]
