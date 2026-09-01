# Trace 4 — Cross-Version Isolation（AC-LA-7）

> **状态**: PENDING（待 TRAE IDE 3.3.95 真实环境采集）
> **场景**: v1 `protocol.marker` 与 v2 `protocol.v2.marker` 并存 → 真实监听方仅消费 v2

## 场景描述

验证 V4.5.10 完全隔离在真实监听方下成立：v1（`logs/host_llm_bridge/v1/`）与 v2（`v2/`）目录并存、双 marker 同时在位时，TRAE IDE 3.3.95 监听方只消费 v2 marker，不读取/迁移/删除 v1 文件。

## 触发命令

```bash
# 预置一条 v1 stale marker（不启动 v1 监听方）
ls logs/host_llm_bridge/v1/protocol.marker

# 发起 v2 请求
export DEVSQUAD_HOST_BRIDGE_VERSION=v2
python3 scripts/cli.py dispatch -t "隔离验证" -r arch
```

## 证据

### 1. v1 marker 全程未被消费/修改

```
<PENDING: 请求前后 v1 目录 mtimes + 内容对比>
```

### 2. v2 正常 round-trip

```
<PENDING: v2 marker 消费 + v2 response>
```

## 结果

- [ ] PASS / FAIL（FAIL 附偏差描述）
