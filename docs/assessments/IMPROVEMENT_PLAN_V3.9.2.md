# DevSquad V3.9.2 改进方案（P0-P3 全量）

> **目标**: 实现硬约束，保障任何项目按生命周期推进，修复 P0-P3 所有问题
> **原则**: 文档先行 → 达成共识 → 按计划推进
> **创建时间**: 2026-06-26

---

## 一、硬约束实现方案（最高优先级）

### HC-1: rbac_fail_closed 默认值修复

**当前状态**: `dispatcher.py:125` 默认 `False`（fail-open），RBAC 异常时放行
**违反约束**: "共识门在关键决策失败时必须安全降级，禁止fail-open直接执行"
**修改方案**:
- 文件: `scripts/collaboration/dispatcher.py:125`
- 改动: `rbac_fail_closed: bool = False` → `rbac_fail_closed: bool = True`
- 影响范围: 仅影响 RBAC 基础设施故障时的行为（正常 RBAC 检查不受影响）
- 测试验证: 现有 `test_dispatch_rbac.py` 17 个测试 + 新增 fail-closed 专项测试
- 风险: 低 — 开发环境默认无 RBAC（`development_mode=True`），仅生产部署受影响

### HC-2: ConsensusEngine 前置介入关键决策点

**当前状态**: ConsensusEngine 仅在 `coordinator.resolve_conflicts()` 后置使用（worker 执行后解决冲突）
**违反约束**: "ConsensusEngine必须作为核心决策机制前置介入所有关键决策点,不可仅作为后置补救措施"
**关键决策点定义**（来自 project_memory）: 发送邮件前、记账前、报告生成前
**修改方案**:
- 在 `dispatch_steps.py` 的 `execute()` 方法中，Step 16（assemble result）之前插入 ConsensusEngine 前置共识检查
- 新增 `scripts/collaboration/consensus_gate.py`：封装前置共识门逻辑
- 当 ConsensusEngine 判断结果为"拒绝"时，result.success = False 并返回
- 当 ConsensusEngine 异常时，安全降级（记录 warning + 标记 needs_review，不直接放行）
- 测试: 新增 `tests/test_consensus_gate.py`

### HC-3: 并行投票架构（已满足，确认即可）

**当前状态**: `async_coordinator.py:516` 使用 `asyncio.gather` 并行执行 workers
**约束**: "三贤者系统必须采用并行投票架构(asyncio.gather)而非串行流水线执行模式"
**结论**: ✅ 已满足。并行 worker 执行 + 并行 LLM 请求均已实现

---

## 二、P0 问题修改方案（立即修复）

### P0-1: rbac_fail_closed 默认值 → 见 HC-1

### P0-2: README.md git clone URL 错误
- 文件: `README.md:428`
- 改动: `weiransoft/devsquad.git` → `lulin70/DevSquad.git`
- 同时检查所有 .md 文件中的 git clone URL

### P0-3: skill-manifest.yaml 测试数冲突
- 文件: `skill-manifest.yaml:10`
- 改动: description 中 "2605 tests passing" → "2703+ tests passing"

### P0-4: ConsensusEngine 前置介入 → 见 HC-2

---

## 三、P1 问题修改方案（短期 1-2 周）

### P1-1: 批量更新版本号 V3.7.2 → V3.9.2

**影响文件清单（28+ 个）**:

| 文件 | 当前版本 | 修改内容 |
|------|---------|---------|
| README.md:74,76 | V3.7.2 | 章节标题+正文版本号 |
| README-CN.md:21 | V3.7.2 | 章节标题 |
| INSTALL.md | V3.6.1/V3.7.2 | 标题+正文 |
| GUIDE.md | V3.7.2/V3.6.0 | 头部+结尾 |
| QUICKSTART.md | V3.7.2 | 全文 |
| COMPARISON.md | V3.7.2 | 全文 |
| EXAMPLES.md | V3.6.1 | 全文 |
| CLAUDE.md:5,15,79,167 | V3.7.2 | 多处 |
| docs/spec/CONSTITUTION.md | V3.7.2 | 全文 |
| docs/spec/SPEC.md | V3.7.2 | 版本+成熟度65%→7.1/10 |
| docs/INDEX.md | V3.6.0 | 版本+日期 |
| docs/USAGE_GUIDE.md | V3.6.0 | 版本 |
| docs/guide/CONFIGURATION.md | V3.6.0 | 版本 |
| docs/guide/QUICK_REFERENCE.md | V3.6.0 | 版本 |
| docs/EXCEPTION_HANDLING_NORMALIZATION_GUIDE.md | V3.6.0 | 版本 |
| docs/PERFORMANCE_MONITORING_INTEGRATION.md | V3.6.0 | 版本 |
| docs/testing/regression_test_strategy.md | v3.6.0 | 版本+测试数1662→2703 |
| helm/devsquad/README.md | V3.6.0 | image.tag |
| config/samples/README.md | V3.6.0 | 版本 |

