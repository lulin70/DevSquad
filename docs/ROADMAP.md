# DevSquad Roadmap

> **文档类型**: 战略演进路线图 (Strategic Roadmap)
> **维护原则**: 活文档 — 每个版本发布时同步更新；P2 学习项随 V4.1.0 PRD 评估结果登记。
> **关联文档**:
> - [V4.1.0_PRD_Matt_Skills_Fusion.md](prd/V4.1.0_PRD_Matt_Skills_Fusion.md) — 28 项借鉴范围（P0/P1/P2）
> - [V4.0.11_Matt_Pocock_Skills_Evaluation.md](audits/V4.0.11_Matt_Pocock_Skills_Evaluation.md) — Matt 21 技能评估
> - [V4.1.0_UIUX_Skills_Evaluation.md](audits/V4.1.0_UIUX_Skills_Evaluation.md) — taste-skill / impeccable UI/UX 评估
> - [ROADMAP_V3.7-V4.0.md](ROADMAP_V3.7-V4.0.md) — V3.7-V4.0 历史路线图

---

## 目录

1. [V4.2+ Roadmap（Matt Pocock 工程理念学习项）](#v42-roadmapmatt-pocock-工程理念学习项)
2. [V4.3+ Roadmap（UI/UX Skills 学习项）](#v43-roadmapuiux-skills-学习项)
3. [已落地条目](#已落地条目)

---

## V4.2+ Roadmap（Matt Pocock 工程理念学习项）

> 来源：V4.1.0 PRD §3.3 P2 学习项（Matt 4 项中 P2-3 git-guardrails 已于 V4.1.0 落地，见 [已落地条目](#已落地条目)）。
> 这些是长期演进参考，不在 V4.1.0 范围内实现，登记于此供后续版本规划。

### P2-1: PrototypeSkill (Matt prototype)

- **ID**: P2-1
- **来源**: Matt Pocock [prototype skill](https://github.com/mattpocock/skills/tree/main/skills/engineering/prototype)
- **学习点**: 快速原型验证能力 — 在投入完整实现前，先产出可运行的最小原型，验证假设
- **目标版本**: V4.2+
- **优先级**: P2
- **落地方式**: 新建 `PrototypeSkill`，支持快速 UI/逻辑原型生成；与现有 `Skillifier` 协调，复用 `MicroTaskPlanner` 的 vertical-slice 模式
- **备注**: 需要与现有 Skillifier 协调，避免与 `intent` skill 职责重叠；需评估是否引入新的 skill 调用模式（model-invoked vs user-invoked）

### P2-2: TeachSkill (Matt teach)

- **ID**: P2-2
- **来源**: Matt Pocock [teach skill](https://github.com/mattpocock/skills/tree/main/skills/engineering/teach)
- **学习点**: DevSquad onboarding 场景 — 引导新用户理解 7 角色协作模型、生命周期阶段、Iron Rules
- **目标版本**: V4.2+
- **优先级**: P2
- **落地方式**: 新建 `TeachSkill`，提供新用户引导流程；推动 `Skillifier` 演进支持教学型 skill；与 `docs/guides/user_onboarding_verification.md` 集成
- **备注**: 区别于 `grilling`（P0-7，one-question-at-a-time 访谈），TeachSkill 是知识传递而非需求采集；需考虑与 `GLOSSARY.md` 术语表联动

### P2-4: pre-commit hooks (Matt setup-pre-commit)

- **ID**: P2-4
- **来源**: Matt Pocock [setup-pre-commit skill](https://github.com/mattpocock/skills/tree/main/skills/engineering/setup-pre-commit)
- **学习点**: pre-commit hooks 集成 — 在 commit 前自动执行 ruff/mypy/pytest 等检查
- **目标版本**: V4.2+
- **优先级**: P2
- **落地方式**: 集成 pre-commit hooks；**版本锁定避免漂移**（Matt 评估中记录的教训：未锁版本导致 hook 版本漂移）；与现有 `.pre-commit-config.yaml` 协调
- **备注**: ⚠️ **关键教训** — 必须使用 `requirements-dev.lock` 锁定 hook 工具版本，避免不同环境间行为漂移；需与 `scripts/check_dependency_lock.py` 集成做一致性校验

---

## V4.3+ Roadmap（UI/UX Skills 学习项）

> 来源：V4.1.0 PRD §3.4 UI/UX P2 学习项（4 项中 P2-UI-4 4pt 网格间距检测可作为 P1 扩展先行落地，其余 3 项登记于此）。
> 这些是 CLI/Dashboard/Skillifier 未来演进的参考，不在 V4.1.0 范围内实现。

### P2-UI-1: CLI 命令词表 (impeccable 23 Commands)

- **ID**: P2-UI-1
- **来源**: [pbakaus/impeccable](https://github.com/pbakaus/impeccable) — 23 Commands 词表
- **学习点**: CLI 命令词表 — impeccable 定义了 23 个分类命令词，作为 CLI 交互的统一词汇框架
- **目标版本**: V4.3+
- **优先级**: P2
- **落地方式**: 作为 CLI 未来演进参考；评估 `scripts/cli.py` / `scripts/cli_dispatch.py` 命令分类是否对齐 23 命令词表；23 个命令按类别（创建/审查/导航/配置等）组织
- **备注**: 当前 DevSquad CLI 已有 dispatch/lifecycle/metrics 等子命令，需评估命令命名一致性；不直接照搬，借鉴分类思路

### P2-UI-2: Live Browser 模式 (impeccable Live Browser)

- **ID**: P2-UI-2
- **来源**: [pbakaus/impeccable](https://github.com/pbakaus/impeccable) — Live Browser 模式
- **学习点**: Live Browser 模式 — impeccable 通过 live browser 实时迭代 UI，边审查边修改
- **目标版本**: V4.3+
- **优先级**: P2
- **落地方式**: 作为 Dashboard 未来演进参考；评估 `scripts/dashboard/` 是否引入实时浏览器迭代模式（Playwright + 热重载）；与 V4.1.0 `UIUXAnalyzer` + `TasteDials` 协同
- **备注**: DevSquad Dashboard 基于 Streamlit，与 impeccable 的 live browser 模式架构不同；借鉴"实时反馈"理念而非照搬实现；需评估对 `tests/e2e/test_dashboard_ui_e2e.py` 的影响

### P2-UI-3: 6 Meta-skills 分层 (taste-skill)

- **ID**: P2-UI-3
- **来源**: [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) — 6 Meta-skills 分层
- **学习点**: Meta-skills 分层 — taste-skill 采用 6 层 meta-skill 架构组织技能
- **目标版本**: V4.3+
- **优先级**: P2
- **落地方式**: 作为 `Skillifier` 演进参考；评估现有 `scripts/collaboration/skillifier.py` 是否引入 meta-skill 分层架构；与 V4.1.0 `standardized_role_template.py` 的 progressive disclosure 协调
- **备注**: DevSquad 已有 `skill_registry.py` + `skill_storage.py` 的扁平注册体系，meta-skill 分层是更高级的组织方式；需评估对 `scripts/collaboration/role_skill_loader.py` 加载逻辑的影响

---

## 已落地条目

> 记录已从 ROADMAP 转为正式实现的 P2 学习项。

### P2-3: git-guardrails (Matt git-guardrails) — ✅ V4.1.0 已落地

- **ID**: P2-3
- **来源**: Matt Pocock [git-guardrails](https://github.com/mattpocock/skills/tree/main/skills/engineering/git-guardrails)
- **学习点**: git 命令分类 — 标记危险 git 操作（force push, reset --hard, clean -f 等）
- **落地版本**: V4.1.0
- **落地方式**: `scripts/collaboration/operation_classifier.py` 新增 `OperationClassifier.classify_git_command(command: str) -> str` 方法，复用现有 ALWAYS_SAFE/NEEDS_REVIEW/FORBIDDEN 三级分类体系
- **分类规则**:
  - FORBIDDEN: `git push --force/-f/--force-with-lease` 到 main/master、`git reset --hard`、`git clean -f/-fd/-fx`、`git branch -D`、`git rebase -i`
  - NEEDS_REVIEW: `git push`（非 force 或到非保护分支）、`git merge`、`git rebase`（非交互）、`git cherry-pick`、`git commit --amend`、`git stash drop`、`git branch -d`
  - ALWAYS_SAFE: `git status`/`log`/`diff`/`show`/`add`/`fetch`/`pull`（非 rebase）/`branch`（列出）/`checkout`（非 orphan）/`stash`（非 drop/pop）
- **测试**: `tests/test_git_guardrails.py`（50+ 测试用例）
- **关联**: [V4.1.0_PRD_Matt_Skills_Fusion.md](prd/V4.1.0_PRD_Matt_Skills_Fusion.md) §3.3

---

> **文档结束**
>
> **版本**: V1.0.0
> **创建日期**: 2026-07-15
> **基线版本**: V4.1.0
> **维护者**: DevSquad Team
> **下次更新**: V4.2 规划启动时
