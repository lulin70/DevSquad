# DevSquad V4.5.14 Release Notes

> **发布日期**: 2026-09-02　**Tag**: `v4.5.14`　**基线**: v4.5.13 (`156cac9`)

## 定位

PATCH 版本（SemVer 合规）：无新功能、无 Breaking。关闭 V4.5.13+ backlog
最后一项 —— "TRAE 监听方在线时跑采集脚本归档真实 PASS"，并修复采集过程中
发现的两处缺陷。

## 交付内容

### 1. 真实监听方 trace 归档（5/5）

- trace_1 success round-trip：48.4s
- trace_2 subagent mapping：architect 34.3s / security 18.1s
- trace_3 fuse threshold：2×timeout → fuse skip → 第三次 `BackendUnavailable`（success）
- trace_4 cross-version isolation：success，`v1_marker_untouched=true`
- trace_5 resource bound：`fail_closed`（预期 PASS）

监听方形态（与 L-V457-001 一致）：监听方 = 宿主 LLM agent 会话——读取
marker → 按 prompt_file 执行任务 → `HostLLMBridgeV2.write_response` 写回
响应信封。每条 trace 均含 `result.json`、`response_*.raw`（原始字节捕获）
与 `v2_snapshot/`，归档于
`docs/e2e_evidence/V4.5.12_trae_ide_real/collected/trace_N/`。

### 2. trace_3 诚实状态修复

`create_backend("host")` 在 `TRAE_ENV` 被剥离的环境（如 TRAE 集成终端的
sandbox 包装）会抛 `BackendUnavailable`，此前导致未捕获 traceback 崩溃
（违反诚实状态契约）。现转为诚实 `fail` 状态并附错误信息；fuse 探测同时
透传 `--wait-seconds`（原先固定 600s，一次完整采集会挂 20 分钟）。

### 3. `_safe_read_json` 缺席文件日志伪影修复（关键更正）

v2 `wait_for_response` 对**不存在**的响应文件也会执行 3 次重试并打出
`JSON decode failed after 3 retries` 警告。修复：缺席文件 = 正常轮询，
立即返回 `None` 不告警；仅"存在但不可解析"才重试 + 告警。

**更正 V4.5.13 finding**：两个 60s 受控探针（项目默认 v2 目录、/var/folders
临时目录各一）均无任何响应文件出现，证明不存在常驻后台 marker 监听方。
V4.5.13 记录的"真实监听方写非 JSON 响应"系上述日志伪影被误读为证据，
已在证据 README 登记更正。

## 门禁

- ruff：0 error（改动 3 文件）
- 测试：新增 2（`TestSafeReadJson`：缺席静默快速返回 / 坏 JSON 重试后告警）；
  `tests/test_host_llm_bridge_v2.py` + `tests/unit/test_v4513_trace_collector.py`
  合计 43 passed
- 版本一致性：`check_version_consistency.py` 4.5.14 全绿
  （含工作区缓存 SKILL.md / skill-manifest.yaml 字节级一致）

## 升级与回滚

无 API/配置变更；从 v4.5.13 直接拉取即可。如需回滚，`git checkout v4.5.13`。
