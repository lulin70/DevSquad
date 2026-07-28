# DevSquad LLM vs Mock 输出质量差距衡量规划

> **文档类型**: 规划文档（待办）— V4.4.0 P1 候选
> **创建日期**: 2026-07-28
> **基线版本**: V4.3.1 (commit 已发布)
> **目标版本**: V4.4.0 P1
> **维护者**: DevSquad Team
> **状态**: 规划中（待用户确认后纳入 V4.4.0 ROADMAP）
> **7-Role 共识**: 7/7 通过（2026-07-28）
> **关联文档**:
> - [V4.3.0_ROADMAP.md](./V4.3.0_ROADMAP.md) — V4.3.0 推进方案
> - [benchmark_real_llm.py](../../scripts/benchmark_real_llm.py) — 已有性能基准脚本
> - [test_real_llm_smoke.py](../../tests/smoke/test_real_llm_smoke.py) — 已有冒烟测试

---

## 1. 背景与动机

### 1.1 问题陈述

DevSquad 默认使用 MockBackend（无需 API key），用户可选启用真实 LLM 后端（OpenAI/Anthropic/MOKA AI）。但**至今未量化衡量 LLM 模式 vs Mock 模式的输出质量差距**，导致以下问题无法回答：

| 问题 | 影响方 |
|------|--------|
| DevSquad 是否真的需要 LLM API Key？ | 产品定位、Onboarding 体验 |
| Mock 模式输出能否满足真实工程任务需求？ | 免费用户体验 |
| LLM 模式相比 Mock 提升了多少？ | Pro 版商业价值论证 |
| 哪些任务类型 Mock 模式已足够，哪些必须用 LLM？ | 任务路由策略 |
| LLM 模式的延迟/成本代价是否值得？ | 用户决策依据 |

### 1.2 现状盘点（2026-07-28 调研）

| 资产 | 路径 | 现状 | 缺口 |
|------|------|------|------|
| MockBackend | `scripts/collaboration/llm_backend.py:84-116` | 统一模板，无 role-specific 差异化 | 7 角色共用同一 Mock 输出 |
| PerformanceMonitor | `scripts/collaboration/performance_monitor.py` | 收集延迟/吞吐量/CPU/内存 | 不区分 LLM vs Mock 模式 |
| BenchmarkRegressionChecker | `scripts/collaboration/benchmark_regression_checker.py` | V4.3.1 新增，单 backend 回归检测 | 不支持双 backend 对比 |
| ConfidenceScorer | `scripts/collaboration/confidence_score.py` | 5-factor 评分（completeness/certainty/specificity/consistency/model quality） | 未用于 LLM vs Mock 对比 |
| FiveAxisConsensusEngine.evaluate() | `scripts/collaboration/five_axis_consensus.py` | V4.3.0 新增 heuristic 5 轴评估器 | 未用于 LLM vs Mock 对比 |
| benchmark_real_llm.py | `scripts/benchmark_real_llm.py` | V4.3.1 新增，测延迟/吞吐量/成功率 | **不测输出质量** |
| test_real_llm_smoke.py | `tests/smoke/test_real_llm_smoke.py` | V4.3.1 新增，端到端冒烟测试 | 不评估输出质量 |
| LLM vs Mock 对比文档 | — | **不存在** | 需新建本规划文档 |

### 1.3 为什么现在做

- V4.3.1 已发布（2026-07-25），BenchmarkRegressionChecker 已落地
- 已有性能基准脚本（benchmark_real_llm.py）但缺质量基准
- 用户明确要求衡量 LLM vs Mock 差距（2026-07-28 对话）
- V4.4.0 ROADMAP 待制定，正好纳入此项

---

## 2. 目标与非目标

### 2.1 目标（SMART）

