# DevSquad Rollback Plan (V4.5.2 / P11.4)

> **Document Version**: V4.5.2
> **Last Updated**: 2026-08-22
> **Audience**: DevOps engineers, release managers
> **Related**: [ALERT_RULES.md](ALERT_RULES.md) · [RUNBOOK.md](RUNBOOK.md) · [OPERATIONS.md](../OPERATIONS.md)

This document defines the rollback strategy from **V4.5.2 → V4.5.1** when critical issues block production use. Rollback is the last resort after [RUNBOOK.md](RUNBOOK.md) mitigation steps fail.

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

> **Document End**
>
> **Version**: V1.1.0 (V4.5.2 P12.1 addendum)
> **Created**: 2026-08-22 — V4.5.2 P11.4 release
> **Next Update**: After first real rollback incident (post-mortem → improvements)