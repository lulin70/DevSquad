# V4.9.0 P2-W4 feature gate — e2e evidence (anchor ⑩)

Three real dispatch runs through the production pipeline (`MultiAgentDispatcher.dispatch`,
mock LLM backend, single-role task). The feature-gate side is fully real: checklist
anchoring (pre-steps), live command execution (Step 23.5), C19 terminal recompute
(Step 24), and the SHA-256 audit chain (`DispatchAuditLogger`).

Design: [V4.9.0_W4_feature-gate_DESIGN.md](../../planning/V4.9.0_W4_feature-gate_DESIGN.md) §7 ⑩.

## Runs

| Run | Gate | Checklist | Result |
|---|---|---|---|
| `run_disabled_report.md` | off (default constructor) | — | `success=true`, `failure_class=none`, **zero feature-gate trace** in details / Markdown / audit event (negative test ①, 4.8.x behavior) |
| `run_pass_report.md` | on | 3 items: 2 × `python -c "import sys; sys.exit(0)"` + 1 waived (`exit(1)` + `waive_reason`) | `success=true`, verdict `pass`, matrix `2 pass · 1 waived`, waived reason rendered in the Markdown matrix (④), audit `dispatch_end` carries the matrix + dual hashes |
| `run_tamper_report.md` | on | 1 item, rewritten **between anchoring and Step 23.5** (via `post_dispatch.execution_completed` event handler) | `success=false`, verdict `fail`, violation `checklist_tampered` (anchored≠computed hash), `failure_class=product_failed` (⑦ C19 recompute), exit code 1, audit carries differing dual hashes |

## Checklist fixture (schema v1)

```json
{
  "schema_version": 1,
  "items": [
    {
      "id": "AC-1",
      "description": "login endpoint returns 200 for valid credentials",
      "verify": { "kind": "command", "command": "<python> -c 'import sys; sys.exit(0)'" }
    },
    {
      "id": "AC-3",
      "description": "manual UI walkthrough documented",
      "verify": { "kind": "command", "command": "<python> -c 'import sys; sys.exit(1)'" },
      "waive_reason": "UI not yet automated; manual sign-off attached"
    }
  ]
}
```

## Reproduce

```bash
# enabled run (checklist at .devsquad/acceptance_checklist.json)
.venv/bin/python scripts/cli.py dispatch "Verify acceptance criteria" \
  --backend mock  # requires feature_gate.enabled: true in .devsquad.yaml
```

Or via the Python API:

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher(
    enable_feature_gate=True,
    feature_gate_checklist=".devsquad/acceptance_checklist.json",
)
result = disp.dispatch("Verify acceptance criteria")
print(result.details["feature_gate"]["verdict"])
```

Regression coverage for all three scenarios lives in
`tests/integration/test_feature_gate_pipeline.py` (①②⑦), `tests/unit/test_feature_gate.py`
(③④⑤ + CLI injection), `tests/test_dispatch_audit.py` (⑥), `tests/test_dispatcher_mixins.py`
(⑧), `tests/unit/test_config_manager.py` (⑨).
