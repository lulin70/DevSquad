# Ponytail 标记使用指南

> **版本**: V3.10.0
> **适用范围**: DevSquad 多 Agent 协作框架
> **相关模块**: `PonytailRuleInjector` / `YagniChecker` / `PromptAssembler`
> **规格参考**: [docs/spec/v3.10.0_spec.md §5.2](../spec/v3.10.0_spec.md)

---

## 1. 概述

Ponytail 标记是 DevSquad V3.10.0 引入的**意图标注约定**，用于在代码/文档中显式标记**有意的简化**（intentional simplifications）。它源于 ponytail 项目的「懒惰阶梯」哲学——懒即高效，而非偷工减料。

标记的核心价值：
- **区分"故意省略"与"遗漏"**：审阅者无需猜测某段简化是有意为之还是疏忽
- **沉淀设计决策**：标记附带简短理由，形成可追溯的轻量级 ADR（Architecture Decision Record）
- **辅助 YagniChecker 运行时决策**：标记的简化不会被运行时检查器误判为缺失实现

---

## 2. `ponytail:` 标记约定

### 2.1 语法

在代码或文档中，以 `ponytail:` 前缀的注释表示一处有意的简化：

```python
# Python
return cached_value  # ponytail: 跳过 TTL 校验，本场景为只读快照
```

```javascript
// JavaScript
const result = items.slice(0, 100);  // ponytail: 硬编码上限 100，MVP 阶段足够
```

```markdown
<!-- Markdown 文档 -->
> ponytail: 本节省略错误码完整对照表，详见附录 A（当前仅 3 个错误码）
```

### 2.2 标记要素

每处标记应包含：
1. **`ponytail:` 前缀**（必需，用于工具识别）
2. **简短理由**（必需，一句话说明为何简化）
3. **可选：适用条件/触发边界**（如"仅 MVP 阶段"/"当 N < 1000 时"）

### 2.3 放置位置

- **行尾注释**：适合单行简化（最常见）
- **行前注释**：适合多行简化的说明
- **文档内联**：适合文档段落的省略说明

---

## 3. 何时使用标记

### 3.1 应当标记的场景

| 场景 | 示例 |
|------|------|
| **YAGNI 简化** | 用户只要 2 种排序方式，省略通用排序工厂 |
| **标准库优先** | 用 `collections.Counter` 替代手写频率统计 |
| **一行实现** | 用 `max(items, key=...)` 替代完整比较类 |
| **删除优于添加** | 移除未使用的抽象层，直接调用 |
| **硬编码临时值** | MVP 阶段的魔法数字，明确后续可配置化 |
| **平台原生方案** | 用 `pathlib.Path` 替代自定义路径工具 |

### 3.2 示例：正确的标记

```python
# ✅ 正确：标记 YAGNI 简化 + 理由
def validate_email(email: str) -> bool:
    return "@" in email  # ponytail: MVP 仅校验 @ 存在，正则校验留待 V2

# ✅ 正确：标记标准库优先
from collections import Counter
freq = Counter(words)  # ponytail: 用标准库替代手写哈希统计

# ✅ 正确：标记一行实现
is_valid = len(errors) == 0  # ponytail: 一行布尔表达式，无需封装 isValid() 方法
```

---

## 4. 何时**不**使用标记

### 4.1 不应标记的场景

| 场景 | 原因 |
|------|------|
| **Bug 临时绕过** | Bug 应修复，不应标记为"有意简化" |
| **未完成的功能** | 用 `TODO:` 或 `FIXME:` 而非 `ponytail:` |
| **安全相关省略** | 安全校验**永不削减**，不可标记省略 |
| **输入校验省略** | 信任边界的输入校验**永不削减** |
| **错误处理省略** | 防数据丢失的错误处理**永不削减** |
| **可访问性省略** | a11y 要求**永不削减** |

### 4.2 示例：错误的标记

```python
# ❌ 错误：Bug 绕过不应标记为 ponytail
try:
    data = parse(json_str)
except Exception:
    pass  # ponytail: 忽略解析错误 ← 这是 Bug，应修复！

# ❌ 错误：安全校验不可省略
def login(user, pwd):
    return True  # ponytail: 跳过密码校验 ← 安全永不削减！

# ❌ 错误：未完成功能应用 TODO
# ponytail: 分页功能待实现 ← 应改为 # TODO: 实现分页
```

