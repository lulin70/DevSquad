# V4.8.0 devsquad-gate 外部试装证据（T-3 第二段）

> 两段式裁定之第二段：发布后完整 findings 试装（2026-10-22 用户裁定，执行计划 §10）。
> 试装仓：lulin70/zeroclaw；PR #38 `trial/devsquad-gate-stage1`（commit ccb4ba2 触发）。
> wrapper：`@v4.8.0` tag ref + **无 `with:` 覆盖**（行使 `devsquad-version` 默认值 4.8.0）。
> 本段同步覆盖 T-4（失败注入）与 T-5（零 secrets）。第一段证据见
> [STAGE1_mechanical_trial.md](STAGE1_mechanical_trial.md)。

## 结论

findings 面全部验证通过：注入反模式 → BREAK 2 findings → verdict fail → exit 1
（T-4 fail-closed 同场验证）；发布后默认值消费链验证通过（PyPI 4.8.0 + tag v4.8.0，
gate 从 PyPI 安装默认版本）；全程零 secrets（T-5）。两段式试装就此闭环，
R1 验收①（外部试装 e2e）完整达成。

## 配置与触发

| 项 | 值 |
|---|---|
| gate ref | `lulin70/DevSquad/.github/workflows/devsquad-gate.yml@v4.8.0`（发布 tag） |
| devsquad-version | 默认值 4.8.0（验证发布时的意识性 bump 生效于消费链） |
| secrets | 零（wrapper 不传任何 secrets；T-5 负面面） |
| 触发 | PR #38 新 commit（ccb4ba2 `trial: stage 2 — findings face with devsquad 4.8.0`） |
| run | [39738128709](https://github.com/lulin70/zeroclaw/actions/runs/39738128709)（2026-10-22T07:05:33Z → 07:05:52Z，19s） |

## findings 面验证矩阵（run 39738128709）

| 验证面 | 期望 | 实测 | 证据 |
|---|---|---|---|
| T-4 失败注入 | 注入 diff → findings > 0 → verdict fail → exit 1 | ✓ job `gate / gate` 失败于 `Exit by verdict` 步骤（exit 1，非环境崩溃；此前步骤全过） | `gh run view 39738128709 --json jobs` |
| findings 计数 | 注入反模式 → BREAK 2 / total 2 | ✓（命中明细见下节） | 评论 findings 字段 |
| failure_class | `product_failed`（产品发现，非环境阻塞） | ✓ | 评论字段 |
| 评论幂等（跨段） | 编辑既有评论不新增 | ✓ **全程 5 次运行仍 1 条评论**（含第一段二分诊断期 2 次 startup_failure / 2 次 blocked）；本段编辑后 body 的 Run 指向 39738128709 | `gh pr view 38 --json comments`（计数=1） |
| T-5 零 secrets | 无任何 secrets 配置，确定性层独立判定且不谎报 | ✓ 全程无 secrets；findings 判定与披露完整 | wrapper 配置 + run 日志 |
| 发布后消费链 | 默认版本从 PyPI 安装 4.8.0 并接线 findings | ✓ install 步骤 success；4.7.2（无接线版本）下同 diff 为 findings 0（第一段），4.8.0 下为 BREAK 2——接线生效的直接对照 | 两段评论对照 |

## 终态评论原文（run 39738128709）

```markdown
## devsquad-gate 审查结果
<!-- devsquad-gate v1 -->

Run: https://github.com/lulin70/zeroclaw/actions/runs/39738128709

- verdict: fail
- findings: BREAK 2 / VULN 0 / total 2
- failure_class: product_failed
- coverage: 1 reviewed / 0 dropped (by gate)
```

## 注入物与命中精度

注入文件 `dev/trial_gate_injection.py`（PR #38 唯一 diff 文件，原文见 PR #38 diff 与
run 日志）含 3 种反模式：

| 注入 | 模式 | 命中 | 说明 |
|---|---|---|---|
| 遗留标记注释行（marker word 注释） | todo_left | ✓ → BREAK-2 | 单行命中 |
| 调试输出调用（debug print call） | print_debug | ✓ → BREAK-2 | 单行命中 |
| 跨行吞异常形态（except 后换行 pass） | bare_except | ✗ 未计 | 扫描为逐行（`scan_diff_patterns` 对单行跑正则）；跨行形态不匹配单行正则——如实记录不虚报 |

BREAK 2 = todo_left(1) + print_debug(1)，与评论 findings 字段一致（findings 按
(pattern, file) 聚合，见 [diff_pattern_scanner.py](../../../scripts/collaboration/diff_pattern_scanner.py)）。

## 与设计 §5 判定矩阵的对应

| 矩阵行 | 本次两段实测 |
|---|---|
| findings > 0 且命中 fail-on（break）→ fail / exit 1 | ✓ 第二段（run 39738128709） |
| blocked 路径 → exit 2 + blocked_reason 披露 | ✓ 第一段两次（run 39733914040 / 39734515208） |
| findings = 0 → pass / exit 0 | ✓ 第一段（run 39734750597）+ T-2 dogfood（DevSquad PR #60，run 39739886471） |

## 残留与处置

- 试装 PR #38 关闭（证据已采集；注入物不合并入 zeroclaw main，trial 分支删除）
- zeroclaw main wrapper 保留 `@v4.8.0`：zeroclaw 成为常设外部消费仓（休眠仓零成本，后续任意 PR 自然续证）
- 采集命令（2026-10-22 实测）：`gh run view 39738128709 --repo lulin70/zeroclaw --json conclusion,jobs`、`gh pr view 38 --repo lulin70/zeroclaw --json comments`、`gh run list --repo lulin70/zeroclaw --workflow=devsquad-gate.yml`
