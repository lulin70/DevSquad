# Trace 5 — Resource Bound（AC-LA-6）

> **状态**: PENDING（待 TRAE IDE 3.3.95 真实环境采集）
> **场景**: 512KB 内 prompt 正常 round-trip；>512KB prompt 触发 MAX_PROMPT_BYTES fail-closed

## 场景描述

验证 `MAX_PROMPT_BYTES=512KB` 资源上限在真实场景下的双向行为：
- 边界内（如 400KB）prompt 正常发布 marker 并完成 round-trip（不误报）
- 超限（>512KB）prompt fail-closed：不创建 marker、不留半成品文件

## 触发命令

```bash
export DEVSQUAD_HOST_BRIDGE_VERSION=v2
# 边界内：400KB prompt
python3 scripts/cli.py dispatch -t "$(python3 -c "print('架构评审 ' * 42000)")" -r arch

# 超限：>512KB prompt
python3 scripts/cli.py dispatch -t "$(python3 -c "print('架构评审 ' * 60000)")" -r arch
```

## 证据

### 1. 400KB prompt 正常 round-trip

```
<PENDING: marker + response 正常产出证明>
```

### 2. >512KB prompt fail-closed（无 marker、无半成品）

```
<PENDING: 错误输出 + 目录清单（无新增 request/marker 文件）>
```

## 结果

- [ ] PASS / FAIL（FAIL 附偏差描述）
