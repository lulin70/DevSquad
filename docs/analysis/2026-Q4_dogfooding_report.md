# DevSquad Dogfooding 季度报告

> 本报告由 `scripts/generate_dogfooding_report.py` 生成，勿手改。
> 生成时间：2026-10-22T02:20:27Z | git SHA：ad092ddbae6e
> 生成命令：`scripts/generate_dogfooding_report.py --output docs/analysis/2026-Q4_dogfooding_report.md`

## 指标总表

| 指标 | 值 | 状态 |
|---|---|---|
| 版本一致性 | 82/passed | ok |
| 配置一致性 | 6 passed / 0 failed | ok |
| 测试金字塔 | 9858 tests / 407 files | ok |
| Bandit 静态安全 | HIGH=0 MEDIUM=0 LOW=106 | ok |
| PR 评论协议覆盖 | 2 workflow file(s) | ok |
| TD 债务进出 | total=4 open=2 resolved=2 | ok |
| pip-audit | collected in CI | unavailable |

## 指标详情（每项附复现命令与本次输出摘录）

### 版本一致性

- 值：`82/passed`（exit_code=0）
- 复现命令：`/Users/lin/trae_projects/DevSquad/.venv/bin/python scripts/check_version_consistency.py`


```
  [PASS] TRAE L3 cache (workspace root .trae) skill-manifest.yaml content TRAE L3 cache (workspace root .trae) skill-manifest.yaml content: identical to source OK
  [PASS] TRAE L4 cache (DevSquad .trae) skill-manifest.yaml content TRAE L4 cache (DevSquad .trae) skill-manifest.yaml content: identical to source OK
----------------------------------------------------------------------
Results: 82 passed, 0 skipped, 0 warnings, 0 failed (out of 82 checks)

All 82 required version checks passed (0 optional skipped). Version 4.7.2 is consistent.
```

### 配置一致性

- 值：`6 passed / 0 failed`（exit_code=0）
- 复现命令：`/Users/lin/trae_projects/DevSquad/.venv/bin/python scripts/check_config_consistency.py`
  
  备注：1 warnings (non-blocking)

```
  [PASS] dockerfile_version_match            Dockerfile ARG VERSION = 4.7.2 (matches VERSION file)
  [PASS] chart_appversion_match              Chart.yaml appVersion = 4.7.2 (matches VERSION file)
  [WARN] values_yaml_tag_match               values.yaml image.tag = 4.7.1 but VERSION file = 4.7.2 (may be intentional for deployment pinning)


1 warning(s) (non-blocking). All critical checks passed.
```

### 测试金字塔

- 值：`9858 tests / 407 files`（exit_code=0）
- 复现命令：`/Users/lin/trae_projects/DevSquad/.venv/bin/python scripts/check_test_pyramid.py tests/`
  
  备注：assessment=warning; - integration ratio 14.9% below 15% target (1472/9858 tests) — consider adding integration tests.

```
  external            1      29    0.3%   OK
  unclassified        0       0    0.0%   —
  --------------------------------------------------

  Assessment: warning
    - integration ratio 14.9% below 15% target (1472/9858 tests) — consider adding integration tests.
```

### Bandit 静态安全

- 值：`HIGH=0 MEDIUM=0 LOW=106`（exit_code=0）
- 复现命令：`/Users/lin/trae_projects/DevSquad/.venv/bin/python scripts/check_bandit.py`


```
  total MEDIUM     : 0
  total LOW        : 106
  scan clean       : True
  report           : docs/audits/bandit_latest.json
  scanned_at       : 2026-10-22T02:20:27.223659+00:00
PASS: bandit gate (HIGH=0; MEDIUM within tolerance).
```

### PR 评论协议覆盖

- 值：`2 workflow file(s)`（exit_code=0）
- 复现命令：`static scan .github/workflows/*.yml`
  
  备注：devsquad-gate.yml (missing fields: failed_roles, replay_cache); test.yml

### TD 债务进出

- 值：`total=4 open=2 resolved=2`（exit_code=0）
- 复现命令：`parse docs/TECH_DEBT.md`


### pip-audit

- 值：`collected in CI`（exit_code=-1）
- 复现命令：`CI security job (test.yml) — 本地默认不执行；复现：见 CI 同款命令于报告附录`
  
  备注：本地未执行（--with-pip-audit 未开启）

## 附录：CI 门禁对照（本地命令 ↔ CI 调用点）

| 本地采集 | CI 调用点 |
|---|---|
| `.venv/bin/python scripts/check_version_consistency.py` | test.yml::test (per-Python test job, final consistency gate) |
| `.venv/bin/python scripts/check_config_consistency.py` | test.yml::test (consistency step) |
| `.venv/bin/python scripts/check_test_pyramid.py tests/` | test.yml::test (pyramid gate) |
| `.venv/bin/python scripts/check_bandit.py` | test.yml::security (bandit gate) |
| `static scan .github/workflows/*.yml` | test.yml (the protocol itself) + devsquad-gate.yml (P1-R1) |
| `parse docs/TECH_DEBT.md` | manual registry; referenced by retrospective batches |
| `pip-audit (CI security job)` | test.yml::security pip-audit steps |
