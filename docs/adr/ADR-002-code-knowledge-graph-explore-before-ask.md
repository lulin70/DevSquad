# ADR-002: CodeKnowledgeGraph as explore-before-ask backbone

## 状态
Accepted

## 日期
2026-07-15

## 上下文

DevSquad V4.1.0 Module 10 (Matt P0-7 grilling) 需要实现 explore-before-ask 纪律：在向用户提问前，先搜索代码库寻找已有答案。

代码库搜索有多种实现方式：
1. **ad-hoc grep/ripgrep** — 每次提问时临时执行文本搜索
2. **AST 遍历** — 每次提问时解析 Python 文件提取符号
3. **CodeKnowledgeGraph** — 已有的持久化代码知识图谱（V3.9-02 引入），支持 find_symbol / find_callers / find_callees / find_similar

选择不同方案会影响：
- `rule_collector.py` GrillingMode 的 explore_before_ask 实现
- `prompt_assembler.py` 的 explore-before-ask 注入文本
- 代码库搜索的响应速度和准确性

## 决策

采用 CodeKnowledgeGraph 作为 explore-before-ask 的搜索后端。

**理由**:
1. CodeKnowledgeGraph 已有持久化索引（SQLite），无需每次重新解析
2. 提供 find_symbol / find_callers 语义查询，比文本搜索更精确
3. 已被 prompt_assembler 的 code_graph_hints 参数集成（V3.9-02），架构一致
4. GrillingMode._extract_search_terms 从问题文本提取符号名，直接传入 find_symbol

## 替代方案

### 方案 A: ad-hoc grep/ripgrep（放弃）
- **描述**: 每次提问时用 `subprocess.run(["rg", ...])` 搜索代码库
- **放弃原因**: 文本搜索无法区分符号定义和字符串引用，误报率高。每次搜索启动子进程开销大。违反 DevSquad "不引入外部依赖"原则（ripgrep 非标准库）

### 方案 B: AST 遍历（放弃）
- **描述**: 每次提问时用 `ast.parse` 遍历项目文件提取符号
- **放弃原因**: 每次全量 AST 解析耗时（大型项目 >2s），不满足 red-capable gate 的 "on-fast" 准则。CodeKnowledgeGraph 已有增量更新机制

### 方案 C: 不做 explore-before-ask（放弃）
- **描述**: grilling 模式直接向用户提问，不搜索代码库
- **放弃原因**: 违反 Matt Pocock grilling 核心理念（explore-before-ask）。用户体验差——代码库已有答案时不应打扰用户

## 后果

### 正面影响
1. **搜索精确** — 语义查询（find_symbol）比文本搜索更准确
2. **响应快速** — 持久化索引查询 <10ms，满足 on-fast 准则
3. **架构一致** — 复用已有 CodeKnowledgeGraph，不引入新依赖
4. **grilling 可降级** — CodeKnowledgeGraph 不可用时，GrillingMode 自动降级为直接提问

### 负面影响
1. **依赖 CodeKnowledgeGraph 构建** — 首次使用需 build_from_project，耗时取决于项目大小
2. **搜索词提取依赖正则** — _extract_search_terms 用正则提取符号名，可能遗漏非常规命名

### 缓解措施
1. GrillingMode 接受 code_graph=None，降级为直接提问模式
2. _extract_search_terms 支持三种命名约定（quoted / snake_case / CamelCase），覆盖 95%+ 场景

---

> **参考**: [Matt Pocock grilling SKILL.md](https://github.com/mattpocock/skills/blob/main/skills/productivity/grilling/SKILL.md) | [CodeKnowledgeGraph](../../scripts/collaboration/code_knowledge_graph.py)