| # | 目标 | 衡量标准 |
|---|------|---------|
| G1 | 量化 LLM vs Mock 在 10 个典型工程任务上的输出质量差距 | 5 维度评分（completeness/certainty/specificity/consistency/model quality）+ 5 轴评估（correctness/readability/architecture/security/performance） |
| G2 | 识别 Mock 模式已足够 vs 必须用 LLM 的任务类型 | 任务分类矩阵（任务类型 × 推荐模式） |
| G3 | 提供 LLM 模式 vs Mock 模式的延迟/成本/质量三维权衡数据 | 性能数据复用 benchmark_real_llm.py + 质量数据新增 |
| G4 | 输出可复现的基准任务集 + 评分脚本 | `data/quality_benchmark/` 任务集 + `scripts/benchmark_quality.py` 脚本 |
| G5 | 生成决策报告，回答"DevSquad 是否需要 LLM"的核心问题 | `docs/analysis/LLM_vs_Mock_Quality_Report.md` |

### 2.2 非目标

- ❌ 不优化 LLM 后端本身（OpenAI/Anthropic/MOKA AI 性能由供应商决定）
- ❌ 不替代真实用户测试（用户规则 3 仍需在发布前执行）
- ❌ 不进入 CI 流水线（需 API key，本地运行）
- ❌ 不修改现有 MockBackend 行为（仅新增 role-specific 增强版作为可选项）

---

## 3. 7-Role 共识评估表

| 角色 | 核心立场 | 关键建议 | 状态 |
|------|---------|---------|------|
| **PM** | 衡量 LLM 价值回答"是否真需要 API Key"的核心问题 | V4.4.0 P1，不阻塞发布但影响产品策略；诚实记录，不掩盖 Mock 已足够好的可能 | ✅ 通过 |
| **Architect** | 复用 ConfidenceScorer + FiveAxisConsensusEngine.evaluate() | 新增 OutputQualityComparator + QualityBenchmarkDataset；评分器 fail-secure | ✅ 通过 |
| **Security** | LLM-as-judge 引入 prompt injection 风险 | InputValidator 预处理 + ContentCache 敏感过滤 + DispatchAuditLogger 审计 | ✅ 通过 |
| **Tester** | 双盲评分（LLM-as-judge + 人工抽查校准） | 10 任务集（5 简单+3 中等+2 复杂）+ E2E-09 骨架 + ≥10 红队用例 | ✅ 通过 |
| **Coder** | MockBackend 需升级为 role-specific 模板（前置依赖） | ~800 行（comparator 400+dataset 200+tests 200） | ✅ 通过 |
| **DevOps** | 本地运行不进 CI（需 API key） | `make benchmark-quality` target + Markdown 报告 | ✅ 通过 |
| **UI** | Dashboard 新增"质量对比"面板 | 雷达图+柱状图，莫兰迪色系（用户偏好） | ✅ 通过 |

**共识结论**: 7/7 通过，纳入 V4.4.0 P1。

---

## 4. 方案设计

### 4.1 评估维度（10 维度，复用现有模块）

#### 4.1.1 ConfidenceScorer 5-factor（输出内在质量）

| 维度 | 含义 | 评分方式 |
|------|------|---------|
| completeness | 完整性：是否覆盖任务所有要求 | heuristic（关键词匹配 + 结构检查） |
| certainty | 确定性：陈述是否明确无歧义 | heuristic（模态词检测） |
| specificity | 具体性：是否提供具体方案而非泛泛而谈 | heuristic（实体密度） |
| consistency | 一致性：内部逻辑是否自洽 | heuristic（矛盾检测） |
| model_quality | 模型质量：输出格式/结构/可读性 | heuristic（结构评分） |

#### 4.1.2 FiveAxisConsensusEngine 5-axis（工程外在质量）

| 维度 | 含义 | 评分方式 |
|------|------|---------|
| correctness | 正确性：技术方案是否正确 | heuristic + LLM-as-judge |
| readability | 可读性：输出是否易于理解 | heuristic（句子长度 + 格式） |
| architecture | 架构：方案是否符合架构原则 | heuristic（模式检测） |
| security | 安全：方案是否考虑安全 | heuristic（安全关键词） |
| performance | 性能：方案是否考虑性能 | heuristic（性能关键词） |

### 4.2 任务集设计（10 个典型工程任务）

