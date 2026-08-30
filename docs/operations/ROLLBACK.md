# DevSquad Rollback Plan (V4.5.10 / P11.4)

> **Document Version**: V4.5.10
> **Last Updated**: 2026-08-30
> **Audience**: DevOps engineers, release managers
> **Related**: [ALERT_RULES.md](ALERT_RULES.md) · [RUNBOOK.md](RUNBOOK.md) · [OPERATIONS.md](../OPERATIONS.md)

This document defines the rollback strategy when critical issues block production use. Rollback is the last resort after [RUNBOOK.md](RUNBOOK.md) mitigation steps fail.

## V4.5.10 Rollback Paths

### R1 — HostLLMBridge protocol v2 → v1 (no redeploy, first choice)

```bash
# Emergency: force v1 everywhere (highest priority flag)
export DEVSQUAD_V455_DISABLE_HOST_BRIDGE_V2=1
# Or version-pinned rollback
export DEVSQUAD_HOST_BRIDGE_VERSION=v1
```

v1/v2 use fully isolated directories (`logs/host_llm_bridge/v1/` vs `v2/`) and distinct marker filenames; rolling back never loses or duplicates in-flight requests of either protocol.

### R2 — `--async` → sync (no redeploy)

Re-run dispatch without `--async`; explicitly neutralize env with `--no-async` when `DEVSQUAD_USE_ASYNC=1` is set. Sync and async share the same output contract.

### R3 — Full version rollback (last resort)

`git checkout v4.5.9` and reinstall, per the original V4.5.3 → V4.5.2 procedure below.


---

## Table of Contents

