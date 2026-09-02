# V4.5.12 TRAE IDE 3.3.95 真实监听方联调证据

> **协议参考**: [weiransoft/TraeMultiAgentSkill](https://github.com/weiransoft/TraeMultiAgentSkill) v2.8.4（HostLLMBridge v2 协议来源）
> **联调对象**: 本机 TRAE IDE 3.3.95 集成终端（宿主 LLM 监听方）
> **背景**: V4.5.10 PRD §1.1 G-α — v2 adapter + FakeHostRunnerV2 已绿，但真实上游监听方未验证。本目录为 V4.5.12 发布前必做的真实联调证据（PRD AC-LA-1 ~ AC-LA-9）。

## Trace 清单

| # | 文件 | 场景 | 对应 AC |
|---|---|---|---|
| 1 | [trace_1_success_round_trip.md](trace_1_success_round_trip.md) | success round-trip：marker 7 字段 + prompt_file 读取 + v2 timestamp 响应 | AC-LA-1/2/3 |
| 2 | [trace_2_subagent_mapping.md](trace_2_subagent_mapping.md) | subagent_type 映射：architect → search | AC-LA-4 |
| 3 | [trace_3_fuse_threshold.md](trace_3_fuse_threshold.md) | fuse_threshold=2 连续 retriable → B path 永久 skip | AC-LA-5 |
| 4 | [trace_4_cross_version_isolation.md](trace_4_cross_version_isolation.md) | v1/v2 marker 并存 → 仅消费 v2 | AC-LA-7 |
| 5 | [trace_5_resource_bound.md](trace_5_resource_bound.md) | >512KB prompt → MAX_PROMPT_BYTES fail-closed | AC-LA-6 |

## 采集方法（V4.5.13 一键脚本）

```bash
# 预演（不写文件）
python3 scripts/collect_trae_traces.py --all --dry-run

# 采集（建议在 TRAE IDE 3.3.95 集成终端执行，确保宿主监听方在线）
python3 scripts/collect_trae_traces.py --all --wait-seconds 20

# 归档位置
docs/e2e_evidence/V4.5.12_trae_ide_real/collected/trace_N/
  result.json      # status: success | timeout | fail | fail_closed（三态诚实契约）
  v2_snapshot/     # request_*.json / request_*.prompt / response_*.json 快照
```

**诚实契约**：`timeout` 表示采集时真实 TRAE IDE 监听方未消费请求（"有 marker 无监听方"的有效证据），必须如实归档，不得标记 PASS。trace_3（fuse）与 trace_5（资源上限）无需监听方即可完整验证。V4.5.13 新增 `invalid_response` 状态：监听方写入了不可解析为 JSON 信封的响应时，原始字节在解析前即被拷贝到 `collected/trace_N/response_*.raw` 存证。

## V4.5.13 采集实录（2026-09-02）

采集命令：`python3 scripts/collect_trae_traces.py --all --wait-seconds 90`（trace_3 用 `TRAE_ENV=1 --wait-seconds 15` 单独补采）。

监听方形态：按 L-V457-001，监听方 = 宿主 LLM agent 会话（TRAE IDE 3.3.95 内的 agent 读取 marker → 按 prompt 执行 → `HostLLMBridgeV2.write_response` 写回信封）。本轮由真实 agent 会话担任监听方，round-trip 18s~48s。

| # | status | round-trip | 证据 |
|---|---|---|---|
| 1 | success | 48.4s | result.json + response_*.raw + v2_snapshot |
| 2 | success（arch 34.3s / sec 18.1s） | — | 同上 ×2 |
| 3 | success（2×timeout → fuse skip → 第三次 BackendUnavailable） | 2×15s | result.json |
| 4 | success（v1_marker_untouched=true） | 42.3s | result.json + raw |
| 5 | fail_closed（预期，oversize prompt 被拒且无残留） | 即时 | result.json |

**关键更正（推翻 V4.5.13 初版"真实监听方写非 JSON 响应"判断）**：两个 60s 受控探针（项目默认 v2 目录、/var/folders 临时目录各一）均无任何响应文件出现 → **不存在常驻后台 marker 监听方**。此前 fuse 探测期间刷屏的 `JSON decode failed after 3 retries` 是日志伪影：v2 `wait_for_response` 对**不存在**的响应文件也走 3 次重试并告警，缺席文件与坏文件被混为一谈。已在 `host_llm_bridge_v2.py::_safe_read_json` 修复（缺席 → 静默快速返回 None；存在但不可解析才重试+告警），并补 2 条单测（tests/test_host_llm_bridge_v2.py::TestSafeReadJson）。

## 证据要求（AC-LA-9）

每条 trace 必须包含：

1. **场景描述**与触发的完整命令
2. **真实文件协议时间戳**（marker 发布时刻 vs response 写入时刻，round-trip 耗时）
3. **TRAE IDE 端日志摘录**（脱敏后；证明监听方读 marker 路由、按 prompt_file 取 prompt）
4. **结果**（PASS/FAIL + 若 FAIL 的偏差描述）

## 状态

- [x] trace_1 success round-trip（V4.5.13 采集实录 2026-09-02）
- [x] trace_2 subagent mapping（同上）
- [x] trace_3 fuse threshold（同上，TRAE_ENV=1 补采）
- [x] trace_4 cross-version isolation（同上）
- [x] trace_5 resource bound（同上，fail_closed 为预期 PASS）

> 采集完成后勾选，并在 [V4.5.12 PRD](../../prd/V4.5.12_PRD.md) §8 门禁表登记。