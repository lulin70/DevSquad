# ADR-004: [DEBUG-xxx] tag mechanism for one-shot cleanup

## 状态
Accepted

## 日期
2026-07-15

## 上下文

DevSquad V4.1.0 Module 7 (Matt P0-4) 引入 red-capable gate 和 6-phase 调试法。调试过程中会产生临时调试日志（如 `print("checkpoint A")`、`logger.debug(f"value={x}")`）。

历史上调试日志的清理依赖人工检查，常见问题：
1. **遗漏** — 调试日志混在业务日志中，难以区分
2. **残留** — 调试结束后忘记删除，进入生产环境
3. **grep 困难** — 调试日志没有统一前缀，无法一次 grep 清理

Matt Pocock diagnosing-bugs SKILL.md 提出 [DEBUG-xxx] tag 机制：所有调试日志必须以 `[DEBUG-xxx]` 前缀标记，cleanup 时一次 grep 即可全部找到。

## 决策

在 `execution_guard.py` 中实现 [DEBUG-xxx] tag 机制：

1. **register_debug_tag(tag)** — 注册调试 tag（如 `[DEBUG-Bug123]`）
2. **cleanup_debug_tags(output)** — 从输出中提取所有 [DEBUG-xxx] tag
3. **strip_debug_tags(output)** — 移除包含 [DEBUG-xxx] 的行
4. **get_registered_debug_tags()** — 获取已注册的 tag 集合
5. **clear_debug_tags()** — 清空注册表

**Tag 命名规范**:
- 格式: `[DEBUG-UPPER_CASE_IDENTIFIER]`
- 示例: `[DEBUG-AUTH_FLOW]`, `[DEBUG-CACHE_MISS]`, `[DEBUG-RACE_CONDITION]`
- 正则: `\[DEBUG-([A-Z0-9_]+)\]`

## 替代方案

### 方案 A: logging.DEBUG 级别（放弃）
- **描述**: 用 `logger.debug()` 替代 [DEBUG-xxx] tag，生产环境设 DEBUG 级别为 OFF
- **放弃原因**: logging.DEBUG 是永久性的业务日志级别，不是临时调试日志。调试结束后仍留在代码中，增加噪声。无法一次 grep 清理

### 方案 B: 注释标记 `# DEBUG:`（放弃）
- **描述**: 用 `# DEBUG:` 注释前缀标记调试代码
- **放弃原因**: 注释不会执行，调试代码必须实际运行（如 print/logger.debug）。注释前缀只能标记位置，不能标记输出

### 方案 C: 专用调试日志文件（放弃）
- **描述**: 调试日志写入独立文件（如 `/tmp/devsquad_debug.log`）
- **放弃原因**: 文件系统依赖增加复杂性。调试日志需要和业务日志混合查看才能定位问题。一次 grep 清理仍需要前缀标记

## 后果

### 正面影响
1. **一次 grep 清理** — `grep -rn "\[DEBUG-" .` 找到所有调试日志
2. **调试可追溯** — 每个 tag 关联一个调试会话（如 `[DEBUG-Bug123]`）
3. **生产安全** — strip_debug_tags 可在部署前自动移除调试输出
4. **与 Matt 理念一致** — 6-phase 调试法的 Phase 1 (build feedback loop) 使用 [DEBUG-xxx] 标记

### 负面影响
1. **开发者需记住加 tag** — 调试时需手动添加 `[DEBUG-xxx]` 前缀
2. **Tag 命名约束** — 仅支持 `[A-Z0-9_]+`，不支持中文或其他字符

### 缓解措施
1. execution_guard 提供 register_debug_tag() 自动注册
2. CI 可检查未注册的 [DEBUG-xxx] tag（未来增强）
3. strip_debug_tags 支持批量移除，减少手动清理负担

---

> **参考**: [Matt Pocock diagnosing-bugs SKILL.md](https://github.com/mattpocock/skills/blob/main/skills/engineering/diagnosing-bugs/SKILL.md) | [ExecutionGuard](../../scripts/collaboration/execution_guard.py)
