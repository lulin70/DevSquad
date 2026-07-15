# Architecture Decision Records (ADR)

> **文档类型**: ADR 体系说明
> **来源理念**: Matt Pocock domain-modeling — ADR with 3-criterion gate
> **目录位置**: `docs/adr/`
> **最后更新**: 2026-07-15 (V4.1.0)

---

## 一、什么是 ADR

ADR (Architecture Decision Record) 是记录架构决策的文档。每个 ADR 描述一个特定的架构决策，包括上下文、决策、替代方案和后果。

## 二、三准则门禁（全满足才写 ADR）

一个决策只有在 **同时满足以下三个准则** 时才需要写 ADR：

| # | 准则 | 说明 | 示例 |
|---|------|------|------|
| 1 | **影响多个模块** | 决策影响范围超过单个文件 | TasteDials vs PromptDials 的职责分离影响 qa/ 和 collaboration/ 两个层 |
| 2 | **有替代方案被考虑** | 决策过程中有多个选项被权衡 | 统一到 PromptDials vs 新建 TasteDials |
| 3 | **未来可能被推翻** | 决策不是永久的，可能随演进改变 | 随 UI/UX 需求演进，TasteDials 可能合并回 PromptDials |

**不满足任一准则的变更**：通过 commit message 或代码注释记录即可，不需要 ADR。

## 三、ADR 格式

```markdown
# ADR-XXX: [决策标题]

## 状态
Accepted | Proposed | Deprecated | Superseded by ADR-YYY

## 上下文
[为什么需要做这个决策？遇到什么问题？]

## 决策
[做了什么决策？最终选择了什么？]

## 替代方案
[考虑过但放弃的方案，以及放弃的原因]

## 后果
[决策带来的正面和负面影响]
```

## 四、ADR 编号规则

- 格式：`ADR-XXX`（三位数字，从 001 开始）
- 文件名：`ADR-XXX-short-title.md`
- 编号连续，不回收（被取代的 ADR 标记为 Superseded，不删除）

## 五、ADR 列表

| ADR | 标题 | 状态 | 日期 |
|-----|------|------|------|
| [ADR-001](ADR-001-four-doc-system.md) | 四文档体系建立（GLOSSARY + ADR + DESIGN + SPEC） | Accepted | 2026-07-15 |

---

> **维护规则**: 每次满足三准则的架构决策必须写 ADR。ADR 一旦 Accepted 不可删除，只能被 Superseded。