| # | 任务 | 难度 | 触发角色 | 评估重点 |
|---|------|------|---------|---------|
| T1 | 设计一个安全的用户认证系统 | 简单 | architect, security | correctness, security |
| T2 | 编写一个二分查找函数 | 简单 | solo-coder | correctness, readability |
| T3 | 设计单元测试策略 | 简单 | tester | completeness, specificity |
| T4 | 编写 PRD 文档大纲 | 简单 | product-manager | completeness, readability |
| T5 | 设计 CI/CD 流水线 | 简单 | devops | architecture, performance |
| T6 | 重构一个 God Class | 中等 | architect, solo-coder | architecture, correctness |
| T7 | 评审一段含漏洞的代码 | 中等 | security, tester | security, correctness |
| T8 | 设计可扩展的微服务架构 | 中等 | architect | architecture, completeness |
| T9 | 设计多租户 SaaS 数据库 | 复杂 | architect, security | architecture, security, correctness |
| T10 | 实现一个并发限流器 | 复杂 | solo-coder, devops | correctness, performance, architecture |

**任务集文件**: `data/quality_benchmark/tasks.json`（含任务描述 + 期望输出特征 + 评估权重）

### 4.3 评分方式（三层）

#### Layer 1: Heuristic 评分（必须，无 API key 依赖）

复用 ConfidenceScorer + FiveAxisConsensusEngine.evaluate() 的 heuristic 评估器：
- 优点：可复现、无 API key 依赖、确定性
- 缺点：无法评估语义深度

#### Layer 2: LLM-as-judge 评分（可选，需 API key）

用独立的 LLM 实例对 Mock 输出和 LLM 输出双盲评分：
- 优点：能评估语义深度、更接近人类判断
- 缺点：成本高、可能引入 prompt injection
- 安全：InputValidator 预处理任务描述 + 评分 prompt 模板固定

#### Layer 3: 人工抽查校准（必须，最少 3 任务）

人工对 3 个任务（T1/T6/T10，覆盖简单/中等/复杂）的 Mock 和 LLM 输出盲评：
- 优点：ground truth 校准
- 缺点：耗时
- 样本量：3 任务 × 2 模式 = 6 份输出

### 4.4 数据模型

```python
@dataclass
class QualityScore:
    """单维度评分结果。"""
    dimension: str          # 维度名（如 "correctness"）
    score: float            # 0.0-1.0
    rationale: str          # 评分理由
    scorer_id: str          # "heuristic" / "llm-judge" / "human"

@dataclass
class TaskQualityResult:
    """单任务质量评估结果。"""
    task_id: str            # T1-T10
    task_description: str
    mock_output: str        # Mock 模式输出
    llm_output: str         # LLM 模式输出
    mock_scores: list[QualityScore]   # Mock 评分
    llm_scores: list[QualityScore]    # LLM 评分
    delta: dict[str, float]           # 各维度 LLM - Mock 差值
    winner: str             # "mock" / "llm" / "tie"

@dataclass
class QualityComparisonReport:
    """整体对比报告。"""
    task_results: list[TaskQualityResult]
    aggregate_stats: dict  # 汇总统计（均值/中位数/标准差）
    task_classification: dict  # 任务分类（mock_sufficient / llm_required / tie）
    cost_benefit: dict     # 成本效益分析（延迟/质量比）
    generated_at: str
    to_markdown(self) -> str
    to_dict(self) -> dict
```

### 4.5 新增模块清单

| # | 模块 | 文件路径 | 职责 | 行数估算 |
|---|------|---------|------|---------|
| 1 | OutputQualityComparator | `scripts/collaboration/output_quality_comparator.py` | 对比器主模块 | ~400 |
| 2 | QualityBenchmarkDataset | `data/quality_benchmark/tasks.json` | 10 任务集 | ~200 |
| 3 | RoleSpecificMockBackend | `scripts/collaboration/llm_backend.py`（扩展） | 7 角色 Mock 模板 | ~150 |
| 4 | benchmark_quality.py | `scripts/benchmark_quality.py` | 质量基准脚本 | ~200 |
| 5 | 单元测试 | `tests/unit/test_output_quality_comparator.py` | 7 维度覆盖 | ~250 |
| 6 | 集成测试 | `tests/integration/test_dispatch_with_quality_compare.py` | dispatch 集成 | ~100 |
| 7 | E2E 骨架 | `tests/e2e/test_user_stories_skeleton.py::test_e2e_09_quality_comparison` | E2E 骨架 | ~50 |
| 8 | 红队测试 | `tests/security/test_quality_comparator_redteam.py` | ≥10 红队用例 | ~150 |
| **合计** | | | | **~1500** |

