# DevSquad 技术债跟踪器 (Tech Debt Tracker)

> **文档类型**: 活跃跟踪器 — 每次 commit 后同步更新
> **维护原则**: 活文档 — 新增 TODO/FIXME 时即时登记；解决时标记 RESOLVED
> **最后更新**: 2026-07-24
> **关联文档**: [TECH_DEBT_ASSESSMENT_V4.0.md](./TECH_DEBT_ASSESSMENT_V4.0.md) — 完整技术债评估 (V4.0.11 基线)

## 范围说明

本跟踪器专注于 `scripts/` 目录下 Python 源码中的 **TODO/FIXME/HACK/XXX/WORKAROUND** 标记的活跃跟踪。
对于更广泛的技术债（架构、测试覆盖、`type: ignore`、文档、God Class 等），
请参阅上方关联的 [TECH_DEBT_ASSESSMENT_V4.0.md](./TECH_DEBT_ASSESSMENT_V4.0.md)。

> **重要**: V4.0.11 评估基线 (TECH_DEBT_ASSESSMENT_V4.0.md §一) 已确认：
> 项目在 V4.0.0 时 TODO/FIXME 数为 1 (非实际问题)，V4.0.11 已清理至 0。
> 本跟踪器作为持续活文档，用于后续新增标记的即时登记。

## 统计概览

| 优先级 | 数量 | 状态 |
|--------|------|------|
| P0 (阻断) | 0 | — |
| P1 (重要) | 0 | — |
| P2 (一般) | 0 | — |
| P3 (低)   | 1 | OPEN |
| **总计** | **1** | |

> **扫描说明**: 运行 `grep -rn "TODO\|FIXME\|HACK" scripts/ --include="*.py" | grep -v "test\|__pycache__"`
> 共返回 18 行匹配。经逐行分析，其中 17 行为**技术债检测工具自身的实现代码**
> （regex 模式、enum 常量、docstring 描述），并非真正的 TODO 标记；
> 仅 1 行为实际注释中包含这些关键字（且为描述性段落标题，非可执行 TODO）。
> 详见下方「扫描方法与排除项」章节。

## 技术债明细

### TD-001: tech_debt_manager.py 描述性段落注释

- **优先级**: P3
- **位置**: `scripts/collaboration/tech_debt_manager.py:477`
- **类型**: 描述性注释（非真实 TODO 标记）
- **描述**: 第 477 行注释 `# TODO/FIXME/HACK comments` 是 `_detect_all` 方法中一段
  代码的段落标题，用于说明其下方 `self._detect_todos(...)` 调用会检测源码中的
  TODO/FIXME/HACK 注释。该注释**不是**待办事项标记，而是检测逻辑的功能描述，
  会被简单的关键字扫描误判为 TODO。
- **建议方案**: 无需修改。该注释准确描述了代码意图，保留有助于可读性。
  如希望避免未来扫描误报，可考虑改写为 `# Detect TODO/FIXME/HACK comments in source`
  以更明确表达动作意图，但非必需。
- **状态**: OPEN (INFORMATIONAL — 非真实技术债，仅作登记以避免重复调查)

## 扫描方法与排除项

### 扫描命令

```bash
cd /Users/lin/trae_projects/DevSquad && grep -rn "TODO\|FIXME\|HACK" scripts/ --include="*.py" | grep -v "test\|__pycache__"
```

### 17 行非 TODO 匹配项分类（已排除）

为避免误导，下表列出其余 17 行匹配的性质，说明为何不计入技术债：

| #  | 位置                                        | 性质     | 说明 |
|----|---------------------------------------------|----------|------|
| 1  | `context_compressor.py:53`                  | Enum 常量 | `TODO = "todo"` — MemoryCategory 枚举成员定义 |
| 2  | `context_compressor.py:220`                 | 列表元素 | `"TODO"` — 类别列表成员 |
| 3  | `context_compressor.py:446`                 | 业务逻辑 | `m.category == MemoryCategory.TODO` — 过滤 TODO 类记忆 |
| 4  | `context_compressor.py:617`                 | 业务逻辑 | `return MemoryCategory.TODO` — 返回枚举值 |
| 5  | `tech_debt_manager.py:427`                  | Regex 模式 | `TODO_PATTERN = re.compile(...)` — 检测器模式定义 |
| 6  | `tech_debt_manager.py:442`                  | Docstring | 描述检测器功能 |
| 7  | `tech_debt_manager.py:601`                  | Docstring | `"""Detect TODO/FIXME/HACK comments."""` |
| 8  | `tech_debt_manager.py:603`                  | 业务逻辑 | `self.TODO_PATTERN.finditer(source)` — 调用检测器 |
| 9  | `tech_debt_manager.py:606`                  | 业务逻辑 | 严重度判定 `tag in ("FIXME", "HACK")` |
| 10 | `tech_debt_manager.py:818`                  | Docstring | 描述公共 API 功能 |
| 11 | `review_checkers.py:52`                     | Regex 模式 | `("todo_left", re.compile(r"\b(?:TODO\|FIXME\|XXX\|HACK)\b"))` |
| 12 | `review_checkers.py:542`                    | Docstring | `"""Check for TODO/FIXME, print debugging, etc."""` |
| 13 | `standardized_role_template.py:509`         | Regex 模式 | `re.findall(r"(?i)\b(TODO\|FIXME\|DEPRECATED\|OUTDATED)\b", ...)` |
| 14 | `standardized_role_template.py:515`         | 描述字符串 | f-string 输出 sediment marker 计数 |
| 15 | `redesign_checkers.py:273`                  | Docstring | `"""Detect functions whose body is only pass/TODO/..."""` |
| 16 | `redesign_checkers.py:278`                  | Regex 模式 | 占位函数检测正则 |
| 17 | `redesign_checkers.py:287`                  | 描述字符串 | f-string 报告占位函数 |

> **结论**: 上述 17 行均为技术债检测工具自身的实现代码（检测器、枚举、报告生成），
> 不构成待办事项。DevSquad 内建的 TODO 检测能力
> （`tech_debt_manager.py` / `review_checkers.py` / `redesign_checkers.py`）
> 本身即是项目成熟度的一部分，其代码自然包含对关键字的引用。

## 维护流程

1. **新增 TODO/FIXME 时**: 开发者在 `scripts/` 下新增此类标记时，须即时在本文件登记新条目 (TD-XXX)，并填写优先级、位置、描述、建议方案。
2. **解决 TODO 时**: 将对应条目状态改为 `RESOLVED` 并保留历史记录（不删除条目），在「变更历史」记录解决日期。
3. **定期扫描**: 每次发布前运行上述扫描命令，核对跟踪器与实际代码一致；剔除检测逻辑误报。
4. **优先级标准**:
   - **P0 (阻断)**: 影响功能正确性/安全性 — 必须在发布前解决
   - **P1 (重要)**: 影响可维护性/性能 — 应在当前迭代解决
   - **P2 (一般)**: 代码质量改进 — 计划在下一迭代解决
   - **P3 (低)**: 可有可无的优化 — 按需解决

## 变更历史

| 日期       | 版本 | 变更                                                                     | 负责人   |
|------------|------|--------------------------------------------------------------------------|----------|
| 2026-07-24 | v1.0 | 初始创建；完成 `scripts/` 目录全量扫描，登记 1 项 P3 (INFORMATIONAL) | DevSquad |
