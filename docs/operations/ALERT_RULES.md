# DevSquad Alert Rules (V4.5.2 / P11.2)

> **Document Version**: V4.5.2
> **Last Updated**: 2026-08-22
> **Audience**: SRE, DevOps, on-call engineers
> **Related**: [RUNBOOK.md](RUNBOOK.md) (incident response) · [ROLLBACK.md](ROLLBACK.md) (V4.5.2 → V4.5.1 rollback)

This document defines Prometheus alert rules for the **5 V4.5.2 modules** plus the existing core metrics. Each rule follows SRE best practices: severity, threshold rationale, runbook link, and noise budget.

---

## Table of Contents

1. [Severity Levels](#severity-levels)
2. [Scraping & Recording Rules](#scraping--recording-rules)
3. [V4.5.2 Module Alerts](#v452-module-alerts)
   - [TaskScaleGate](#taskscalegate-alerts)
   - [OrderChainDetector](#orderchaindetector-alerts)
   - [BackendPath B/A/C](#backendpath-bac-alerts)
   - [PerfBaseline](#perfbaseline-alerts)
   - [HostLLMBridge](#hostllmbridge-alerts)
4. [Core Metrics Alerts](#core-metrics-alerts)
5. [Alertmanager Routing](#alertmanager-routing)

---

## 1. Severity Levels

| Severity | Response Time | Notification | Examples |
|----------|---------------|--------------|----------|
| `critical` | 5 min | Page on-call + Slack `#oncall-devsquad` | B path permanently down, fuse skip, p95 regression blocked PR |
| `warning` | 30 min | Slack `#devsquad-ops` | Elevated failure rate, single-reason retries, baseline drift |
| `info` | next day | Slack `#devsquad-metrics` | Module activation counter trending |

**Noise budget**: ≤ 5 alerts per day per service. All rules include `for:` duration to filter transient spikes.

---

## 2. Scraping & Recording Rules

### Scrape config (`prometheus.yml`)

```yaml
scrape_configs:
  - job_name: 'devsquad'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['devsquad-api:8000']
    scrape_interval: 15s
    scrape_timeout: 10s
```

### Recording rules (`devsquad_recording.yml`)

```yaml
groups:
  - name: devsquad_v452_recording
    interval: 30s
    rules:
      # Backend failure rate per path (per-second)
      - record: devsquad:backend_failure_rate:by_path_reason
        expr: |
          sum by (path, reason) (rate(devsquad_v452_backend_failures_total[5m]))

      # Fuse skip events in last 1h
      - record: devsquad:fuse_skips:1h
        expr: |
          sum by (path, reason) (increase(devsquad_v452_fuse_skips_total[1h]))

      # Perf regression count blocked in last 24h
      - record: devsquad:perf_regression_blocks:24h
        expr: |
          sum by (path) (increase(devsquad_v452_perf_regression_total{outcome="block"}[24h]))

      # p95 latency by path (5-min moving average)
      - record: devsquad:perf_p95_ms:5m_avg
        expr: |
          avg_over_time(devsquad_v452_perf_p95_ms[5m])
```

---

## 3. V4.5.2 Module Alerts

### TaskScaleGate Alerts

| ID | Rule | Severity | Threshold | For | Rationale |
|----|------|----------|-----------|-----|-----------|
| TSG-1 | TaskScale always L (consensus overload) | warning | `S/M` rate < 5% over 1h | 30m | Dispatcher always escalating to consensus = role matcher broken or workload inflated |
| TSG-2 | TaskScale always S (under-utilization) | info | `M/L` rate < 1% over 24h | 6h | Possible multi-role capabilities silently disabled (check `roles=` arg or config) |

```yaml
groups:
  - name: devsquad_v452_taskscalegate
    rules:
      - alert: TaskScaleAlwaysL
        expr: |
          sum(rate(devsquad_v452_task_scale_total{level=~"S|M"}[1h]))
            / sum(rate(devsquad_v452_task_scale_total[1h])) < 0.05
        for: 30m
        labels: { severity: warning, module: TaskScaleGate }
        annotations:
          summary: "TaskScaleGate decisions skewed to L (consensus) — possible role matcher regression"
          runbook: "docs/operations/RUNBOOK.md#taskscalegate-always-l"

      - alert: TaskScaleAlwaysS
        expr: |
          sum(rate(devsquad_v452_task_scale_total{level=~"M|L"}[24h]))
            / sum(rate(devsquad_v452_task_scale_total[24h])) < 0.01
        for: 6h
        labels: { severity: info, module: TaskScaleGate }
        annotations:
          summary: "TaskScaleGate never escalates to M/L — multi-role disabled or trivial workload"
```

---

### OrderChainDetector Alerts

| ID | Rule | Severity | Threshold | For | Rationale |
|----|------|----------|-----------|-----|-----------|
| OCD-1 | Heuristic decision rate suspiciously low | warning | `heuristic` source < 1% of decisions over 24h | 6h | Detector may be over-relying on defaults — under-detected strong-order tasks |
| OCD-2 | All decisions forced single-role | warning | `single_role="true"` rate > 95% over 1h | 30m | Multi-agent parallel path appears broken |

```yaml
groups:
  - name: devsquad_v452_orderchaindetector
    rules:
      - alert: OrderChainHeuristicSilent
        expr: |
          sum(rate(devsquad_v452_order_chain_total{source="heuristic"}[24h]))
            / sum(rate(devsquad_v452_order_chain_total[24h])) < 0.01
        for: 6h
        labels: { severity: warning, module: OrderChainDetector }
        annotations:
          summary: "OrderChainDetector heuristic rarely triggers — strong-order tasks may be under-detected"

      - alert: OrderChainAlwaysSingle
        expr: |
          sum(rate(devsquad_v452_order_chain_total{single_role="true"}[1h]))
            / sum(rate(devsquad_v452_order_chain_total[1h])) > 0.95
        for: 30m
        labels: { severity: warning, module: OrderChainDetector }
        annotations:
          summary: "All OrderChainDetector decisions are single-role — multi-agent parallel path suspect"
          runbook: "docs/operations/RUNBOOK.md#orderchain-always-single"
```

---

### BackendPath B/A/C Alerts

| ID | Rule | Severity | Threshold | For | Rationale |
|----|------|----------|-----------|-----|-----------|
| BAC-1 | **Fuse skip triggered** | **critical** | any increase in `devsquad_v452_fuse_skips_total` | 0m | Path permanently disabled — user will not get LLM result from that path |
| BAC-2 | Backend failure rate > 50% on any path | critical | failure_rate > 0.5/s over 5m | 5m | Path is broken or API key invalid |
| BAC-3 | Backend failure rate > 10% sustained | warning | failure_rate > 0.1/s over 15m | 15m | Degraded but recoverable |
| BAC-4 | Only C (mock) path active | warning | `path="B"\|path="A"` rate == 0 over 1h | 1h | Real LLM unreachable — degraded mode |

```yaml
groups:
  - name: devsquad_v452_backendpath
    rules:
      - alert: FuseSkipTriggered
        expr: increase(devsquad_v452_fuse_skips_total[5m]) > 0
        for: 0m
        labels: { severity: critical, module: BackendPath }
        annotations:
          summary: "V4.5.2 fuse skipped a backend path ({{ $labels.path }}) — reason: {{ $labels.reason }}"
          description: "Backend path {{ $labels.path }} permanently disabled after consecutive {{ $labels.reason }} failures. User traffic now falls back to lower-priority paths (B→A→C)."
          runbook: "docs/operations/RUNBOOK.md#fuse-skip-triggered"

      - alert: BackendFailureRateHigh
        expr: |
          sum by (path) (rate(devsquad_v452_backend_failures_total[5m])) > 0.5
        for: 5m
        labels: { severity: critical, module: BackendPath }
        annotations:
          summary: "Backend path {{ $labels.path }} failure rate > 50% over 5m"

      - alert: BackendFailureRateElevated
        expr: |
          sum by (path) (rate(devsquad_v452_backend_failures_total[15m])) > 0.1
        for: 15m
        labels: { severity: warning, module: BackendPath }
        annotations:
          summary: "Backend path {{ $labels.path }} failure rate > 10% over 15m — degraded mode"

      - alert: OnlyMockActive
        expr: |
          sum(rate(devsquad_v452_backend_calls_total{path=~"B|A"}[1h])) == 0
            and sum(rate(devsquad_v452_backend_calls_total[1h])) > 0
        for: 1h
        labels: { severity: warning, module: BackendPath }
        annotations:
          summary: "Only C (mock) backend path active — real LLM unreachable"
          runbook: "docs/operations/RUNBOOK.md#only-mock-active"
```

---

### PerfBaseline Alerts

| ID | Rule | Severity | Threshold | For | Rationale |
|----|------|----------|-----------|-----|-----------|
| PB-1 | **Perf regression PR blocked** | **critical** | any increase in `outcome="block"` | 0m | CI gate tripped — release pipeline stalled |
| PB-2 | p95 latency spike on Mock path | warning | `devsquad_v452_perf_p95_ms{path="mock"}` > +50% baseline | 30m | Mock latency regression |
| PB-3 | p95 latency spike on Host path | warning | `devsquad_v452_perf_p95_ms{path="host"}` > +50% baseline | 30m | Host bridge latency regression |
| PB-4 | PerfBaseline snapshot missing | warning | `absent(devsquad_v452_perf_p95_ms)` for >1h | 1h | Collection script not running |

```yaml
groups:
  - name: devsquad_v452_perfbaseline
    rules:
      - alert: PerfRegressionBlocked
        expr: increase(devsquad_v452_perf_regression_total{outcome="block"}[1h]) > 0
        for: 0m
        labels: { severity: critical, module: PerfBaseline }
        annotations:
          summary: "V4.5.2 perf baseline gate BLOCKED path {{ $labels.path }} — p95 regression > threshold"
          description: "PR pipeline halted. Either accept the regression (update baseline) or investigate the regression cause."
          runbook: "docs/operations/RUNBOOK.md#perf-regression-blocked"

      - alert: PerfMockLatencySpike
        expr: |
          devsquad_v452_perf_p95_ms{path="mock"}
            > on() devsquad:perf_baseline_p95:mock * 1.5
        for: 30m
        labels: { severity: warning, module: PerfBaseline }
        annotations:
          summary: "Mock path p95 latency +50% above baseline"

      - alert: PerfHostLatencySpike
        expr: |
          devsquad_v452_perf_p95_ms{path="host"}
            > on() devsquad:perf_baseline_p95:host * 1.5
        for: 30m
        labels: { severity: warning, module: PerfBaseline }
        annotations:
          summary: "Host bridge path p95 latency +50% above baseline"

      - alert: PerfBaselineSnapshotMissing
        expr: absent(devsquad_v452_perf_p95_ms{path=~"mock|host|api"})
        for: 1h
        labels: { severity: warning, module: PerfBaseline }
        annotations:
          summary: "PerfBaseline snapshots absent for >1h — collection script broken or skipped"
          runbook: "docs/operations/RUNBOOK.md#perf-snapshot-missing"
```

---

### HostLLMBridge Alerts

| ID | Rule | Severity | Threshold | For | Rationale |
|----|------|----------|-----------|-----|-----------|
| HBB-1 | Host timeout rate > 5/min | warning | `host_timeout` reason rate > 0.083/s | 10m | Programming AI host unresponsive |
| HBB-2 | B path 100% failure for >15m | critical | `devsquad_v452_backend_failures_total{path="B"}` rate > 0 for 15m | 15m | Host bridge is dead |

```yaml
groups:
  - name: devsquad_v452_hostbridge
    rules:
      - alert: HostBridgeTimeoutElevated
        expr: |
          sum(rate(devsquad_v452_backend_failures_total{path="B", reason="host_timeout"}[5m]))
            > 0.083
        for: 10m
        labels: { severity: warning, module: HostLLMBridge }
        annotations:
          summary: "HostLLMBridge timeout rate >5/min — programming AI host may be unresponsive"

      - alert: HostBridgeDown
        expr: |
          sum(rate(devsquad_v452_backend_failures_total{path="B"}[5m])) > 0
        for: 15m
        labels: { severity: critical, module: HostLLMBridge }
        annotations:
          summary: "HostLLMBridge (B path) failing 100% for 15m — auto-degraded to A/C"
          runbook: "docs/operations/RUNBOOK.md#host-bridge-down"
```

---

## 4. Core Metrics Alerts

### Existing alerts (unchanged from V4.5.1)

| ID | Rule | Severity | For | Source |
|----|------|----------|-----|--------|
| CORE-1 | Dispatch p95 > 60s | warning | 10m | `devsquad_dispatch_duration_seconds` |
| CORE-2 | Error rate > 5% | critical | 5m | `devsquad_errors_total` |
| CORE-3 | LLM call failure > 30% | warning | 10m | `devsquad_llm_calls_total{success="false"}` |
| CORE-4 | Cache hit rate < 50% | warning | 1h | `devsquad_cache_hits_total` / `devsquad_cache_misses_total` |

### P12.1 Module Alerts (V4.5.2 addendum)

#### MokaAIBackend (P12.1.1)

| ID | Rule | Severity | For | Source | Runbook |
|----|------|----------|-----|--------|---------|
| MOKA-1 | MOKA API failure rate > 30% | warning | 10m | `devsquad_v452_backend_failures_total{path="A",reason=~"moka.*"}` | [RUNBOOK#moka-api-down](#moka-api-down) |
| MOKA-2 | MOKA latency p95 > 15s | warning | 5m | `devsquad_v452_perf_p95_ms{path="A"} > 15000` | [RUNBOOK#moka-api-slow](#moka-api-slow) |
| MOKA-3 | MOKA consecutive timeouts (3+ in 5m) | critical | 5m | `rate(devsquad_v452_backend_failures_total{reason="moka_timeout"}[5m]) >= 0.01` | [RUNBOOK#moka-api-down](#moka-api-down) |

#### GitLabConnector (P12.1.3)

| ID | Rule | Severity | For | Source | Runbook |
|----|------|----------|-----|--------|---------|
| GL-1 | GitLab API failure rate > 20% | warning | 10m | `devsquad_connector_failures_total{connector="gitlab"}` | [RUNBOOK#gitlab-api-down](#gitlab-api-down) |
| GL-2 | GitLab API auth failure | critical | 5m | `devsquad_connector_failures_total{connector="gitlab",reason="auth_failed"}` | [RUNBOOK#gitlab-token-expired](#gitlab-token-expired) |

#### BackendConfig (P12.1.5)

| ID | Rule | Severity | For | Source | Runbook |
|----|------|----------|-----|--------|---------|
| BC-1 | Invalid backend in user config | warning | 1h | filesystem: `~/.devsquad/config.yaml` schema validation | [RUNBOOK#invalid-config](#invalid-backend-config) |
| BC-2 | Config write failure | warning | 10m | log-based: `backend.set` exceptions | [RUNBOOK#config-write-fail](#config-write-fail) |

```yaml
# P12.1 alert rules — append to the recording rules in section 2
groups:
  - name: devsquad_v452_moka
    rules:
      - alert: MokaApiFailureRate
        expr: |
          sum(rate(devsquad_v452_backend_failures_total{path="A",reason=~"moka.*"}[10m]))
            / sum(rate(devsquad_v452_backend_calls_total{path="A"}[10m])) > 0.30
        for: 10m
        labels: { severity: warning, module: moka_backend }
        annotations:
          summary: "MOKA API failure rate > 30%"
          runbook: "docs/operations/RUNBOOK.md#moka-api-down"

      - alert: MokaLatencyHigh
        expr: devsquad_v452_perf_p95_ms{path="A"} > 15000
        for: 5m
        labels: { severity: warning, module: moka_backend }
        annotations:
          summary: "MOKA p95 latency > 15s"
          runbook: "docs/operations/RUNBOOK.md#moka-api-slow"

  - name: devsquad_v452_gitlab
    rules:
      - alert: GitLabApiFailureRate
        expr: |
          sum(rate(devsquad_connector_failures_total{connector="gitlab"}[10m]))
            / sum(rate(devsquad_connector_operations_total{connector="gitlab"}[10m])) > 0.20
        for: 10m
        labels: { severity: warning, module: gitlab_connector }
        annotations:
          summary: "GitLab API failure rate > 20%"
          runbook: "docs/operations/RUNBOOK.md#gitlab-api-down"

      - alert: GitLabAuthFailure
        expr: increase(devsquad_connector_failures_total{connector="gitlab",reason="auth_failed"}[5m]) > 0
        for: 5m
        labels: { severity: critical, module: gitlab_connector }
        annotations:
          summary: "GitLab authentication failure"
          runbook: "docs/operations/RUNBOOK.md#gitlab-token-expired"
```

```yaml
groups:
  - name: devsquad_core
    rules:
      - alert: DispatchSlow
        expr: histogram_quantile(0.95, sum by (le, mode) (rate(devsquad_dispatch_duration_seconds_bucket[10m]))) > 60
        for: 10m
        labels: { severity: warning }
        annotations: { summary: "p95 dispatch latency > 60s" }

      - alert: ErrorRateElevated
        expr: |
          sum(rate(devsquad_errors_total[5m]))
            / sum(rate(devsquad_dispatch_total[5m])) > 0.05
        for: 5m
        labels: { severity: critical }
        annotations: { summary: "Dispatch error rate > 5%" }

      - alert: LLMCallFailures
        expr: |
          sum(rate(devsquad_llm_calls_total{success="false"}[10m]))
            / sum(rate(devsquad_llm_calls_total[10m])) > 0.30
        for: 10m
        labels: { severity: warning }
        annotations: { summary: "LLM call failure rate > 30%" }

      - alert: CacheHitRateLow
        expr: |
          sum(rate(devsquad_cache_hits_total[1h]))
            / (sum(rate(devsquad_cache_hits_total[1h])) + sum(rate(devsquad_cache_misses_total[1h]))) < 0.5
        for: 1h
        labels: { severity: warning }
        annotations: { summary: "Cache hit rate < 50%" }
```

---

## 5. Alertmanager Routing

```yaml
route:
  receiver: 'devsquad-default'
  group_by: ['alertname', 'module']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - matchers: [severity="critical"]
      receiver: 'pagerduty-devsquad'
      group_wait: 10s
      repeat_interval: 1h
    - matchers: [severity="warning"]
      receiver: 'slack-devsquad-ops'
      group_wait: 1m
      repeat_interval: 12h
    - matchers: [severity="info"]
      receiver: 'slack-devsquad-metrics'
      group_wait: 5m
      repeat_interval: 24h

receivers:
  - name: 'pagerduty-devsquad'
    pagerduty_configs: [{ service_key: '<redacted>' }]
  - name: 'slack-devsquad-ops'
    slack_configs: [{ channel: '#devsquad-ops', send_resolved: true }]
  - name: 'slack-devsquad-metrics'
    slack_configs: [{ channel: '#devsquad-metrics', send_resolved: true }]
  - name: 'devsquad-default'
    webhook_configs: [{ url: 'http://devsquad-dashboard:8501/api/alerts' }]
```

---

## Appendix: Metric Naming Reference

All V4.5.2 metrics follow Prometheus naming conventions:

```
devsquad_v452_<module>_<entity>_<unit>[_{outcome}]
```

| Metric | Type | Labels | Unit |
|--------|------|--------|------|
| `devsquad_v452_task_scale_total` | Counter | level, orchestrator | events |
| `devsquad_v452_order_chain_total` | Counter | source, single_role | events |
| `devsquad_v452_backend_calls_total` | Counter | path (B/A/C) | calls |
| `devsquad_v452_backend_failures_total` | Counter | path, reason | failures |
| `devsquad_v452_fuse_skips_total` | Counter | path, reason | skip events |
| `devsquad_v452_perf_p95_ms` | Gauge | path | milliseconds |
| `devsquad_v452_perf_regression_total` | Counter | path, outcome (pass/block) | events |
| `devsquad_v452_perf_latency_ms` | Histogram | path | milliseconds |

---

> **Document End**
>
> **Version**: V1.0.0
> **Created**: 2026-08-22 — V4.5.2 P11.2 release
> **Next Update**: When new V4.6 modules add Prometheus metrics, append a new §3.X section