### 4.6 Skill 集成点（防幽灵功能硬约束）

| 新模块 | Skill 集成 | dispatcher API | 触发阶段 |
|--------|----------|---------------|---------|
| OutputQualityComparator | DispatchSkill.run(mode="compare_quality") | `dispatcher.compare_mode_quality(tasks, mock_backend, llm_backend)` | 手动触发（需 API key） |
| RoleSpecificMockBackend | MockBackend 默认行为升级 | `MockBackend(role_specific=True)` | 启动时配置 |
| benchmark_quality.py | CLI 入口 | `python scripts/benchmark_quality.py --backend openai` | 命令行触发 |

**防幽灵验证**:
- ✅ Skill 调用链：`DispatchSkill.run(mode="compare_quality")` 自然触发
- ✅ 统计计数器：`_call_counter` 可被 `check_module_activation.py` 检测
- ✅ 用户可见性：`to_markdown()` 渲染 Markdown 报告"质量对比"章节
- ✅ 测试覆盖：unit + integration + e2e + redteam 四层

---

## 5. 推进计划（4 Phase）

### Phase 1: 前置依赖 + 任务集（1 周）

| 任务 | 文件路径 | 验证命令 | 状态 |
|------|---------|---------|------|
| 1.1 MockBackend 升级为 role-specific | `scripts/collaboration/llm_backend.py` | `pytest tests/unit/test_llm_backend.py`（扩展） | ⏳ |
| 1.2 创建 10 任务集 | `data/quality_benchmark/tasks.json` | `python -c "import json; json.load(open('data/quality_benchmark/tasks.json'))"` | ⏳ |
| 1.3 任务集验证脚本 | `scripts/validate_benchmark_tasks.py` | `python scripts/validate_benchmark_tasks.py` | ⏳ |

**门禁**:
- [ ] MockBackend role-specific 模板 7 角色全覆盖
- [ ] 任务集 10 任务覆盖 7 角色 × 3 难度
- [ ] 现有测试零回归（MockBackend 升级不破坏向后兼容）

### Phase 2: 对比器实现 + 单元测试（2 周）

| 任务 | 文件路径 | 验证命令 | 状态 |
|------|---------|---------|------|
| 2.1 先写测试（TDD） | `tests/unit/test_output_quality_comparator.py` | `pytest tests/unit/test_output_quality_comparator.py`（先 fail） | ⏳ |
| 2.2 实现 OutputQualityComparator | `scripts/collaboration/output_quality_comparator.py` | `pytest tests/unit/test_output_quality_comparator.py`（全 pass） | ⏳ |
| 2.3 集成 ConfidenceScorer | 复用 `scripts/collaboration/confidence_score.py` | 上述测试覆盖 | ⏳ |
| 2.4 集成 FiveAxisConsensusEngine.evaluate() | 复用 `scripts/collaboration/five_axis_consensus.py` | 上述测试覆盖 | ⏳ |
| 2.5 实现 LLM-as-judge 评分器 | `scripts/collaboration/output_quality_comparator.py`（内部） | 上述测试覆盖 | ⏳ |

**门禁**:
- [ ] 单元测试覆盖率 ≥80%（7 维度：Happy/Error/Boundary/Performance/Configuration/Integration/Security）
- [ ] OutputQualityComparator 复杂度 ≤C（radon）
- [ ] LLM-as-judge 评分器 fail-secure（LLM 失败降级为 heuristic）
- [ ] InputValidator 预防 prompt injection（红队测试覆盖）

### Phase 3: 集成 + E2E + 红队（1 周）