---

## 5. Ponytail 硬约束边界

Ponytail 哲学强调"懒惰"，但有**四条永不削减的底线**：

| 底线 | 含义 | 标记适用性 |
|------|------|------------|
| **信任边界输入校验** | 外部输入（用户/API/文件）必须校验 | ❌ 不可标记省略 |
| **防数据丢失错误处理** | 涉及持久化/删除/转账等不可逆操作 | ❌ 不可标记省略 |
| **安全性** | 认证/授权/加密/防注入 | ❌ 不可标记省略 |
| **可访问性** | WCAG/a11y 相关实现 | ❌ 不可标记省略 |

> **原则**：`ponytail:` 标记只能用于"可以更懒"的地方，不能用于"不该偷懒"的地方。

---

## 6. 配置

### 6.1 启用 ponytail 规则注入

在 `.devsquad.yaml` 中配置：

```yaml
quality_control:
  enabled: true
  minimal_implementation: true    # 启用 ponytail 规则注入
  ponytail_markers: true          # 启用 ponytail: 标记约定（默认 true）
```

### 6.2 禁用标记

若需禁用标记约定（仍保留懒惰阶梯规则）：

```yaml
quality_control:
  minimal_implementation: true
  ponytail_markers: false         # 禁用标记，注入器会附加说明
```

禁用后，`PonytailRuleInjector` 会在注入文本末尾追加：
> *(Note: `ponytail:` markers are disabled in config; do not add them to output.)*

### 6.3 压缩模式自动跳过

为避免压缩失效，以下 PromptAssembler 压缩模式**自动跳过** ponytail 注入：
- `ultra_minimal`（FULL_COMPACT）
- `minimal`（SESSION_MEMORY）

`structured` / `standard` / `simple` / `direct` 模式正常注入。

---

## 7. 与 YagniChecker 的关系

| 维度 | PonytailRuleInjector | YagniChecker |
|------|---------------------|--------------|
| **类型** | 静态 prompt 注入 | 运行时决策树 |
| **时机** | 生成前（行为准则） | 生成中（每步决策） |
| **输出** | 规则文本 | verdict（NECESSARY/SKIP/USE_STDLIB/...） |
| **作用** | 让 LLM 内化懒惰心态 | 强制每步经过懒惰阶梯检查 |
| **互补** | 提供心态基础 | 提供执行保障 |

**两者协同**：PonytailRuleInjector 让 LLM "想偷懒"，YagniChecker 确保 LLM "真的偷懒对了"。`ponytail:` 标记是 LLM 表达"我已按懒惰阶梯决策"的显式信号，YagniChecker 在运行时遇到标记可减少重复检查。

---

## 8. 审阅指引

代码审阅时遇到 `ponytail:` 标记：

1. **核实理由是否成立**：简化是否真的符合 YAGNI/标准库优先/一行实现原则？
2. **核实边界是否正确**：是否触碰了四条永不削减底线？
3. **核实条件是否合理**：标记的适用条件（如"MVP 阶段"）是否会在可预见未来失效？
4. **无需要求补全**：标记的简化是**有意的**，不应要求"补全实现"，除非理由已失效。

---

## 9. 反模式

| 反模式 | 问题 | 正确做法 |
|--------|------|----------|
| 标记泛滥 | 每行都加 `ponytail:` | 只标记**非显而易见**的简化 |
| 标记代替注释 | `ponytail: 变量 x` | 标记是**意图标注**，不是普通注释 |
| 标记掩盖 Bug | `# ponytail: 忽略异常` | Bug 应修复，不可标记 |
| 标记后不跟踪 | "MVP 阶段"永久延续 | 在 ROADMAP 中记录简化项的清理计划 |
| 无理由标记 | `# ponytail:` | 必须附带简短理由 |

---

## 10. 相关文档

- [V3.10.0 规格文档 §5.2](../spec/v3.10.0_spec.md) — PonytailRuleInjector 设计
- [ponytail_headroom_research.md](../research/ponytail_headroom_research.md) — 调研背景
- [PonytailRuleInjector 源码](../../scripts/collaboration/ponytail_rule_injector.py)
- [YagniChecker 源码](../../scripts/collaboration/yagni_checker.py)
