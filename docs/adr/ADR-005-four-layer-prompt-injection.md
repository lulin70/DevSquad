# ADR-005: Four-layer prompt injection architecture

## 状态
Accepted

## 日期
2026-07-15

## 上下文

DevSquad PromptAssembler 负责组装 Worker prompt。随着版本演进，prompt 注入层逐渐增多：

1. **V3.10.0 Phase 4** — `_build_learned_rules_injection()` 从 .devsquad.yaml 加载学习规则
2. **V3.x** — `_build_quality_control_injection()` QC 注入
3. **V3.x** — PonytailRuleInjector 注入 ponytail 规则
4. **V4.1.0 Module 10** — `inject_grilling_discipline()` grilling 纪律注入

需要决定这些注入层如何组织，避免 prompt 膨胀和职责混乱。

## 决策

采用四层 prompt 注入架构，每层职责明确、独立构建、可选跳过：

| 层 | 方法 | 来源 | 职责 | 条件 |
|----|------|------|------|------|
| **L1: QC** | `_build_quality_control_injection()` | .devsquad.yaml `quality_control` | 质量控制规则 | `qc_enabled=True` |
| **L2: Ponytail** | `PonytailRuleInjector.build_injection()` | .devsquad.yaml `ponytail_rules` | Ponytail 标记规则 | 配置存在时 |
| **L3: Learned Rules** | `_build_learned_rules_injection()` | .devsquad.yaml `learned_rules` | 历史任务回顾规则 (tier-1, conf≥0.8) | `qc_enabled=True` + 规则存在 |
| **L4: Grilling** | `inject_grilling_discipline()` | 模块级函数 | Grilling 纪律 (one-Q-at-a-time + explore-before-ask) | 始终注入 |

**注入顺序**: L1 → L2 → L3 → L4（追加到 base_prompt 之后）

**设计原则**:
1. 每层独立构建 — 任一层失败不影响其他层
2. 每层可选 — 通过配置或条件控制是否注入
3. 每层有明确边界 — 不在其他层中重复内容
4. L4 始终注入 — grilling 纪律是所有角色的基本素养

## 替代方案

### 方案 A: 统一到 QC 层（放弃）
- **描述**: 将 learned_rules + grilling 都放在 QC 注入中
- **放弃原因**: QC 关注质量门禁规则，learned_rules 关注历史经验，grilling 关注访谈纪律。职责不同，混合会导致 QC 层膨胀且难以独立配置

### 方案 B: 动态选择注入层（放弃）
- **描述**: 根据任务复杂度选择注入哪些层（Simple 仅 L1，Complex 全部）
- **放弃原因**: grilling 纪律应始终存在（L4），不能因任务简单就跳过。learned_rules 和 QC 的条件已由配置控制，无需额外的复杂度判断

### 方案 C: 合并到 PromptDials（放弃）
- **描述**: 将注入内容编码到 PromptDials 旋钮中
- **放弃原因**: PromptDials 控制 prompt 风格（verbosity/creativity/risk_tolerance），注入内容是具体规则/纪律，两者职责不同。dials 是连续旋钮，注入是离散内容

## 后果

### 正面影响
1. **职责清晰** — 四层各有明确职责，不重叠
2. **独立配置** — 每层可通过配置独立开关
3. **可扩展** — 未来新增注入层只需添加新方法，不改现有层
4. **grilling 始终生效** — L4 无条件注入，确保所有角色遵循 grilling 纪律

### 负面影响
1. **prompt 长度增加** — 四层注入累计约 500-1000 字符
2. **配置复杂度** — 需理解四层配置项的含义和条件
3. **层间依赖隐性** — L3 依赖 L1 的 `qc_enabled`，非完全独立

### 缓解措施
1. 每层注入有长度限制（learned_rules 最多 10 条）
2. PromptAssembler metadata 记录各层是否注入，便于调试
3. 文档明确四层职责边界（本 ADR + GLOSSARY.md）

---

> **参考**: [PromptAssembler](../../scripts/collaboration/prompt_assembler.py) | [PonytailRuleInjector](../../scripts/collaboration/ponytail_rule_injector.py) | [Matt Pocock grilling SKILL.md](https://github.com/mattpocock/skills/blob/main/skills/productivity/grilling/SKILL.md)
