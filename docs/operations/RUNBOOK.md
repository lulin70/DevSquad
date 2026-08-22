# DevSquad Runbook (V4.5.2 / P11.3)

> **Document Version**: V4.5.2
> **Last Updated**: 2026-08-22
> **Audience**: On-call SRE/DevOps engineers
> **Related**: [ALERT_RULES.md](ALERT_RULES.md) (alert definitions) · [ROLLBACK.md](ROLLBACK.md) (V4.5.2 → V4.5.1 rollback)

This runbook provides step-by-step incident response for the 5 V4.5.2 modules plus commonly encountered issues. Each scenario follows the structure: **Alert → Symptoms → Diagnosis → Mitigation → Recovery → Prevention**.

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [V4.5.2 Module Incidents](#v452-module-incidents)
   - [Fuse Skip Triggered](#fuse-skip-triggered)
   - [Perf Regression Blocked](#perf-regression-blocked)
   - [Only Mock Active](#only-mock-active)
   - [Host Bridge Down](#host-bridge-down)
   - [TaskScale Always L](#taskscale-always-l)
   - [OrderChain Always Single](#orderchain-always-single)
   - [Perf Snapshot Missing](#perf-snapshot-missing)
3. [Core Service Incidents](#core-service-incidents)
   - [API Server Won't Start](#api-server-wont-start)
   - [High Error Rate](#high-error-rate)
   - [Cache Miss Storm](#cache-miss-storm)
4. [Operational Procedures](#operational-procedures)
   - [Baseline Reset](#baseline-reset)
   - [Anti-Ghost Re-verification](#anti-ghost-re-verification)
   - [Module Activation Counter Reset](#module-activation-counter-reset)

---

## Quick Reference

| Symptom | First action | Link |
|---------|--------------|------|
| PR pipeline blocked | Check [Perf Regression Blocked](#perf-regression-blocked) | § 2.2 |
| All dispatches return mock | Check [Only Mock Active](#only-mock-active) | § 2.3 |
| HostBridgeBackend broken | Check [Host Bridge Down](#host-bridge-down) | § 2.4 |
| Anti-ghost CI failing | Check [Anti-Ghost Re-verification](#anti-ghost-re-verification) | § 4.2 |
| Perf baseline drift | Check [Baseline Reset](#baseline-reset) | § 4.1 |

---

## V4.5.2 Module Incidents

### Fuse Skip Triggered

**Alert**: `FuseSkipTriggered` (critical)
**Source**: `devsquad_v452_fuse_skips_total` increase > 0
**Module**: BackendPath

#### Symptoms

- Log: `FallbackBackend: fuse blocked <Backend> after N consecutive <reason> failures`
- Metric: `devsquad_v452_backend_failures_total{path="<P>",reason="<R>"}` rate > 0
- User reports: dispatch results look low-quality or are mock-only

#### Diagnosis

```bash
# 1. Check which path/reason was skipped
curl -s http://localhost:8000/metrics | grep fuse_skips_total

# 2. Inspect backend_logs for the actual error
grep -E "FallbackBackend.*failed" /var/log/devsquad/*.log | tail -20

# 3. Verify backend reachability
curl -X POST $OPENAI_API_BASE/chat/completions -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{"model":"gpt-5.5","messages":[{"role":"user","content":"ping"}]}'
```

#### Mitigation (Immediate)

1. **If host bridge fuse skip** — programming AI host is unresponsive. Restart host process and verify bridge files:
   ```bash
   ls -la $BRIDGE_DIR/  # should show protocol.marker
   cat $BRIDGE_DIR/protocol.marker
   ```
2. **If API fuse skip** — usually auth or rate-limit. Rotate API key and verify quotas.
3. **If mock path** — should never be fuse-skipped (always available); investigate if it occurs.

#### Recovery

The fuse state is **per-process** (in-memory in `FallbackBackend._skipped`). Restart the API server to clear it:

```bash
systemctl restart devsquad-api
# or
pkill -f "uvicorn scripts.api_server" && \
  uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 &
```

After restart, the first dispatch call will re-attempt all B→A→C paths and the recovered backend will be re-included.

#### Prevention

- Add per-backend health checks to `/api/v1/health` (planned V4.6).
- Lower `FUSE_SKIP_AFTER_CONSECUTIVE` only with caution (currently 2 — already conservative).
- Implement periodic reachability probe to detect permanent failures faster.

---

### Perf Regression Blocked

**Alert**: `PerfRegressionBlocked` (critical)
**Source**: `devsquad_v452_perf_regression_total{outcome="block"}` increase > 0
**Module**: PerfBaseline

#### Symptoms

- GitHub Actions: `perf-baseline` workflow job fails with `within_threshold=False`
- Log: `Performance regression detected: p95 235.2ms → 280.5ms (+19.3%)`
- Developer blocked from merging PR

#### Diagnosis

```bash
# 1. View the perf snapshot
python3 -c "
import json
with open('docs/reference/PERFORMANCE_BASELINE.json') as f:
    base = json.load(f)
for path, snap in base['snapshots'].items():
    print(f\"{path:15s} p95={snap['p95_ms']:.2f}ms  baseline\")
"

# 2. Check the PR's perf report (uploaded as workflow artifact)
# Download from: https://github.com/<org>/<repo>/actions/runs/<run_id>
```

#### Decision Tree

```
Is the regression expected (e.g., new feature adds work)?
├── Yes → Update baseline (preferred) or accept temporarily
└── No  → Investigate cause before merging
    ├── Did code change affect this path?
    │   ├── Yes → Profile and optimize
    │   └── No  → Check infra: CPU throttling, network, GC pauses
```

#### Mitigation (Accept Regression Temporarily)

Only if the regression is **known and accepted**. Add a `perf-tolerance` PR label and update baseline:

```bash
# Re-run baseline collection locally and commit
python3 scripts/collect_baseline.py
git add docs/reference/PERFORMANCE_BASELINE.json
git commit -m "chore(perf): update baseline after accepted regression (#N)"
```

#### Mitigation (Reject & Investigate)

1. Run profiling locally:
   ```bash
   python3 -m cProfile -o profile.out -m scripts.cli dispatch "task" --backend mock
   python3 -m pstats profile.out
   ```
2. Bisect commits:
   ```bash
   git bisect start HEAD main
   git bisect run python3 -m pytest tests/test_perf_baseline_ci_gate.py
   ```
3. Fix the regression, re-run `perf-baseline.yml`.

#### Recovery

CI will auto-retry after pushing a fix. No manual intervention needed.

#### Prevention

- Run `tests/test_perf_baseline_ci_gate.py` locally before pushing.
- Add explicit perf budgets for hot paths in code review.

---

### Only Mock Active

**Alert**: `OnlyMockActive` (warning)
**Source**: `path=~"B|A"` rate == 0 over 1h, while `path="C"` rate > 0
**Module**: BackendPath

#### Symptoms

- All dispatch responses are prefixed `[MOCK MODE]`
- Users see `[MOCK MODE] AI Assistant Analysis` in dispatch output
- `DEVSQUAD_LLM_BACKEND` env var may be misconfigured

#### Diagnosis

```bash
# 1. Verify env vars
env | grep -E "DEVSQUAD_OPENAI|DEVSQUAD_ANTHROPIC|MOKA|TRAE_ENV"

# 2. Test backend reachability
python3 -c "
from scripts.collaboration.llm_backend import create_backend
b = create_backend('auto')
print('Selected:', type(b).__name__, 'path:', b.path)
print('Available:', b.is_available())
"

# 3. Check API server startup logs
journalctl -u devsquad-api --since "1 hour ago" | grep -i "backend\|path"
```

#### Mitigation

1. **Missing API key** — set the appropriate env var:
   ```bash
   export DEVSQUAD_OPENAI_API_KEY="sk-..."
   systemctl restart devsquad-api
   ```
2. **Wrong backend selected** — explicitly set:
   ```bash
   export DEVSQUAD_LLM_BACKEND="openai"  # or anthropic, moka
   ```
3. **Host bridge misconfigured** — verify `TRAE_ENV` or `CLAUDE_CODE_ENV` is set if intending to use B path.

#### Recovery

After fixing env config, restart API server. Verify with:
```bash
curl http://localhost:8000/api/v1/health | jq '.components'
```

#### Prevention

- Add startup check that warns if `DEVSQUAD_LLM_BACKEND` is unset AND no API keys found.
- Document required env vars in deployment runbook (see `INSTALL.md`).

---

### Host Bridge Down

**Alert**: `HostBridgeDown` (critical)
**Source**: `path="B"` failure rate > 0 for 15m
**Module**: HostLLMBridge

#### Symptoms

- B path requests all fail with `host_timeout`
- `HostLLMBridge` subprocess / file protocol broken
- Programming AI IDE (Trae/ClaudeCode) may have crashed

#### Diagnosis

```bash
# 1. Verify bridge directory
ls -la "$BRIDGE_DIR/" 2>&1 | head -20

# 2. Test bridge protocol manually
python3 -c "
import os
os.environ['TRAE_ENV'] = 'host_llm'
from scripts.collaboration.host_llm_bridge import HostLLMBridge
b = HostLLMBridge(bridge_dir=os.environ.get('BRIDGE_DIR'))
print('Available:', b.is_available())
print('Bridge dir:', b._bridge_dir)
print('Marker exists:', b._marker_path.exists() if hasattr(b, '_marker_path') else 'N/A')
"

# 3. Check host process
ps aux | grep -E "trae|claude-code|host_llm"
```

#### Mitigation

1. **Restart the programming AI host** (Trae IDE / Claude Code):
   - Trae: `File → Restart` or quit & relaunch
   - Claude Code: `Ctrl+R` (reload) or restart CLI
2. **Verify bridge dir is writable**:
   ```bash
   mkdir -p "$BRIDGE_DIR"
   touch "$BRIDGE_DIR/.test" && rm "$BRIDGE_DIR/.test"  # should succeed
   ```
3. **Fallback path will engage automatically** — A → C will serve traffic while B recovers.

#### Recovery

Host bridge is stateless across processes. After restarting host:
```bash
# Clear stale bridge files
rm -f "$BRIDGE_DIR"/request_*.json "$BRIDGE_DIR"/response_*.json

# Reset host environment
unset TRAE_AGENT_PATH  # force re-detection
```

Restart DevSquad API:
```bash
systemctl restart devsquad-api
```

#### Prevention

- Implement host liveness heartbeat in `HostLLMBridge`.
- Add CI smoke test that exercises the bridge protocol.

---

### TaskScale Always L

**Alert**: `TaskScaleAlwaysL` (warning)
**Source**: S/M rate < 5% over 1h
**Module**: TaskScaleGate

#### Symptoms

- Every dispatch escalates to `consensus` orchestrator
- Dispatch latency increased (consensus has 7-role overhead)
- Possible cause: regex hints broken or task patterns changed

#### Diagnosis

```bash
# 1. Check decision distribution
curl -s http://localhost:8000/metrics | grep task_scale_total

# 2. Manually probe TaskScaleGate
python3 -c "
from scripts.collaboration.task_scale_gate import TaskScaleGate
g = TaskScaleGate()
test_tasks = [
    'Fix typo in README',
    'Add 2 modules for OAuth',
    'Implement full project from scratch',
]
for t in test_tasks:
    scale = g.decide(t)
    print(f'{t:50s} → {scale.level} ({scale.signal})')
"
```

#### Mitigation

1. **If heuristic regressed** — compare signals with V4.5.1 known-good:
   ```bash
   git log --oneline scripts/collaboration/task_scale_gate.py | head -5
   ```
2. **Revert if needed** (test thoroughly before merging revert):
   ```bash
   git revert <commit-hash>
   ```
3. **Tune thresholds** — adjust `_L_FILE_HINTS`, `_M_MODULE_HINTS` regex patterns to match new task descriptions.

#### Recovery

After fix, restart API server. Alert auto-clears after 30m of S/M > 5%.

#### Prevention

- Add unit tests for representative task descriptions.
- Snapshot TaskScale decisions to detect drift early.

---

### OrderChain Always Single

**Alert**: `OrderChainAlwaysSingle` (warning)
**Source**: `single_role="true"` rate > 95% over 1h
**Module**: OrderChainDetector

#### Symptoms

- Most dispatches run sequentially instead of multi-agent parallel
- Throughput drops (parallel → sequential)
- Possible cause: heuristic regex over-matches

#### Diagnosis

```bash
python3 -c "
from scripts.collaboration.order_chain_detector import OrderChainDetector
d = OrderChainDetector()
test_tasks = [
    'Refactor this script',
    'Build a complete application',
    'Explain this code',
]
for t in test_tasks:
    decision = d.detect(t)
    print(f'{t:40s} → single={decision.single_role} source={decision.source}')
"
```

#### Mitigation

- If heuristic is over-eager, raise `HEURISTIC_SCORE_THRESHOLD` from 3 → 4.
- If specific pattern triggers too often, add to `_EXCLUSION_PATTERNS`.

#### Recovery

Restart API server after fix.

#### Prevention

- E2E test covering representative task types.
- Track `source` distribution in dashboards (heuristic should be 10-40%, not 95%+).

---

### Perf Snapshot Missing

**Alert**: `PerfBaselineSnapshotMissing` (warning)
**Source**: `absent(devsquad_v452_perf_p95_ms)` for >1h
**Module**: PerfBaseline

#### Symptoms

- No perf snapshots in metrics endpoint
- `docs/reference/PERFORMANCE_BASELINE.json` not being updated

#### Diagnosis

```bash
# 1. Check workflow runs
gh run list --workflow=perf-baseline.yml --limit 5

# 2. Run baseline collection manually
python3 scripts/collect_baseline.py

# 3. Check the JSON file
ls -la docs/reference/PERFORMANCE_BASELINE.json
cat docs/reference/PERFORMANCE_BASELINE.json | jq '.snapshots | keys'
```

#### Mitigation

1. **Workflow not triggering** — check `.github/workflows/perf-baseline.yml` cron syntax.
2. **Mock path unavailable** — verify `DEVSQUAD_LLM_BACKEND=mock` is set in CI.
3. **Permissions issue** — workflow may lack `contents: write` to commit baseline updates.

#### Recovery

Re-run the workflow:
```bash
gh workflow run perf-baseline.yml
```

#### Prevention

- Add health check to verify perf collection ran in last 24h.
- Schedule fallback cron in case main schedule fails.

---

## Core Service Incidents

### API Server Won't Start

**Alert**: API server health check failing / container restart loop
**Module**: Core

#### Quick Diagnosis

```bash
# Check container/service status
systemctl status devsquad-api
docker ps -a | grep devsquad-api

# View startup logs
journalctl -u devsquad-api --since "5 minutes ago"
# or
docker logs devsquad-api --tail 100

# Common errors:
# - "Address already in use" → port 8000 conflict
# - "Permission denied" → file system permissions
# - "ModuleNotFoundError" → venv broken
```

#### Mitigation

1. **Port conflict**:
   ```bash
   lsof -i :8000
   kill <PID>  # or use different port: --port 8001
   ```
2. **Permission denied on auth dir**:
   ```bash
   chown -R devsquad:devsquad /var/lib/devsquad/
   chmod 700 /var/lib/devsquad/auth/
   ```
3. **Module errors**:
   ```bash
   source .venv/bin/activate
   pip install -e .[all]
   ```

---

### High Error Rate

**Alert**: `ErrorRateElevated` (critical, > 5%)
**Module**: Core

#### Diagnosis

```bash
# 1. Breakdown by error type
curl -s http://localhost:8000/metrics | grep devsquad_errors_total

# 2. Recent error logs
journalctl -u devsquad-api --since "10 minutes ago" | grep -E "ERROR|Exception" | tail -20

# 3. Trace a failing dispatch
DEVSQUAD_LOG_LEVEL=DEBUG uvicorn scripts.api_server:app --port 8000
```

#### Mitigation

1. **LLM provider outage** — see [Only Mock Active](#only-mock-active)
2. **Database connection failures** — check DB host, credentials, connection pool
3. **Cache backend (Redis) down** — degrade gracefully, check Redis health

---

### Cache Miss Storm

**Alert**: `CacheHitRateLow` (warning, < 50%)
**Module**: Core

#### Diagnosis

```bash
# Check Redis
redis-cli -h <host> ping
redis-cli -h <host> info stats | grep -E "keyspace|hit_rate"

# Recent cache metrics
curl -s http://localhost:8000/metrics | grep devsquad_cache
```

#### Mitigation

1. **Redis evicted keys** — increase `maxmemory` or shorten TTLs.
2. **Cache backend switched** — verify config: `DEVSQUAD_CACHE_BACKEND=redis`.
3. **Cold restart** — wait for cache to warm up (~30 min).

---

## Operational Procedures

### Baseline Reset

When to reset `docs/reference/PERFORMANCE_BASELINE.json`:
- After a **known** performance improvement (new baseline is better)
- After infrastructure change (new hardware, region, OS)
- Quarterly (housekeeping)

**Procedure**:
```bash
# 1. Capture current baseline as backup
cp docs/reference/PERFORMANCE_BASELINE.json docs/reference/PERFORMANCE_BASELINE.v452.bak

# 2. Collect new baseline
python3 scripts/collect_baseline.py

# 3. Verify the new values
cat docs/reference/PERFORMANCE_BASELINE.json | jq '.snapshots'

# 4. Commit
git add docs/reference/PERFORMANCE_BASELINE.json
git commit -m "chore(perf): refresh baseline after infra upgrade"
git push origin main
```

### Anti-Ghost Re-verification

If `scripts/check_module_activation.py` reports ghost modules:

```bash
# 1. Run the gate
python3 scripts/check_module_activation.py

# 2. For each ghost module, check wiring
grep -rn "task_scale_gate\|order_chain_detector\|host_llm_bridge\|backend_paths\|perf_baseline" \
  scripts/ | head -20

# 3. Verify dispatch pipeline still invokes them
grep -A 2 "TaskScaleGate\(\)" scripts/collaboration/dispatch_pre_steps.py
```

If a module's counter is 0 after a representative dispatch, the wiring is broken. Restore by:
1. Check the import in the relevant pipeline file.
2. Verify the module's `decide()`/`detect()`/`generate()` is called.
3. Re-run `check_module_activation.py`.

### Module Activation Counter Reset

The `_call_counter` is module-level state. To reset:

```bash
# Restart the process (counters reset on import)
systemctl restart devsquad-api

# Or in tests:
python3 -c "
import importlib
import scripts.collaboration.task_scale_gate as m
importlib.reload(m)
print('Counter reset to:', m.get_call_counter())
"
```

---

## 5. P12.1 Module Incidents (V4.5.2 addendum)

### MOKA API Down

**Alert**: MOKA-1 / MOKA-3 (failure rate or consecutive timeouts)
**Symptoms**: All MOKA-backed dispatches fail with `RuntimeError: MokaAIBackend.generate failed after 3 attempts`. Users see fallback to Mock.

**Diagnosis**:
```bash
# 1. Test MOKA connectivity directly
devsquad doctor --provider moka

# 2. Check MOKA API status page
open https://www.moka.ai/status  # or vendor-specific status page

# 3. Verify credentials
echo "MOKA_API_KEY set: $([ -n "$MOKA_API_KEY" ] && echo yes || echo no)"
```

**Mitigation** (5 min):
```bash
# Option A: Switch to alternative backend
devsquad backend set openai
export DEVSQUAD_OPENAI_API_KEY=sk-...

# Option B: Switch to Mock temporarily
devsquad backend set mock

# Option C: Use Anthropic
devsquad backend set anthropic
export DEVSQUAD_ANTHROPIC_API_KEY=sk-ant-...
```

**Recovery**: After MOKA service restoration, restore prior selection:
```bash
devsquad backend set moka
# Confirm:
devsquad doctor --provider moka  # should be reachable
```

**Prevention**:
- Subscribe to MOKA status page updates.
- Set up multi-provider fallback via `devsquad backend set auto-fallback`.

### MOKA API Slow

**Alert**: MOKA-2 (p95 > 15s)
**Symptoms**: Dispatch latency high (60s+). User complaints about slowness.

**Diagnosis**:
```bash
# Check live p95
devsquad metrics | grep perf_p95
```

**Mitigation**:
```bash
# Switch to faster provider
devsquad backend set openai  # typically faster than MOKA for short prompts
```

### GitLab API Down

**Alert**: GL-1 (GitLab failure rate > 20%)
**Symptoms**: `devsquad` cannot post MR comments, transition issues, or submit reviews.

**Diagnosis**:
```bash
# 1. Test token validity
curl -H "PRIVATE-TOKEN: $GITLAB_TOKEN" https://gitlab.com/api/v4/user

# 2. Check GitLab status
open https://status.gitlab.com/
```

**Mitigation**:
- Set `simulation=True` mode (default for dispatch; should not be hitting this).
- If explicitly using `api` mode, temporarily switch to `cli` or `simulation`.

### GitLab Token Expired

**Alert**: GL-2 (auth failure)
**Symptoms**: 401 Unauthorized responses.

**Diagnosis**:
```bash
# Check token scopes
curl -H "PRIVATE-TOKEN: $GITLAB_TOKEN" https://gitlab.com/api/v4/personal_access_tokens/self
```

**Mitigation**:
1. Generate new token: GitLab → User Settings → Access Tokens → `api` scope.
2. Update `.env` or `~/.devsquad/config.yaml`:
   ```bash
   export GITLAB_TOKEN=glpat-...  # new token
   ```

### Invalid Backend Config

**Alert**: BC-1 (invalid backend in user config)
**Symptoms**: `devsquad` falls back to `auto` despite user-configured selection.

**Diagnosis**:
```bash
# Show current effective backend
devsquad backend get

# Validate user config
cat ~/.devsquad/config.yaml
```

**Mitigation**:
```bash
# Fix invalid value
devsquad backend set auto  # reset to safe default
devsquad backend set openai  # or set a valid value
```

### Config Write Fail

**Alert**: BC-2 (config write failure)
**Symptoms**: `devsquad backend set ...` fails with `OSError`.

**Diagnosis**:
```bash
# Check directory permissions
ls -ld ~/.devsquad/

# Check disk space
df -h ~
```

**Mitigation**:
- Fix permissions: `chmod 755 ~/.devsquad`
- Free disk space if needed.
- Fall back to env var: `export DEVSQUAD_LLM_BACKEND=moka`

---

> **Document End**
>
> **Version**: V1.1.0 (V4.5.2 P12.1 addendum)
> **Created**: 2026-08-22 — V4.5.2 P11.3 release
> **Next Update**: When new alert scenarios arise (post-incident review)
