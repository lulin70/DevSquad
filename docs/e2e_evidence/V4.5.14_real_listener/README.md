# V4.5.14 Real-Listener Trace Evidence

> **状态**: V4.5.14 archived 5/5 traces in [V4.5.12_trae_ide_real/](../V4.5.12_trae_ide_real/)

## Traces

| # | Status | Duration | Evidence |
|---|--------|----------|----------|
| 1 | success (architect) | 48.4s | [../V4.5.12_trae_ide_real/collected/trace_1/](../V4.5.12_trae_ide_real/collected/trace_1/) |
| 2 | success (architect 34.3s / security 18.1s) | — | [../V4.5.12_trae_ide_real/collected/trace_2/](../V4.5.12_trae_ide_real/collected/trace_2/) |
| 3 | success (2×timeout → fuse skip → 3rd BackendUnavailable) | 2×15s | [../V4.5.12_trae_ide_real/collected/trace_3/](../V4.5.12_trae_ide_real/collected/trace_3/) |
| 4 | success (v1_marker_untouched=true) | 42.3s | [../V4.5.12_trae_ide_real/collected/trace_4/](../V4.5.12_trae_ide_real/collected/trace_4/) |
| 5 | fail_closed (oversize prompt, no artifacts left) | instant | [../V4.5.12_trae_ide_real/collected/trace_5/](../V4.5.12_trae_ide_real/collected/trace_5/) |

## Listener

Real TRAE IDE 3.3.95 agent session reading `protocol.v2.marker`, executing the
promoted task via the prompt file, and writing the response envelope via
`HostLLMBridgeV2.write_response`.

## Honest-Status Fixes (V4.5.14)

- `scripts/collect_trae_traces.py::trace_3`: `BackendUnavailable` → honest `fail`
- `scripts/collaboration/host_llm_bridge_v2.py::_safe_read_json`: absent file → None immediately (no retry, no warning)