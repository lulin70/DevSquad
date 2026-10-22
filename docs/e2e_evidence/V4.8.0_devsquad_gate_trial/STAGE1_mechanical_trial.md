# V4.8.0 devsquad-gate 外部试装证据（T-3）

> 两段式裁定之第一段：发布前机制性试装（2026-10-22 用户裁定，执行计划 §10）。
> 试装仓：lulin70/zeroclaw（私有、Rust、休眠）；PR #38 `trial/devsquad-gate-stage1`。
> wrapper：`devsquad-version: "4.7.2"` 显式 + gate ref（见下文演进）。
> 第二段（发布后）：4.8.0 默认值 + tag ref 完整 findings 试装（T-3/T-4/T-5 同批）。

## 结论

机制面全部验证通过；试装抓到两个真实缺陷（F-1/F-2），当日修复并入 PR #59。
**试装的最大价值得到证明**：结构防腐测试无法覆盖 workflow_call 真实调用面，
首例外部消费即暴露 QUICKSTART 示例缺陷与私有仓拉取缺陷。

## 缺陷台账

| # | 现象 | 根因 | 修复 | 验证 |
|---|---|---|---|---|
| F-1 | caller 未授予 `permissions: pull-requests: write` 时 run 报 `startup_failure`（无 job 创建） | GitHub 拒绝被调方权限超过调用方 token；QUICKSTART 通道 C 示例转写设计 §2.2 模板时丢失 permissions 块 | QUICKSTART 示例补 permissions 授予 + 失败说明；zeroclaw wrapper 同步修复 | run 39733914040 启动成功（此前 39732040953/39732988326 均 startup_failure） |
| F-2a | 私有仓 diff 拉取 404 → 恒 blocked（fail-closed 行为正确但 pass 路径不可达） | 匿名 curl 无法访问私有仓 PR diff | 第一次修复：认证 curl（Bearer token 走 env） | run 39734515208 仍失败——修复不充分 |
| F-2b | 认证 curl 仍失败 | `github.com/.../N.diff` 302 重定向到 `patch-diff.githubusercontent.com`，curl 跨域剥离 Authorization 头 | 最终修复：REST pulls 端点（`Accept: application/vnd.github.v3.diff`）直返 diff，无跨域重定向 | run 39734750597 成功，verdict pass |

## 机制面验证矩阵（run 39734750597 终态 + 全程）

| 验证面 | 期望 | 实测 | 证据 |
|---|---|---|---|
| workflow_call 触发 | pull_request 事件触发 gate | ✓（4 次触发 4 次运行） | zeroclaw Actions run 列表 |
| 评论协议 v1 | 4 字段 + `<!-- devsquad-gate v1 -->` 锚点 | ✓ verdict/findings/failure_class/coverage 全字段 | PR #38 评论原文（下附） |
| 幂等性 | `--edit-last --create-if-none` 编辑不新增 | ✓ **3 次运行仅 1 条评论**（created 06:26:22，内容随 run 更新） | PR #38 comments 计数=1 |
| fail-closed blocked | 环境故障 → exit 2 + blocked_reason 披露 | ✓（fetch 失败两次均诚实 blocked + 原因） | run 39733914040/39734515208 |
| pass 路径 | findings=0 → exit 0 → job success | ✓（4.7.2 无 diff findings 接线，诚实 0） | run 39734750597 success |
| coverage 口径 | 唯一 `+++ b/` 文件数 | ✓ 1 reviewed（注入文件） | 评论 coverage 字段 |
| T-5 secrets 缺失面 | 零 secrets 配置下确定性层照常判定 | ✓（wrapper 未传任何 secrets，全链路运行） | 全程无 secrets 配置 |

## 终态评论原文（run 39734750597）

```markdown
## devsquad-gate 审查结果
<!-- devsquad-gate v1 -->

Run: https://github.com/lulin70/zeroclaw/actions/runs/39734750597

- verdict: pass
- findings: BREAK 0 / VULN 0 / total 0
- failure_class: n/a
- coverage: 1 reviewed / 0 dropped (by gate)
```

## 二分诊断记录（startup_failure 定位过程）

1. 远程调用（`@main`）startup_failure → 远程 vs caller 语法？
2. 本地副本（同结构）startup_failure → 排除跨仓访问
3. 绝对最小 workflow_call 成功 → 问题在 gate 结构
4. 逐项加回：inputs+with ✓ → **permissions 块失败**（根因 F-1）
5. caller 授予 permissions → 成功

## 残留与第二段计划

- zeroclaw wrapper 暂指 DevSquad `release/v4.8.0-bump`（含 F-2b 修复）；PR #59 合并后切回 `@main`，发布后第二段切 `@v4.8.0` tag + 默认版本
- 试装 PR #38 保持开放（第二段 findings 面车辆；注入物 `dev/trial_gate_injection.py` 含 TODO/print/bare-except，4.8.0 下应产出 BREAK-2 findings → verdict fail → exit 1，即 T-4 同场验证）
- 采集命令（2026-10-22 实测）：`gh pr view 38 --repo lulin70/zeroclaw --json comments`、`gh run list --repo lulin70/zeroclaw --workflow=devsquad-gate.yml`
