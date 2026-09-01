# Trace 2 — Subagent Type Mapping（AC-LA-4）

> **状态**: PENDING（待 TRAE IDE 3.3.95 真实环境采集）
> **场景**: agent_type=architect → 监听方调用 search subagent；其他 agent_type → general_purpose_task

## 场景描述

验证 `HostBridgeBackend.SUBAGENT_TYPE_MAP` 在真实上游调度链路生效：
`resolve_subagent_type("architect") == "search"`，其余角色 → `general_purpose_task`。marker 中的 `agent_type` 是监听方决策的唯一输入。

## 触发命令

```bash
# architect → search
export DEVSQUAD_HOST_BRIDGE_VERSION=v2
python3 scripts/cli.py dispatch -t "架构评审任务" -r arch

# 非 architect → general_purpose_task（对照组）
python3 scripts/cli.py dispatch -t "安全审查任务" -r sec
```

## 证据

### 1. architect → search

```
<PENDING: marker agent_type=architect + TRAE IDE 端 subagent 调度日志（脱敏）>
```

### 2. 非 architect → general_purpose_task

```
<PENDING: 对照组 marker + 调度日志>
```

## 结果

- [ ] PASS / FAIL（FAIL 附偏差描述）