**执行方式**: 用脚本批量替换，然后逐个文件人工审核上下文

### P1-2: README-JP.md 全面更新

- 从 V3.6.6/V3.7.2 同步到 V3.9.2
- 徽章、章节标题、正文版本号全部更新
- 补充 V3.8（EventBus+Dispatcher Split）和 V3.9（auto LLM fallback等）变更内容

### P1-3: SKILL_JP.md 补齐缺失章节

缺失 7 个章节需从 SKILL.md 翻译补充:
1. Complete Workflow
2. Advanced Features
3. Dispatch Mode Table
4. System Status Query
5. Error Handling
6. Language Rules
7. Meta Iron Rule

### P1-4: README 三语言章节结构对齐

**方案**: 以 README.md（EN）为基准，CN/JP 对齐章节结构
- EN 独有章节（7 Core Roles、Five Capability Domains、Plan C、Configuration）→ 翻译到 CN/JP
- CN/JP 独有章节（使用示例、开发指南、性能基准、致谢）→ 翻译到 EN
- 统一为 17 章结构

### P1-5: CLAUDE.md + SKILL.md 重复修复
- CLAUDE.md:140-141: 删除重复的 SKILL.md 条目
- SKILL.md:65,301: 合并重复的 Architecture Overview 章节

### P1-6: 魔法数字抽取（20+ 处）

**方案**: 创建 `scripts/collaboration/constants.py` 集中管理阈值

| 文件 | 魔法数字 | 常量名 |
|------|---------|--------|
| memory_serializer.py:373 | 70 | MEMORY_QUALITY_THRESHOLD |
| usage_tracker.py:189,191 | 100, 10 | USAGE_HIGH_THRESHOLD, USAGE_MEDIUM_THRESHOLD |
| skill_extractor.py:450-463 | 60,50,50,80 | COMPLETENESS_THRESHOLD, SECURITY_THRESHOLD... |
| ci_feedback_adapter.py:198-206 | 80,60,10 | COVERAGE_HIGH, COVERAGE_MEDIUM, DEBT_THRESHOLD |
| confidence_score.py:27,365 | 0.7, 1000 | CONFIDENCE_THRESHOLD, MAX_TOKENS |
| review_checkers.py:559 | 200 | MAX_LINE_COUNT |
| prompt_assembler.py:502-550 | 15,30,150 | DESC_SHORT/LONG/MAX |

---

## 四、P2 问题修改方案（中期 2-4 周）

### P2-1: 统一归档目录 ✅ 已完成 (2026-06-27)
- 合并 `docs/archive/`（6文件，被 .gitignore 忽略）到 `docs/_archive/` ✅
- 删除 `docs/archive/` 目录和 .gitignore 中的对应条目 ✅
- 删除悬空的 `scripts/collaboration/_archived/README.md` ✅
- 扁平化 `docs/_archive/archive_v2/v2/dev/` 深层嵌套 → `docs/_archive/archive_v2/dev/` ✅
- 验证: 90 单元测试全绿，59 文件重命名，2 处文本修正

### P2-2: 删除 README 双副本 ✅ 已完成 (2026-06-27)
- 保留根目录 `README-CN.md` / `README-JP.md` ✅
- 删除 `docs/i18n/README_CN.md` / `docs/i18n/README_JP.md`（V3.6.6 过时版本，独有内容已在 EN README / SKILL.md / CHANGELOG.md 中以更权威形式存在） ✅
- 同步更新 `README.md` 文档资源表（i18n 路径 → 根路径） ✅
- 顺带修复 `CLAUDE.md` 中过时的测试数（2115+ → 2703+）和版本号（3.7.2 → 3.9.2） ✅