1. [Rollback Decision Matrix](#rollback-decision-matrix)
2. [Compatibility Matrix](#compatibility-matrix)
3. [Pre-Rollback Checklist](#pre-rollback-checklist)
4. [Rollback Procedures](#rollback-procedures)
   - [Standard Rollback (≤ 30 min downtime acceptable)](#standard-rollback)
   - [Hot Rollback (zero downtime, blue-green)](#hot-rollback)
   - [Partial Rollback (V4.5.2 modules only)](#partial-rollback)
5. [Post-Rollback Verification](#post-rollback-verification)
6. [Forward-Fix and Re-deploy](#forward-fix-and-re-deploy)
7. [Rollback Drills](#rollback-drills)

---

## Rollback Decision Matrix

| Symptom | Severity | Time-to-Detect | Action | Reference |
|---------|----------|----------------|--------|-----------|
| PR pipeline halted by perf regression | critical | minutes | **Update baseline**, NOT rollback | [RUNBOOK §Perf Regression Blocked](RUNBOOK.md#perf-regression-blocked) |
| Single backend path fuse-skipped | critical | 5-30 min | **Restart process**, NOT rollback | [RUNBOOK §Fuse Skip Triggered](RUNBOOK.md#fuse-skip-triggered) |
| Anti-Ghost CI failing (ghost module) | critical | hours | **Investigate wiring**, may need partial rollback | § 4.3 below |
| Multiple V4.5.2 modules broken in prod | critical | 1-2 hours | **Full rollback** to V4.5.1 | § 4.1 |
| Data corruption / loss | critical | minutes | **Full rollback + data restore** | § 4.1 + DB restore |
| User-visible quality regression | warning | hours | **Monitor**, rollback if > 10% complaints | § 4.3 |

### Decision rule

> **Rollback when**: a V4.5.2-specific change is the root cause AND cannot be mitigated within 1 hour.
>
> **Don't rollback when**: the issue exists in both V4.5.1 and V4.5.2 (rollback won't help) OR the issue is environmental (config, infra, network).

---

## Compatibility Matrix

### V4.5.2 → V4.5.1 module compatibility

| Module | V4.5.1 present? | V4.5.1 behavior if V4.5.2 module disabled | Rollback safety |
|--------|-----------------|------------------------------------------|-----------------|
| **TaskScaleGate** | ✅ Added in V4.5.2 | Dispatch would lose S/M/L pre-routing; defaults to full role pool | ✅ Safe — defaults to V4.5.1 max_roles |
| **OrderChainDetector** | ✅ Added in V4.5.2 | Multi-agent parallel always used (no chain optimization) | ✅ Safe — performance regression only |
| **HostLLMBridge (B path)** | ❌ Not in V4.5.1 | `HostBridgeBackend` doesn't exist; falls back to A → C | ✅ Safe — V4.5.1 uses `TraeBackend` (passthrough) |
| **BackendPath enums** | ✅ Added in V4.5.2 | Resolve order fallback to A → C (no B path) | ✅ Safe — V4.5.1 has no B path |
| **PerfBaseline** | ✅ Added in V4.5.2 | No perf snapshot collection; CI gate skipped | ✅ Safe — CI warning only |
| **ApprovalGate** | ✅ Added in V4.5.1 | Default `approval_callback=None` → auto-approve | ✅ Safe — backward compatible |
| **ConnectorFramework** | ✅ Added in V4.5.1 | `simulation=True` default → no network calls | ✅ Safe — backward compatible |
| **Anti-Ghost counters** | ✅ V4.5.0+ | CI gate `check_module_activation.py` fails open if module absent | ✅ Safe — CI warning |

### Data compatibility

| Data type | V4.5.2 schema | V4.5.1 schema | Migration needed? |
|-----------|---------------|---------------|-------------------|
| `DispatchResult` JSON | Adds `approval_records` (V4.5.1) + `connector_operations` (V4.5.1) + perf fields (V4.5.2) | V4.5.1 ignores unknown fields | ❌ None (downgrade-safe) |
| SQLite history DB | Same schema | Same | ❌ None |
| Audit log | Same format | Same | ❌ None |
| Performance baseline JSON | `v4.5.2` version field | V4.5.1 ignores | ❌ None |
| Cache (Redis) | Same keys | Same | ❌ None |
| Auth/credentials | Same | Same | ❌ None |

**Conclusion**: V4.5.2 → V4.5.1 rollback is **schema-safe** (no destructive migration).

### Configuration compatibility

| Env var | V4.5.2 behavior | V4.5.1 behavior | Notes |
|---------|-----------------|-----------------|-------|
| `DEVSQUAD_LLM_BACKEND=auto-fallback` | B→A→C resolve | V4.5.1: `auto-fallback` unknown, raises `ValueError` | ⚠️ Must switch to `auto` or `fallback` before rolling back |
| `DEVSQUAD_OPENAI_API_KEY` | Detected in A path | Same | ✅ Same |
| `DEVSQUAD_ANTHROPIC_API_KEY` | Detected in A path | Same | ✅ Same |
| `MOKA_API_KEY` | Moka AI endpoint | Same | ✅ Same |
| `TRAE_ENV`, `CLAUDE_CODE_ENV` | Triggers B path | V4.5.1: silently ignored (TraeBackend passthrough) | ⚠️ B path won't activate |

**Pre-rollback env var adjustments**:
```bash
# Change before rollback (if currently set to auto-fallback)
export DEVSQUAD_LLM_BACKEND="fallback"  # or "auto"
```

---

## Pre-Rollback Checklist

Before initiating rollback, confirm:

- [ ] **Issue is V4.5.2-specific**: confirmed via `[RUNBOOK.md](RUNBOOK.md)` diagnosis steps
- [ ] **Mitigation steps attempted**: fuse reset, baseline update, env fix all tried
- [ ] **Time budget exhausted**: > 1 hour since incident start (unless data corruption)
- [ ] **Stakeholders notified**: `#oncall-devsquad` Slack + PagerDuty acknowledged
- [ ] **Backup captured**: current state snapshot before destructive changes
- [ ] **Rollback plan reviewed**: this document read end-to-end
- [ ] **V4.5.1 artifacts available**: Docker image tag, git tag, Helm chart version known

```bash
# Capture diagnostic bundle before rollback
mkdir -p /tmp/devsquad-rollback-$(date +%Y%m%d)
cd /tmp/devsquad-rollback-*/

# 1. Service status
systemctl status devsquad-api > service-status.txt
docker ps -a | grep devsquad > containers.txt

# 2. Recent logs
journalctl -u devsquad-api --since "2 hours ago" > logs.txt

# 3. Metrics snapshot
curl -s http://localhost:8000/metrics > metrics.txt
curl -s http://localhost:8000/api/v1/health > health.json

# 4. Git state
git log --oneline -20 > git-log.txt
git status > git-status.txt
git tag --sort=-creatordate | head -10 > tags.txt

tar czf rollback-bundle-$(date +%Y%m%d-%H%M%S).tar.gz /tmp/devsquad-rollback-*
```

---

## Rollback Procedures

### Standard Rollback

**Downtime**: ≤ 30 minutes
**Use case**: full app rollback when V4.5.2 modules cause unrecoverable issues

#### Option A: Git + Docker (recommended)

```bash
# 1. Identify V4.5.1 tag
V451_TAG="v4.5.1"  # or "4.5.1" depending on your tagging convention
git fetch --tags
git checkout $V451_TAG

# 2. Adjust env vars (see Configuration compatibility)
# Edit .env or k8s configmap

# 3. Rebuild Docker image
docker build --build-arg VERSION=4.5.1 -t devsquad:4.5.1 .

# 4. Stop current container
docker stop devsquad-api
docker rm devsquad-api

# 5. Start V4.5.1 container
docker run -d --name devsquad-api \
  -p 8000:8000 \
  -e DEVSQUAD_LLM_BACKEND=fallback \
  # ... other env vars from .env ...
  devsquad:4.5.1

# 6. Verify
curl http://localhost:8000/api/v1/health | jq '.version'
# Should report "4.5.1"
```

#### Option B: Helm (Kubernetes)

```bash
# 1. Revert chart values
helm repo update
helm rollback devsquad-api 1  # rolls back to previous release

# 2. If specific version needed
helm upgrade --install devsquad-api ./helm/devsquad \
  --set image.tag=4.5.1 \
  --set env.DEVSQUAD_LLM_BACKEND=fallback
```

#### Option C: Systemd

```bash
# 1. Stop service
systemctl stop devsquad-api

# 2. Check out V4.5.1
cd /opt/devsquad
git fetch --tags
git checkout v4.5.1
source .venv/bin/activate
pip install -e .

# 3. Restart
systemctl start devsquad-api

# 4. Verify
systemctl status devsquad-api
```

---

### Hot Rollback

**Downtime**: 0 (zero-downtime blue-green)
**Use case**: production with strict SLO, want to keep V4.5.2 alive until V4.5.1 is verified

#### Procedure (Kubernetes)

```bash
# 1. Deploy V4.5.1 alongside V4.5.2 (different deployment name)
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: devsquad-api-v451
spec:
  replicas: 2
  selector:
    matchLabels:
      app: devsquad
      version: v4.5.1
  template:
    metadata:
      labels:
        app: devsquad
        version: v4.5.1
    spec:
      containers:
      - name: devsquad
        image: devsquad:4.5.1
        env:
        - name: DEVSQUAD_LLM_BACKEND
          value: "fallback"
EOF

# 2. Wait for V4.5.1 pods to be ready
kubectl wait --for=condition=ready pod -l version=v4.5.1 --timeout=5m

# 3. Switch service to V4.5.1 (atomic update)
kubectl patch service devsquad-api -p '{"spec":{"selector":{"version":"v4.5.1"}}}'

# 4. Verify traffic shifted
kubectl logs -l version=v4.5.1 --tail 50
# Look for new requests arriving

# 5. After verification (15+ min), scale down V4.5.2
kubectl scale deployment devsquad-api --replicas=0
# Or delete: kubectl delete deployment devsquad-api
```

#### Procedure (Docker Compose)

```bash
# 1. Add V4.5.1 service to docker-compose.yml
cat >> docker-compose.rollback.yml <<EOF
version: '3.8'
services:
  devsquad-api-v451:
    image: devsquad:4.5.1
    environment:
      DEVSQUAD_LLM_BACKEND: fallback
    ports:
      - "8001:8000"
EOF

# 2. Start V4.5.1 alongside
docker-compose -f docker-compose.rollback.yml up -d

# 3. Verify V4.5.1 health
curl http://localhost:8001/api/v1/health | jq '.version'

# 4. Switch load balancer / reverse proxy
# Update nginx/Caddy config to point to 8001 instead of 8000
nginx -s reload

# 5. After verification, stop V4.5.2
docker stop devsquad-api
```

---

### Partial Rollback

**Use case**: only specific V4.5.2 modules are broken; others work fine

#### Scenario: Only `TaskScaleGate` is broken

```bash
# Disable TaskScaleGate by setting feature flag
export DEVSQUAD_DISABLE_TASK_SCALE_GATE=1
systemctl restart devsquad-api
```

(In V4.5.2, this flag is **not yet implemented** — workaround is to revert `dispatch_pre_steps.py` to V4.5.1 version.)

#### Scenario: Only `PerfBaseline` CI is broken

```bash
# Disable the workflow temporarily
# Edit .github/workflows/perf-baseline.yml:
# Add at top:
#   if: false  # temporary disable

git add .github/workflows/perf-baseline.yml
git commit -m "ci: disable perf-baseline temporarily"
git push
```

The application keeps working; only the PR perf gate is disabled.

#### Scenario: Only B path (HostLLMBridge) is broken

```bash
# Force A → C only (skip B path detection)
unset TRAE_ENV CLAUDE_CODE_ENV TRAE_AGENT_PATH ANTHROPIC_ENV
export DEVSQUAD_LLM_BACKEND=fallback  # or auto with API key set

systemctl restart devsquad-api
```

B path is opt-in via env vars; unsetting them reverts to V4.5.1 behavior (A → C).

---

## Post-Rollback Verification

After rolling back, verify each layer:

```bash
# 1. Version check
curl http://localhost:8000/api/v1/health | jq '.version'
# Expected: "4.5.1"

# 2. Health check
curl http://localhost:8000/api/v1/health | jq '.components'
# Expected: all "healthy"

# 3. Liveness probe
curl -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/ready
# Expected: 200

# 4. Smoke test
python3 -m scripts.cli dispatch "ping test" --backend mock

# 5. Verify V4.5.2 metrics are gone
curl -s http://localhost:8000/metrics | grep devsquad_v452
# Expected: no output (V4.5.1 doesn't have these metrics)

# 6. Verify V4.5.1 metrics still present
curl -s http://localhost:8000/metrics | grep devsquad_dispatch_total
# Expected: metric line

# 7. Run full test suite (if safe)
cd /opt/devsquad
source .venv/bin/activate
python -m pytest tests/test_version.py tests/test_api_security.py -q
```

### Alert verification

```bash
# 1. Silence V4.5.2-specific alerts temporarily
amtool silence add --alertmanager http://alertmanager:9093 \
  --match "module=TaskScaleGate" --duration 4h
amtool silence add --alertmanager http://alertmanager:9093 \
  --match "module=PerfBaseline" --duration 4h
# (Other modules can be silenced similarly)

# 2. Verify alertmanager state
amtool silence query --alertmanager http://alertmanager:9093
```

### Communication

- Post in `#oncall-devsquad` Slack:
  ```
  :rotating_light: ROLLBACK COMPLETE :rotating_light:
  V4.5.2 → V4.5.1 (reason: <one-line root cause>)
  ETA for re-deploy: <estimate>
  Incident channel: <link>
  ```
- Update status page (if applicable)
- Notify stakeholders via email

---

## Forward-Fix and Re-deploy

After rollback, the forward path is:

1. **Root cause analysis** (24-48h):
   - Identify which V4.5.2 module caused the issue
   - Write incident report (post-mortem template in [RUNBOOK §Operational Procedures](RUNBOOK.md#operational-procedures))

2. **Fix branch**:
   ```bash
   git checkout -b fix/v452-<issue>
   # Implement fix
   git commit -m "fix(v452): <description>"
   ```

3. **Re-test in staging**:
   ```bash
   # Deploy V4.5.2-fixed to staging
   helm upgrade devsquad-api-staging ./helm/devsquad \
     --set image.tag=4.5.2-fix1 \
     --namespace staging
   ```

4. **Canary in production** (10% traffic):
   - Deploy V4.5.2-fixed alongside V4.5.1
   - Route 10% of traffic to fixed version
   - Monitor for 24h

5. **Full re-deploy**:
   ```bash
   helm upgrade devsquad-api ./helm/devsquad \
     --set image.tag=4.5.2-fix1
   ```

6. **Update this document** with lessons learned:
   - What triggered the rollback?
   - What could we have detected earlier?
   - What additional safeguards should we add?

---

## Rollback Drills

### Quarterly drill schedule

| Quarter | Drill type | Owner | Duration |
|---------|-----------|-------|----------|
| Q1 | Standard rollback in staging | DevOps | 1h |
| Q2 | Hot rollback (k8s blue-green) | DevOps | 2h |
| Q3 | Partial rollback (feature flag) | DevOps | 30m |
| Q4 | Full disaster recovery | DevOps + SRE | 4h |

### Drill procedure

```bash
# 1. Schedule drill (announce in #devsquad-ops 1 week prior)
# 2. Use staging environment (NEVER drill in prod)
# 3. Deploy "broken" V4.5.2 (e.g., with a deliberately broken module)
# 4. Detect the issue (via alerts / smoke test)
# 5. Execute rollback procedure (timed)
# 6. Verify all checks pass
# 7. Document lessons learned
# 8. Update this runbook
```

### Drill metrics

- **Time-to-Detect (TTD)**: from issue to first alert
- **Time-to-Mitigate (TTM)**: from alert to mitigation
- **Time-to-Rollback (TTR)**: from alert to full V4.5.1 restored
- **RTO target**: 30 min (standard), 0 min (hot)
- **RPO target**: 0 (no data loss expected)

Track these metrics; if any drill exceeds targets, update procedures.

---

## 8. P12.1 Module Rollback (V4.5.2 addendum)

### Why P12.1 Needs a Separate Rollback Path

V4.5.2 P12.1 introduced 5 opt-in modules (MokaAIBackend, GitLabConnector, Doctor, Metrics CLI, BackendConfig). These modules are **all opt-in**: they do not change the default dispatch behavior. Therefore, **partial rollback is the primary path** — users can simply not use them, without rolling back the entire V4.5.2 release.

### P12.1.1 Rollback: Disable MOKA Backend

**Symptoms**: MOKA API errors, fallback to mock degrades dispatch quality.

**Action (no code change required)**:
```bash
# Switch back to default (auto-resolution)
devsquad backend set auto

# Or explicitly use a different provider
devsquad backend set openai  # requires DEVSQUAD_OPENAI_API_KEY
devsquad backend set mock    # for development
```

**Code rollback** (if MokaAIBackend is causing CI failures):
```bash
# Disable explicit MOKA in tests by removing import
# In scripts/collaboration/llm_backend.py: revert the line:
#   "moka": _get_moka_backend(),
# to:
#   "moka": OpenAIBackend,  # legacy alias
```

### P12.1.3 Rollback: Disable GitLabConnector

**Symptoms**: GitLab API errors, token issues, or rate limiting.

**Action (no code change required)**:
- The dispatch pipeline defaults to `simulation=True` for all connectors, so GitLabConnector is **not** invoked unless explicitly enabled.
- If a user explicitly calls `GitLabConnector(simulation=False)`, switch back:
  ```python
  gitlab = GitLabConnector(simulation=True)  # safe default
  ```

### P12.1.4 Rollback: Doctor CLI

**Symptoms**: Doctor CLI crashes or blocks dispatch (it should be a non-blocking diagnostic).

**Action**: Doctor CLI is **read-only** and never touches the dispatch path. To remove:
```bash
# Simply don't call `devsquad doctor`. No code removal needed.
```

### P12.1.5 Rollback: BackendConfig

**Symptoms**: Invalid config blocks dispatch, write failures corrupt user setup.

**Action (no code change required)**:
```bash
# Reset to safe defaults
devsquad backend set auto

# Or delete the config file
rm ~/.devsquad/config.yaml

# Or override via env var (highest priority in resolution order)
export DEVSQUAD_LLM_BACKEND=auto
```

**Code rollback** (if `load_backend_config()` is failing):
```python
# In scripts/collaboration/llm_backend.py: comment out the call to
# resolve_backend() and fall back to os.environ.get("DEVSQUAD_LLM_BACKEND", "auto")
```

### Full P12.1 Rollback (Code-level)

If all 5 P12.1 modules need to be removed at the code level:

```bash
# 1. Revert llm_backend.py to remove explicit MOKA + resolve_backend wiring
git revert <commit-hash>  # or cherry-pick revert

# 2. Remove CLI subcommand registrations from scripts/cli.py
# Delete the metrics / doctor / backend subparser blocks

# 3. Revert check_module_activation.py to verify only 5 modules

# 4. Update CHANGELOG and VERSION_HISTORY to mark P12.1 as deprecated

# 5. Re-run full test suite
python3 -m pytest tests/ -q
```

**Estimated time**: 15-20 minutes (well within RTO of 30 min).

---

## 9. P12.2 Module Rollback (V4.5.3 addendum)

### Why P12.2 Needs a Separate Rollback Path

The 5 V4.5.3 modules (ArtifactStore, DispatchEffect, EffectRegistry, AuditCLI, Worker artifact integration) are **opt-in by default** — Worker integration uses try/except (best-effort), so a bad ArtifactStore write never crashes dispatch. This means P12.2 rollback can be **scoped per-module** without touching the dispatch pipeline.

### P12.2.1 Rollback: Disable ArtifactStore

**Symptoms**: Manifest corruption, atomic rewrite failures, file system permission errors.

**Action (no code change required)**:
```bash
# Stop writing new artifacts (best-effort writes still happen but ignore failures)
export DEVSQUAD_ARTIFACT_STORE_DISABLED=1

# Quarantine existing artifacts (move out of root)
mv artifacts/ artifacts-quarantine-$(date +%Y%m%d)/
```

**Code rollback** (if needed):
```bash
# Revert the 3 commits that introduced ArtifactStore
git revert <commit-1> <commit-2> <commit-3>  # artifact_store.py + tests + worker integration
```

**Verification**:
```bash
python3 scripts/check_module_activation.py
# ArtifactStore_P12.2.1 should show "counter=0 FAIL (ghost)" after revert
# This is EXPECTED behavior — module is intentionally disabled.
```

### P12.2.3 Rollback: Disable DispatchEffect Protocol

**Symptoms**: Effect apply/revert exceptions, EffectOutcome returning errors that break callers.

**Action (no code change required)**:
```python
# In scripts/collaboration/artifact_store.py, comment out the effect registration block:
# try:
#     from scripts.collaboration.dispatch_effect import (
#         EffectContext, WriteFileEffect,
#     )
#     registry = _get_global_registry()
#     ...
# except Exception:
#     pass
```

**Code rollback** (if needed):
```bash
# Revert dispatch_effect.py + effect_registry.py
git revert <commit>
```

### P12.2.4 Rollback: Disable EffectRegistry

**Symptoms**: LIFO stack corruption, thread-safety issues, revert_all() infinite loop.

**Action**: Reuse DispatchEffect rollback (registry is consumed by artifact_store.py only).

### P12.2.5 Rollback: Remove Artifact↔Effect Binding

Same as P12.2.1 (the binding lives inside ArtifactStore.write/delete).

### P12.2.6 Rollback: Disable Audit CLI

**Symptoms**: SHA-256 verify false positives, SQLite DB lock contention, sensitive data leakage in output.

**Action (no code change required)**:
```bash
# Stop running `devsquad audit` — the dispatch audit logger continues writing to SQLite.
# The CLI just becomes unreadable; underlying dispatch_audit.py is unaffected.

# Remove audit subparser from scripts/cli.py (1 commit revert)
git revert <cli-audit-registration-commit>
```

**Code rollback** (if audit subparser also corrupts `cli.py`):
```bash
# Revert scripts/cli.py to remove `from scripts.cli_audit import cmd_audit` + p_audit subparser block
git revert <cli-audit-commit>
```

### Full P12.2 Rollback (Code-level)

If all 5 V4.5.3 modules need to be removed at the code level:

```bash
# 1. Revert 5 commit chain (artifact_store + dispatch_effect + effect_registry + cli_audit + worker)
git revert <commit-1>..<commit-5>

# 2. Revert check_module_activation.py to verify only 8 modules (not 11)
git revert <check-module-activation-v453-commit>

# 3. Update CHANGELOG and VERSION_HISTORY to mark P12.2 as deprecated
# 4. Update SKILL.md / skill-manifest.yaml description (remove V4.5.3 entry)

# 5. Re-run full test suite (expect 8524+ tests instead of 8600+)
python3 -m pytest tests/ -q
```

**Estimated time**: 15-20 minutes (well within RTO of 30 min).

---

## 10. P12.3 Module Rollback (V4.5.4 addendum)

### Module Fiber + Coeffect + Modules CLI 单模块回滚

**触发条件**: 任一 V4.5.4 新模块（ModuleFiber / CoeffectResolver / Modules CLI）单独故障需回滚该模块而非整体 V4.5.4。

**影响范围**:
- ModuleFiber 故障 → 影响所有 14 个已注册模块的 FSM 状态追踪；fallback 行为为 best-effort `_activate_v454_modules()` 跳过，回归到 V4.5.3 直调模式
- CoeffectResolver 故障 → 影响 dispatcher 的 `_coeffect_resolver.resolve_activation_order()` 调用；fallback 为跳过拓扑解析，模块按注册顺序激活
- Modules CLI 故障 → 不影响运行时，仅影响运维可视化（`devsquad modules status|graph|retry`）；fallback 为手工执行

**前置条件**:
- 已确认 V4.5.3 tag 仍可部署
- `_PROVIDER_REGISTRY` 状态已 dump 至 `.devsquad_cache/fiber_state.json`

**回滚步骤**:

```bash
# 1. 标记目标模块为 Failed（保留 registry 元数据以便恢复）
devsquad modules retry --module <MODULE_NAME> --mark-failed --reason "V4.5.4 P12.3 rollback"

# 2. 禁用 V4.5.4 P12.3 特定模块（dispatcher 启动时跳过）
export DEVSQUAD_V454_DISABLE_MODULE_FIBER=1
export DEVSQUAD_V454_DISABLE_COEFFECT=1
# Modules CLI 禁用：
export DEVSQUAD_V454_DISABLE_MODULES_CLI=1

# 3. 重新部署 dispatcher（使用 V4.5.4 但 feature-flag 关闭）
kubectl rollout restart deployment/devsquad-dispatcher -n devsquad
# 或:
systemctl restart devsquad-dispatcher

# 4. 验证 anti-ghost 仍 14/14（fallback 模式下所有模块 representative call 仍可触发）
.venv/bin/python scripts/check_module_activation.py --verbose
# 期望: 14/14 PASS (fallback path)

# 5. 完整回滚（极端情况：V4.5.4 完全不能运行）
git checkout v4.5.3
systemctl restart devsquad-dispatcher
.venv/bin/python -m pytest tests/ -q  # 期望 8943 passed (V4.5.3 + P12.2)
```

**验证清单**:
- [ ] `devsquad modules status` 返回 OK（fallback 模式）
- [ ] `check_module_activation.py` 14/14 PASS
- [ ] `devsquad dispatcher --dry-run` 测试 1 个 mock 任务可正常完成
- [ ] 监控 SC-11/12/13 告警在 5m 内不再触发
- [ ] ArtifactStore 数据保留（V4.5.3 兼容格式）

**Estimated time**: 10-15 分钟（feature-flag 回滚）/ 30-40 分钟（完全回滚到 V4.5.3）。

### 全量 V4.5.4 → V4.5.3 回滚（紧急情况）

**触发条件**: V4.5.4 P12.3 整体不兼容或 anti-ghost 持续 < 14/14。

**回滚步骤**:

```bash
# 1. Revert dispatcher.py 新增 5 kwargs (`enable_fiber`, `enable_coeffect`, 等)
git revert <v454-dispatcher-commit>

# 2. Revert scripts/cli_modules.py + scripts/cli.py modules subparser
rm scripts/cli_modules.py
git revert <v454-cli-modules-commit>

# 3. Revert check_module_activation.py to verify only 11 modules (not 14)
git revert <v454-check-module-activation-commit>

# 4. 保留 scripts/collaboration/module_fiber.py + coeffect.py（不删除，因外部模块可能 import）
#    但 dispatcher 不再调用它们

# 5. Update CHANGELOG and VERSION_HISTORY to mark P12.3 as deprecated
# 6. Update SKILL.md / skill-manifest.yaml description (remove V4.5.4 entry)

# 7. Re-run full test suite (expect 8943 tests instead of 8996+)
.venv/bin/python -m pytest tests/ -q
```

**Estimated time**: 25-35 分钟 (well within RTO of 60 min for full version rollback).

---

> **Document End**
>
> **Version**: V1.3.0 (V4.5.6 P12.4 addendum)
> **Created**: 2026-08-22 — V4.5.2 P11.4 release
> **Updated**: 2026-08-25 — V4.5.6 P12.4 added §11 (per-module + full rollback)
> **Next Update**: After first real rollback incident (post-mortem → improvements)

---

## 11. P12.4 Module Rollback (V4.5.6 addendum)

### P12.4.1 Rollback: Disable HostLLMBridge v2 (回退到 v1)

**触发条件**: V4.5.6 P12.4.1 marker v2 协议不兼容旧监听方。

**回滚步骤**:

```bash
# 1. 关闭 v2 协议开关，回退到 v1
echo "DEVSQUAD_V455_DISABLE_HOST_BRIDGE_V2=1" >> /etc/devsquad/devsquad.env

# 2. 重启 dispatcher
systemctl restart devsquad-dispatcher

# 3. 验证 v1 协议生效
curl http://devsquad-api:8000/metrics | grep host_bridge_protocol_version
# 期望: v1
```

**保留内容**: `scripts/collaboration/host_llm_bridge_v2.py` 文件保留（外部模块可能 import）

**验证清单**:
- [ ] `devsquad host-bridge status` 显示 protocol=v1
- [ ] `check_module_activation.py` 17/17 PASS (V4.5.6 18 - 1 disabled)
- [ ] 旧监听方 marker 格式兼容

**Estimated time**: 5 分钟 (feature-flag 回滚)

---

### P12.4.2 Rollback: Disable DispatcherTransaction

**触发条件**: Transaction 5-state FSM 卡死或 rollback 风暴。

**回滚步骤**:

```bash
# 1. 关闭 transaction 模块（保留模块文件，但 dispatcher 不调用）
echo "DEVSQUAD_V455_DISABLE_TRANSACTION=1" >> /etc/devsquad/devsquad.env

# 2. 重启
systemctl restart devsquad-dispatcher

# 3. 验证
devsquad modules status --module DispatcherTransaction
# 期望: state=Disabled
```

**保留内容**: `scripts/collaboration/dispatcher_transaction.py` 文件保留

**验证清单**:
- [ ] 17/17 anti-ghost (1 disabled)
- [ ] dispatch 回到 V4.5.4 行为（无事务边界）
- [ ] rollback metric 不再增加

**Estimated time**: 5 分钟

---

### P12.4.3 Rollback: Disable IntentWorkflowMapper

**触发条件**: IntentMapper resolve 失败率高，fallback 到 "dev" 后下游仍 fail。

**回滚步骤**:

```bash
echo "DEVSQUAD_V455_DISABLE_INTENT=1" >> /etc/devsquad/devsquad.env
systemctl restart devsquad-dispatcher
devsquad modules status --module IntentWorkflowMapper
```

**保留内容**: `scripts/collaboration/dispatcher_intent_mapper.py` 保留（hardcoded DEFAULT_WORKFLOWS 数据用于 reference）

**Estimated time**: 5 分钟

---

### P12.4.4 Rollback: Disable DispatchLoopController

**触发条件**: LoopController 频繁熔断阻断正常 dispatch。

**回滚步骤**:

```bash
echo "DEVSQUAD_V455_DISABLE_LOOP=1" >> /etc/devsquad/devsquad.env
systemctl restart devsquad-dispatcher
devsquad modules status --module DispatchLoopController
```

**保留内容**: `scripts/collaboration/dispatcher_loop_controller.py` 保留

**Estimated time**: 5 分钟

---

### 全量 V4.5.6 → V4.5.4 回滚（紧急情况）

**触发条件**: V4.5.6 P12.4 整体不兼容或 anti-ghost 持续 < 18/18。

**回滚步骤**:

```bash
# 1. Revert dispatcher.py 新增 4 kwargs (`enable_host_bridge_v2`, `enable_transaction`, 等)
git revert <v455-dispatcher-commit>

# 2. Revert check_module_activation.py 到 verify 14 个模块 (not 18)
git revert <v455-check-module-activation-commit>

# 3. Revert VERSION + CHANGELOG (4.5.6 → 4.5.4)
git revert <v455-version-sync-commit>

# 4. 保留 scripts/collaboration/host_llm_bridge_v2.py + dispatcher_transaction.py +
#    dispatcher_intent_mapper.py + dispatcher_loop_controller.py（不删除，因外部模块可能 import）
#    但 dispatcher 不再调用它们

# 5. Update CHANGELOG and VERSION_HISTORY to mark P12.4 as deprecated
# 6. Update SKILL.md / skill-manifest.yaml description (remove V4.5.6 entry)

# 7. Re-run full test suite (expect 8996 tests instead of 9048)
.venv/bin/python -m pytest tests/ -q
```

**Estimated time**: 25-35 分钟 (well within RTO of 60 min for full version rollback).