| 任务 | 文件路径 | 验证命令 | 状态 |
|------|---------|---------|------|
| 3.1 dispatch pipeline 集成 | `scripts/collaboration/dispatch_hooks.py` | `pytest tests/integration/test_dispatch_with_quality_compare.py` | ⏳ |
| 3.2 E2E-09 骨架 | `tests/e2e/test_user_stories_skeleton.py::test_e2e_09_quality_comparison` | `pytest tests/e2e/test_user_stories_skeleton.py::test_e2e_09_quality_comparison` | ⏳ |
| 3.3 红队用例 ≥10 条 | `tests/security/test_quality_comparator_redteam.py` | `pytest tests/security/test_quality_comparator_redteam.py` | ⏳ |
| 3.4 benchmark_quality.py 脚本 | `scripts/benchmark_quality.py` | `python scripts/benchmark_quality.py --backend mock --tasks 10` | ⏳ |
| 3.5 SKILL.md + CHANGELOG 更新 | `SKILL.md` / `CHANGELOG.md` | `bash scripts/check_doc_consistency.sh` | ⏳ |

**门禁**:
- [ ] dispatch pipeline 集成测试通过（零回归）
- [ ] E2E-09 测试 pass（给定 10 任务，生成对比报告）
- [ ] 红队测试 ≥10 条（评分操纵/模式混淆/敏感泄露）
- [ ] CI 全绿（不含需 API key 的测试）
- [ ] SKILL.md 模块数 +1（OutputQualityComparator）

### Phase 4: 执行基准 + 生成报告（1 周）

| 任务 | 输出 | 验证方式 | 状态 |
|------|------|---------|------|
| 4.1 执行 Mock 模式基准（10 任务） | Mock 输出 + heuristic 评分 | `python scripts/benchmark_quality.py --backend mock` | ⏳ |
| 4.2 执行 LLM 模式基准（10 任务，需 API key） | LLM 输出 + heuristic 评分 | `python scripts/benchmark_quality.py --backend openai` | ⏳ |
| 4.3 执行 LLM-as-judge 评分（双盲） | LLM-as-judge 评分 | 脚本自动 | ⏳ |
| 4.4 人工抽查校准（3 任务 × 2 模式） | 人工评分 | 人工执行 | ⏳ |
| 4.5 生成决策报告 | `docs/analysis/LLM_vs_Mock_Quality_Report.md` | Markdown 报告 | ⏳ |
| 4.6 Dashboard 面板 | `dashboard/v43_panels.py`（扩展） | `streamlit run scripts/dashboard.py` | ⏳ |

**门禁**:
- [ ] 10 任务 × 2 模式 = 20 份输出全部生成
- [ ] 三层评分（heuristic + LLM-as-judge + 人工）全部完成
- [ ] 决策报告回答 G1-G5 全部目标
- [ ] Dashboard 面板可视化正常（莫兰迪色系）

---

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Mock 模式评估结果已足够好，影响 Pro 版商业价值 | 中 | 中 | 诚实记录，不掩盖；Mock 足够好反而是产品优势（免费用户也能用） |
| LLM-as-judge 评分引入 prompt injection | 中 | 高 | InputValidator 预处理 + 评分 prompt 模板固定 + 红队测试 |
| 任务集不代表真实用户场景 | 中 | 中 | 任务集覆盖 7 角色 × 3 难度 + 人工抽查校准 |
| MockBackend 升级破坏向后兼容 | 低 | 高 | 保留 `role_specific=False` 默认行为 + 全量回归测试 |
| LLM API 成本超预算 | 低 | 低 | 10 任务 × 2 模式 = 20 次 LLM 调用，成本可控 |
| 评分方式偏差（heuristic 无法评估语义深度） | 中 | 中 | 三层评分（heuristic + LLM-as-judge + 人工）交叉校准 |

---

## 7. 成本效益预估

### 7.1 开发成本

| 项 | 估算 |
|----|------|
| 代码量 | ~1500 行 |
| 开发周期 | 5 周（4 Phase） |
| 测试用例 | ~50（unit 25 + integration 5 + e2e 1 + redteam 10 + 其他 9） |

### 7.2 运行成本

| 项 | 估算 |
|----|------|
| LLM API 调用 | 10 任务 × 2 模式 = 20 次（基准）+ 10 次（LLM-as-judge）= 30 次 |
| 预估成本 | OpenAI gpt-4: ~$3-5 / Anthropic: ~$2-4 / MOKA: 按套餐 |
| 人工抽查 | 3 任务 × 2 模式 = 6 份输出 × 10 分钟 = 1 小时 |