### P2-3: 拆分剩余巨型文件 ✅ 已完成 (2026-06-27)
- `prompt_assembler.py`（1020行）→ facade(216) + base(112) + 4 mixin(152/218/297/213) ✅
- `ue_test_framework.py`（995行）→ facade(170) + base(424) + 4 mixin(89/185/236/53) ✅
- `workflow_engine.py`（988行）→ facade(100) + base(439) + 4 mixin(282/156/145/122) ✅
- 验证: 248 测试全绿（含 5 prompt_assembler + 47 ue_test + 104 workflow_engine 相关），ruff/flake8/mypy 全绿
- 模式: 沿用已验证的 mixin extraction + facade，100% 公共 API 向后兼容

### P2-4: GUIDE 三语言章节对齐 ✅ 已完成 (2026-06-27)
- CN 第12章"关注点增强包" → EN 第12章"Focus Enhancement Pack" / JP 第12章"フォーカス強化パッケージ" ✅
- EN/JP 第15章"Agent Skills Quality Framework" → CN 第16章"Agent 技能质量框架" ✅
- 统一为 17 章 + 3 附录（A→B→C 顺序对齐） ✅
- 三语言章节结构 100% 对齐，版本号 V3.9.2 一致

### P2-5: Contract 测试扩展 ✅ 已完成 (2026-06-27)
- 从 1 个文件（MemoryProvider）扩展到 4 个核心协议 ✅
- `test_cache_provider_contract.py`: 26 测试（LLMCache + NullCacheProvider）
- `test_llm_backend_contract.py`: 22 测试（MockBackend + TraeBackend）
- `test_permission_guard_contract.py`: 16 测试（PLAN/DEFAULT/BYPASS 三级别）
- 验证: 64 新测试 + 61 现有 contract 测试全绿，ruff 0 错误，使用真实组件（非 Mock）

### P2-6: CI 版本号一致性检查 ✅ 已完成 (2026-06-27)
- 新增 `scripts/check_version_consistency.py` 脚本 ✅
- 在 CI lint job 中添加步骤运行此脚本 ✅
- 检查 15 个文件: pyproject.toml / _version.py / skill-manifest.yaml / Dockerfile / helm Chart.yaml (version+appVersion) / CHANGELOG.md / CHANGELOG-CN.md / README.md/CN/JP / SKILL.md / CLAUDE.md / deployment.yaml / COMPARISON.md ✅
- 两种检查模式: `first_match` (CHANGELOG 首条目必须等于当前版本) 和 `contains` (其他文件至少包含一次当前版本，允许历史引用) ✅
- 验证: 15 passed, 0 failed, "All 15 version checks passed. Version 3.9.2 is consistent." ✅

---

## 五、P3 问题修改方案（长期）

### P3-1: 真实 LLM 后端性能基线
- 在有 API key 的环境中运行 `scripts/benchmark_real_llm.py`
- 记录基线数据到 `docs/MATURITY_ASSESSMENT.md`
- 建立 monthly 性能回归机制

### P3-2: REST API 安全增强
- 添加 HTTPS 强制重定向中间件
- 添加速率限制中间件（slowapi 或自定义）

### P3-3: helm chart 版本同步
- `helm/devsquad/Chart.yaml` image.tag: 3.6.0 → 3.9.2
- `helm/devsquad/README.md` 版本号同步

---

## 六、执行计划与校验方法

| 阶段 | 内容 | 校验方法 |
|------|------|---------|
| 阶段1 | P0 全部修复 | pytest 2703+ passed + mypy 0 errors + ruff clean |
| 阶段2 | P1-1 版本号批量更新 | `scripts/check_version_consistency.py` 通过 |
| 阶段3 | P1-2~P1-5 多语言对齐 | 人工审校 + 章节结构对比脚本 |
| 阶段4 | P1-6 魔法数字抽取 | pytest + mypy + ruff 全绿 |
| 阶段5 | P2 归档清理+文件拆分 | pytest + 目录结构检查 |
| 阶段6 | P3 长期改进 | 按需推进 |

---

## 七、风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| rbac_fail_closed=True 破坏现有测试 | 中 | 中 | 先跑测试确认，失败则修复测试（不回退默认值） |
| ConsensusEngine 前置介入增加延迟 | 低 | 低 | 仅在关键决策点触发，非每步触发 |
| 版本号批量替换误伤 | 低 | 低 | 替换前 grep 确认上下文，替换后 diff 审核 |
| 多语言翻译质量 | 中 | 中 | 机器翻译+人工审核 |
