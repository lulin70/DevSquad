# Trace 1 — Success Round-Trip（AC-LA-1/2/3）

> **状态**: PENDING（待 TRAE IDE 3.3.95 真实环境采集）
> **场景**: architect agent_type dispatch → marker 7 字段发布 → 监听方按 prompt_file 读取 → v2 timestamp 响应

## 场景描述

验证真实 TRAE IDE 集成终端能按 weiransoft v2.8.4 协议完成一次完整 round-trip：
marker 发布（7 字段）→ 监听方仅凭 marker 路由 → 读取 `request_{id}.prompt` → 写入 `response_{id}.json`（v2 `timestamp` 字段，非 v1 `completed_at`）。

## 触发命令

```bash
export DEVSQUAD_HOST_BRIDGE_VERSION=v2
python3 scripts/cli.py dispatch -t "设计认证系统" -r arch
```

## 证据

### 1. marker 7 字段（AC-LA-1）

```
# cat logs/host_llm_bridge/v2/protocol.v2.marker
<PENDING: 真实 marker JSON，须含 request_id/agent_type/task/request_file/prompt_file/timeout_seconds/timestamp>
```

### 2. 监听方仅凭 marker 路由（AC-LA-2）

```
<PENDING: TRAE IDE 端日志摘录（脱敏）——证明未读完整 request JSON 即决策>
```

### 3. prompt_file 读取 + v2 timestamp 响应（AC-LA-3）

```
# cat logs/host_llm_bridge/v2/response_<id>.json
<PENDING: v2 响应 JSON，须含 timestamp 字段>
```

### 4. 时间戳

| 事件 | 时刻 |
|---|---|
| marker 发布 | PENDING |
| response 写入 | PENDING |
| round-trip 耗时 | PENDING |

## 结果

- [ ] PASS / FAIL（FAIL 附偏差描述）