### 7.3 预期收益

| 收益 | 价值 |
|------|------|
| 回答"DevSquad 是否需要 LLM"核心问题 | 产品策略决策依据 |
| 任务路由策略（Mock 足够 vs 必须 LLM） | 用户体验优化 |
| Pro 版商业价值量化论证 | 商业化决策依据 |
| 输出质量基准线建立 | 后续版本质量回归检测基础 |

---

## 8. 决策待确认项

> 以下决策需用户确认后才能进入实施阶段。

| # | 决策项 | 选项 | 推荐 |
|---|--------|------|------|
| D1 | 是否纳入 V4.4.0 P1？ | A. 纳入 V4.4.0 P1 / B. 推迟到 V4.5.0 / C. 不做 | A |
| D2 | MockBackend 是否升级为 role-specific？ | A. 升级（默认 role_specific=True）/ B. 升级（默认 False，可选）/ C. 不升级 | B（向后兼容） |
| D3 | 评分方式优先级？ | A. heuristic 主导 / B. LLM-as-judge 主导 / C. 三层并列 | A（成本低可复现） |
| D4 | 任务集数量？ | A. 10 任务（当前方案）/ B. 20 任务 / C. 5 任务（最小可行） | A |
| D5 | 是否需要人工抽查？ | A. 必须 3 任务 / B. 可选 / C. 不需要 | A（ground truth 校准） |
| D6 | Dashboard 面板是否在本期实现？ | A. 本期实现 / B. 推迟到 V4.5.0 | B（聚焦核心对比功能） |

---

## 9. 验收标准

### 9.1 功能验收

- [ ] `python scripts/benchmark_quality.py --backend mock --tasks 10` 生成 Mock 模式评分报告
- [ ] `python scripts/benchmark_quality.py --backend openai --tasks 10` 生成 LLM 模式评分报告
- [ ] `docs/analysis/LLM_vs_Mock_Quality_Report.md` 回答 G1-G5 全部目标
- [ ] 任务分类矩阵输出（mock_sufficient / llm_required / tie）

### 9.2 质量验收

- [ ] 单元测试覆盖率 ≥80%
- [ ] 红队测试 ≥10 条全部通过
- [ ] E2E-09 测试 pass
- [ ] radon 复杂度 ≤C
- [ ] ruff 0 errors / mypy 0 errors
- [ ] 文档一致性检查通过

### 9.3 文档验收

- [ ] SKILL.md 模块表新增 OutputQualityComparator
- [ ] CHANGELOG V4.4.0 条目完整
- [ ] README 三语版本同步
- [ ] 本规划文档状态更新为"已完成"

---

## 10. 7-Role LLM 评审结论（2026-07-28，MOKA AI claude-opus-5）

> **完整评审报告**: [2026-07-28_LLM_vs_Mock_7Role_LLM_Review.md](../analysis/2026-07-28_LLM_vs_Mock_7Role_LLM_Review.md)
> **评审方式**: 直接串行 LLM 调用（MOKA AI, anthropic/claude-opus-5, 7 角色 × 单次）
> **总耗时**: 638.1s + 重试 171.0s ≈ 13.5 分钟 | **7/7 成功**

### 10.1 立场汇总

| 角色 | 立场 | 耗时 | Tokens |
|------|------|------|--------|
| 架构师 | **有条件通过** | 110.3s | 5348 |
| 产品经理 | **有条件通过** | 78.4s | 4294 |
| 安全专家 | **有条件通过** | 98.4s（重试） | 5185 |
| 测试专家 | **有条件通过** | 239.0s | 5274 |
| 独立开发者 | **有条件通过** | 105.6s | 4941 |
| DevOps工程师 | **有条件通过** | 86.3s | 4516 |
| UI设计师 | **有条件通过** | 72.6s（重试） | 4106 |

**共识**: 7/7 有条件通过（无无条件通过，无不通过）

### 10.2 核心共识（7 角色高度一致）

