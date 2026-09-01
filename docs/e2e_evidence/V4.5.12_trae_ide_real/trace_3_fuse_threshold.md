# Trace 3 — Fuse Threshold = 2（AC-LA-5）

> **状态**: PENDING（待 TRAE IDE 3.3.95 真实环境采集）
> **场景**: 连续 2 次同因 retriable timeout → B path 永久 skip，后续 generate 直接 BackendUnavailable

## 场景描述

验证 `HostBridgeBackend` 熔断在真实上游反馈下触发：连续 2 次相同原因的 retriable 失败后，B path 被永久跳过，后续调用直接抛 `BackendUnavailable`（不再写 marker）。

## 触发命令

```bash
export DEVSQUAD_HOST_BRIDGE_VERSION=v2
# 停止/阻塞 v2 监听方使请求 timeout，连续触发 2 次
python3 scripts/cli.py dispatch -t "熔断触发 1" -r arch   # 期望 timeout（retriable #1）
python3 scripts/cli.py dispatch -t "熔断触发 2" -r arch   # 期望 timeout（retriable #2 → fuse）
python3 scripts/cli.py dispatch -t "熔断后调用"  -r arch   # 期望立即 BackendUnavailable，无新 marker
```

## 证据

### 1. 前 2 次 timeout（marker 有、response 无）

```
<PENDING: 两次请求的 marker/目录清单 + dispatch 输出>
```

### 2. fuse 后 BackendUnavailable（无新 marker）

```
<PENDING: 第 3 次调用输出 + 目录无新增 marker 证明>
```

## 结果

- [ ] PASS / FAIL（FAIL 附偏差描述）
