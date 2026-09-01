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

## 采集方法（每条 trace 通用）

```bash
# 1. 准备隔离 bridge 目录
export DEVSQUAD_HOST_BRIDGE_VERSION=v2
python3 scripts/cli.py dispatch -t "<任务>" -r arch

# 2. 在 TRAE IDE 3.3.95 集成终端观察
ls -la logs/host_llm_bridge/v2/
cat logs/host_llm_bridge/v2/protocol.v2.marker   # 7 字段
cat logs/host_llm_bridge/v2/response_<id>.json   # v2 timestamp 字段

# 3. 归档本 trace 文件 + 脱敏 TRAE IDE 端日志（移除 API Key 等敏感字段）
```

## 证据要求（AC-LA-9）

每条 trace 必须包含：

1. **场景描述**与触发的完整命令
2. **真实文件协议时间戳**（marker 发布时刻 vs response 写入时刻，round-trip 耗时）
3. **TRAE IDE 端日志摘录**（脱敏后；证明监听方读 marker 路由、按 prompt_file 取 prompt）
4. **结果**（PASS/FAIL + 若 FAIL 的偏差描述）

## 状态

- [ ] trace_1 success round-trip
- [ ] trace_2 subagent mapping
- [ ] trace_3 fuse threshold
- [ ] trace_4 cross-version isolation
- [ ] trace_5 resource bound

> 采集完成后勾选，并在 [V4.5.12 PRD](../../prd/V4.5.12_PRD.md) §8 门禁表登记。