| # | 共识 | 支持角色 | 影响决策 |
|---|------|---------|---------|
| C1 | **Layer 1 heuristic 评分存在循环论证风险**。ConfidenceScorer + FiveAxisConsensusEngine 是为 LLM 输出设计的启发式打分器，用它评 Mock vs LLM 等于先假设结论再测量。Mock 模板化短文本在 completeness/specificity 上必然低分。 | 架构师/PM/测试/独立开发者/DevOps | D3 |
| C2 | **先做薄切片/探针，不要直接投入 1500 行**。架构师建议仪器校准门（~50 行），PM 建议限时 spike，测试专家建议效度验证，独立开发者建议 200 行探针，DevOps 建议 150 行薄切片。 | 全部 7 角色 | D1 |
| C3 | **砍掉 dispatch 集成和 Dashboard**。基准测试是 tooling 不是 skill surface；一次性实验被过度产品化；`DispatchSkill.run(mode="compare_quality")` 是错误的集成点。 | 架构师/PM/独立开发者/DevOps/安全/UI | D6 |
| C4 | **统计设计不足**。10 任务 × 1 次采样无法区分"模式差距"和"采样噪声"；LLM 是随机过程需要 n=3 重复采样；6 份人工抽查不足以校准三层评分体系。 | 全部 7 角色 | D4/D5 |
| C5 | **冻结现有 MockBackend，不修改**。三臂对照（冻结基线 / RoleSpecificMockBackend / LLM）才能分离"模板价值"与"LLM 价值"。 | 架构师/PM/测试/独立开发者/安全 | D2 |

### 10.3 对 6 项决策的修订建议

| 决策 | 原方案推荐 | LLM 评审修订建议 | 共识度 |
|------|----------|----------------|--------|
| **D1** 纳入 V4.4.0 P1？ | A. 纳入 | **修订**: 先做薄切片/探针（~150-200 行，3 任务 × Layer 1），拿到信号强度后再决定是否扩建。不直接纳入 P1 完整 1500 行。 | 7/7 一致 |
| **D2** MockBackend 升级？ | B. 升级默认 False | **修订**: 冻结现有 MockBackend 作为不可变基线（打版本号），RoleSpecificMockBackend 作为独立第三臂新增、默认关闭。三臂对照。**绝不修改现有 MockBackend**。 | 7/7 一致 |
| **D3** 评分优先级？ | A. heuristic 主导 | **修订**: 都不主导。人工盲评为 ground truth，LLM-as-judge 为主要比较信号（须带位置互换 + null control），heuristic 仅作廉价回归哨兵（须先验证相关性）。**从主指标剔除 `model_quality` 因子**（同义反复）。 | 7/7 一致 |
| **D4** 任务集数量？ | A. 10 任务 | **修订**: 保持 10 个或缩到 6 个，但**每个任务 n=3 重复采样**。优先补"Mock 可能够用"的边界任务（boilerplate/changelog/格式化）。加 2-3 个对抗注入任务 + 1 个事实核查任务。 | 7/7 一致 |
| **D5** 人工抽查？ | A. 必须 3 任务 | **修订**: 扩大到 8-16 份人工抽查，双人独立盲评计算一致性（Cohen's κ）。预算从 1 小时改为 3-4 小时。**改用成对强制选择**（A/B 盲选）而非 10 维度打分。 | 7/7 一致 |
| **D6** Dashboard 时机？ | B. 推迟 V4.5.0 | **维持**: 延后到 V4.5.0，且以基准确定要周期性回归为前提。V4.4.0 用 `to_markdown()` + JSON artifact。**P1 冻结可视化数据契约（JSON schema）**。 | 7/7 一致 |

### 10.4 方案修订摘要（基于 LLM 评审反馈）

