# DevSquad V4.5.11 Release Notes

> **发布日期**: 2026-08-31
> **版本类型**: PATCH 风格内部硬化迭代（无新用户功能；含 1 项 Breaking）
> **基线**: V4.5.10（commit `34c2dfb` / tag `v4.5.10`）

## 主题

**清理与统一**。关闭 V4.5.10 复盘登记的全部 4 项顺延项（PRD `docs/prd/V4.5.11_PRD.md`）：bridge 日志保留、`_LegacyRiskStoreProxy` 删除、Worker 双路径合并、risks CLI 输出统一。

## 核心交付

| 项 | 内容 |
|---|---|
| PRUNE 保留策略 | v1/v2 bridge 目录在 `create_request` / `write_response` / response 清理后按 mtime 裁剪到 `PRUNE_MAX_FILES`（默认 100）；marker 与 `.tmp` 不计数；`DEVSQUAD_BRIDGE_PRUNE_MAX_FILES` 覆盖，`0` 禁用，非法值 `ValueError` fail-loud |
| Legacy proxy 删除 | `scripts.cli_risks` 移除 `_LegacyRiskStoreProxy` 与 `_RISK_STORE`（V4.5.7 兼容视图）；grep 验证零外部调用者；4 份内部测试迁移为 FileRiskStore 直读 |
| Worker 统一路径 | 新增 `_do_work_async`（async 后端原生 await，sync 后端 run_in_executor 桥接，共享 cache/stream helper）；删除 `_ado_work`；`execute()` 在活动 loop 内改走 `_run_coro_on_thread` 守护线程，消除 `asyncio.run()` 递归崩溃 |
| risks CLI 输出统一 | `RISK_FIELD_ORDER` 规范字段序；`add` 输出与 list/show/export 同构（单对象 JSON，indent=2）；clear 计数改用 `_register_count`（缺文件不再 KeyError） |

## Breaking

1. `from scripts.cli_risks import _RISK_STORE` 抛 `ImportError`。请改用 `FileRiskStore(root=...).transaction("default")` 读写，或 Python API `add_risk()`。

## 门禁与验证

- 新增测试：`tests/unit/test_v4511_bridge_prune.py`（9）、`tests/unit/test_v4511_worker_unified.py`（4）、`tests/unit/test_cli_risks.py` 新增字段序断言
- 迁移测试：`test_cli_risks.py` / `test_cli_risks_api_contract.py` / `test_risk_register_cli.py` / `test_risks_cli_e2e.py` / v458 契约（合计通过）
- 契约保全：`test_v459_worker_async.py` **零修改**通过——aexecute 对 sync 后端保留 V4.5.9 `self.execute` 桥接（子类覆写可观察），async 后端走统一 `_do_work_async`
- 全量回归 `pytest -m "not external"`：9491 passed / 3 failed → 3 处失败根因修复后重跑确认（见复盘 L-V4511-006）

## 已知限制

- 上游 trae v2.8.4 真实监听方联调继续顺延（V4.5.12+）
- SQLite risk store 维持 JSON-only long-term 裁决（重立项条件见 V4.5.10 PRD §6）
