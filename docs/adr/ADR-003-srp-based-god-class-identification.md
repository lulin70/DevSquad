# ADR-003: SRP-based God Class identification (replacing mechanical thresholds)

## 状态
Accepted

## 日期
2026-07-15

## 上下文

DevSquad 历史上使用机械阈值（方法数 >30 或行数 >500/800）识别 God Class。D13 N-1 分析和 P2-2 任务验证了这些阈值极度不可靠：

- D13 N-1: 52 候选 → 1 TRUE / 51 FALSE = **1.9% hit rate (98.1% 误判率)**
- P2-2: 4 个候选（mce_adapter/redis_cache/warmup_manager/worker）全部判定为 NOT God Class
- 误判的类: enhanced_renderer.py, environmental_audio.py, cc2_combat_effects.py, smoke_tactical_ai.py

V4.1.0 Module 6 (Matt P0-3) 引入 deletion test 作为新的架构审查工具。需要决定 God Class 识别的标准方法。

## 决策

采用 SRP（单一职责原则）分析作为 God Class 的唯一可靠判断标准，废弃机械阈值。

**新标准**:
1. **SRP 分析** — 类是否承担多个不相关的职责？每个方法是否服务于同一职责？
2. **Deletion test** — 删除该类后，复杂度是否消失？若消失则不是 God Class（可能是合理的复杂类）
3. **接口内聚性** — 公开方法之间是否有强内聚关系？

**废弃标准**:
- ❌ 方法数 >30
- ❌ 行数 >500 或 >800
- ❌ 注释密度阈值

## 替代方案

### 方案 A: 保留机械阈值 + SRP 补充（放弃）
- **描述**: 保留行数/方法数阈值作为初筛，再用 SRP 分析确认
- **放弃原因**: 98.1% 误判率意味着初筛几乎无效，浪费大量时间。阈值产生的噪声远大于信号

### 方案 B: 仅用 deletion test（放弃）
- **描述**: 用 deletion test 替代所有 God Class 检测
- **放弃原因**: deletion test 检测 pass-through/shallow module，与 God Class（职责过多）是不同的问题。两者互补但不可互相替代

### 方案 C: 引入复杂度工具（如 radon cc）（放弃）
- **描述**: 用圈复杂度工具自动识别 God Class
- **放弃原因**: 圈复杂度衡量函数级复杂度，不衡量类级职责分散。高复杂度 ≠ God Class。DevSquad CI 已有 radon cc check（≥21 blocking），但用于函数级，不用于类级判断

## 后果

### 正面影响
1. **零误判** — SRP 分析基于职责语义，不依赖行数/方法数
2. **与 Matt 理念一致** — deletion test + deep/shallow 词汇统一架构审查语言
3. **节省时间** — 不再对 98% 的误判候选做无意义的分析
4. **可解释性** — SRP 分析结果可向开发者解释"为什么这个类不是 God Class"

### 负面影响
1. **无法全自动** — SRP 分析需要人类/AI 判断，无法纯自动化
2. **主观性** — 不同审查者对"职责"的划分可能不同
3. **无量化指标** — 无法用单一数字衡量"是否 God Class"

### 缓解措施
1. RedesignAuditor 提供 deletion_test() 作为客观辅助工具
2. 架构师 SKILL.md 中写明 SRP 分析的标准流程
3. GLOSSARY.md 定义 SRP 和 God Class 的明确含义

---

> **参考**: [Matt Pocock improve-codebase-architecture SKILL.md](https://github.com/mattpocock/skills/blob/main/skills/engineering/improve-codebase-architecture/SKILL.md) | [D13 N-1 分析](../audits/V4.0.10_Project_Evaluation_Report.md) | [P2-2 取消记录](../P2_P3_PLAN.md)