| 原方案 | 修订后 | 依据 |
|--------|-------|------|
| ~1500 行 + 4 Phase | **~200 行薄切片先行**，信号强度决定后续扩建 | C2（7/7 一致） |
| heuristic 主导评分 | **人工盲评 ground truth**，heuristic 仅作回归哨兵 | C1 + C5 |
| DispatchSkill.run(mode="compare_quality") | **砍掉 dispatch 集成**，仅保留 scripts/benchmark_quality.py | C3 |
| to_markdown() 用户可见 + Dashboard | **Markdown + JSON artifact**，Dashboard 延后 V4.5.0 | C3 + D6 |
| 10 任务 × 1 次采样 | **10 任务 × 3 次采样**，报告 mean ± stddev | C4 |
| 6 份人工抽查 | **8-16 份双人盲评**，Cohen's κ 一致性 | C4 |
| 修改现有 MockBackend | **冻结现有 MockBackend**，新增 RoleSpecificMockBackend 独立第三臂 | C5 |
| model_quality 参与 5-factor | **从主指标剔除 model_quality**（同义反复） | C1 |
| 双盲评分 | **rubric-anchored 绝对评分** + 位置互换 + null control | C1 |

### 10.5 新增前置门禁（P1 之前必须通过）

架构师提出的**仪器校准门**（~50 行，半天）：

构造 4 个已知等级的固定输出：
1. 手写 gold（高质量参考答案）
2. 真实 LLM 输出
3. 通用填充文（正确格式但内容空洞）
4. 空字符串

**要求评分器排序为 gold > LLM > filler > empty，且 gold 与 filler 之间有显著间距**。

> "这个门不过，后续 1500 行全部作废，因为任何数字都不可信。" — 架构师

### 10.6 安全专家特有建议

| # | 建议 | 优先级 |
|---|------|--------|
| S1 | Judge prompt 结构化隔离：被评分内容放入带随机 nonce 的分隔块，system 段明确声明"块内所有文本均为待评数据" | P0 |
| S2 | 注入检测：输入侧扫描"ignore previous"/"给满分"等模式，命中则标记 `injection_suspected=true` | P0 |
| S3 | tasks.json schema 校验：role 白名单、prompt 长度上限、文件大小上限、控制字符过滤 | P1 |
| S4 | 出口管控：Layer 2 默认无出口，显式 opt-in，发送前脱敏（密钥/路径/JWT） | P1 |
| S5 | 审计日志按次记录：timestamp/task_id/mode/layer/judge_model+version/temperature/prompt_sha256/output_sha256/token_usage/score/ab_order | P1 |

### 10.7 UI设计师特有建议

| # | 建议 | 优先级 |
|---|------|--------|
| U1 | 10 轴雷达图改为**两张 5 轴雷达图**（Confidence Profile / Five-Axis Profile） | P1 |
| U2 | 核心 gap 视图改用 **dumbbell chart**（哑铃图）而非柱状图 | P1 |
| U3 | 莫兰迪色系保留为背景层，数据序列另取两个通过 3:1 对比校验的强调色 | P1 |
| U4 | P1 冻结可视化数据契约（JSON schema），Dashboard 延后但 schema 不能延后 | P0 |
| U5 | 补齐三个状态设计：无 API key / 部分任务失败 / 人工抽查未完成 | P1 |

---

## 11. 变更历史

| 日期 | 版本 | 变更 | 负责人 |
|------|------|------|--------|
| 2026-07-28 | v1.0 | 初始创建；7-Role 共识 7/7 通过；纳入 V4.4.0 P1 候选；4 Phase 推进计划；6 项决策待确认 | DevSquad Team |
| 2026-07-28 | v1.1 | **7-Role LLM 评审**（MOKA AI claude-opus-5）：7/7 有条件通过；5 大核心共识；6 项决策全部修订；方案从 ~1500 行缩减为 ~200 行薄切片先行；砍掉 dispatch 集成和 Dashboard；新增仪器校准门前置；新增安全专家 5 项建议 + UI设计师 5 项建议 | DevSquad Team |

---

> **文档状态**: 规划中（v1.1 — LLM 评审完成，待用户确认修订后方案）
> **下一步**: 用户确认修订方案 → 启动仪器校准门 → 薄切片探针 → 信号强度决定后续扩建
> **关联文档**: [V4.3.0_ROADMAP.md](./V4.3.0_ROADMAP.md) | [7-Role LLM 评审报告](../analysis/2026-07-28_LLM_vs_Mock_7Role_LLM_Review.md) | [benchmark_real_llm.py](../../scripts/benchmark_real_llm.py) | [test_real_llm_smoke.py](../../tests/smoke/test_real_llm_smoke.py)
