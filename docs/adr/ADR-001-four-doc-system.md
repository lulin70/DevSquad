# ADR-001: 四文档体系建立（GLOSSARY + ADR + DESIGN + SPEC）

## 状态
Accepted

## 日期
2026-07-15

## 上下文

DevSquad V4.0.11 及之前版本仅有 SPEC.md（技术规范）作为核心文档，存在以下问题：

1. **术语散落** — deep/shallow/seam/Consensus/Gate 等术语散落在代码注释、SKILL.md、各文档中，无统一术语表
2. **决策无追溯** — 架构决策（如"7 角色权重设计"、"TasteDials vs PromptDials 分离"）仅记录在 commit message 或 project_memory 中，无结构化决策记录
3. **设计准则缺失** — UI/UX 审计（UIUXAnalyzer）仅依赖通用规则，无项目特定设计准则作为上下文
4. **SPEC.md 职责过载** — SPEC.md 同时承担技术规范、术语定义、设计准则的职责，文档膨胀

借鉴 Matt Pocock domain-modeling 的 CONTEXT.md（纯术语表）+ ADR（三准则决策记录）理念，以及 impeccable 的 PRODUCT.md + DESIGN.md（设计准则上下文）协议，需要建立四文档体系。

## 决策

建立四文档体系，职责严格分离：

| 文档 | 职责 | 来源理念 | 位置 |
|------|------|----------|------|
| **GLOSSARY.md** | 纯术语表（禁止实现细节） | Matt CONTEXT.md | `docs/spec/GLOSSARY.md` |
| **ADR** | 架构决策记录（三准则全满足才写） | Matt domain-modeling | `docs/adr/` |
| **DESIGN.md** | 项目设计准则（UI/UX 审计上下文） | impeccable PRODUCT+DESIGN | `docs/spec/DESIGN.md` |
| **SPEC.md** | 技术规范（模块/API/数据模型） | DevSquad 现有 | `docs/spec/SPEC.md` |

## 替代方案

### 方案 A: 统一到 SPEC.md（放弃）
- **描述**: 所有内容继续放在 SPEC.md 中，用章节区分
- **放弃原因**: SPEC.md 职责过载，文档膨胀不可维护。术语、决策、设计准则的读者和更新频率不同，混在一起导致每次更新都需翻阅整个文档

### 方案 B: 三文档体系（无 DESIGN.md）（放弃）
- **描述**: 仅建立 GLOSSARY + ADR + SPEC，不新建 DESIGN.md
- **放弃原因**: UIUXAnalyzer 审计时无项目特定设计准则作为上下文，只能依赖通用规则。impeccable 的 PRODUCT+DESIGN 协议证明项目特定设计准则对 UI/UX 审计价值很大。用户明确要求增强 UI/UX 能力

### 方案 C: 五文档体系（新增 PRODUCT.md）（放弃）
- **描述**: 额外新建 PRODUCT.md（产品上下文），完全照搬 impeccable 协议
- **放弃原因**: DevSquad 已有 PRD（产品需求文档）覆盖产品上下文功能，新建 PRODUCT.md 会与 PRD 职责重叠。impeccable 的 PRODUCT.md 在 DevSquad 中由 PRD 承担

## 后果

### 正面影响
1. **术语统一** — GLOSSARY.md 作为唯一术语来源，消除术语散落问题
2. **决策可追溯** — ADR 提供结构化决策记录，三准则门禁避免 ADR 泛滥
3. **UI/UX 审计增强** — DESIGN.md 提供项目特定设计准则，UIUXAnalyzer 可按项目准则检测
4. **文档可维护** — 四文档职责分离，各自独立演进，更新频率互不影响

### 负面影响
1. **文档数量增加** — 从 1 个核心文档（SPEC.md）增加到 4 个
2. **一致性维护成本** — 四文档间需要保持术语和引用的一致性
3. **学习曲线** — 新贡献者需要理解四文档的职责边界

### 缓解措施
1. CI 一致性检查 — `scripts/check_doc_consistency.sh` 检查四文档间的术语一致性
2. GLOSSARY.md 作为术语唯一来源 — 其他文档引用 GLOSSARY.md 中的术语，不重复定义
3. ADR 三准则门禁 — 避免低价值 ADR 泛滥
4. 本 ADR 本身作为示例 — 后续 ADR 参考本文件格式

---

> **参考**: [Matt Pocock domain-modeling SKILL.md](https://github.com/mattpocock/skills/blob/main/skills/engineering/domain-modeling/SKILL.md) | [impeccable PRODUCT+DESIGN 协议](https://github.com/pbakaus/impeccable)
