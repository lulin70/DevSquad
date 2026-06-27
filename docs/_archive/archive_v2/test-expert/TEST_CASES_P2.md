# Phase 2: PermissionGuard 权限守卫 — 详细测试用例

**版本**: v1.0
**日期**: 2026-04-15
**作者**: 测试专家 (Tester Role)
**基于**: TEST_PLAN_P2.md + USER_STORIES_P2.md

---

## Phase 1: 单元测试 (T1-T6)

### T1: 数据模型验证

**TC-T1.01** ProposedAction 创建和默认值
- **前置**: PermissionGuard 模块已导入
- **步骤**:
  1. 创建 `ProposedAction(action_type=ActionType.FILE_READ, target="/tmp/test.txt")`
  2. 检查所有字段有值
- **预期**: action_type, target, description 非空; risk_score=0.0; timestamp 为近期时间; source_worker_id=None
- **优先级**: P0

**TC-T1.02** ProposedAction 序列化 roundtrip
- **步骤**:
  1. 创建完整 ProposedAction（含 metadata）
  2. 转为 dict
  3. 从 dict 还原
  4. 对比字段一致性
- **预期**: 所有字段值完全一致
- **优先级**: P1

**TC-T1.03** PermissionRule 创建和校验
- **步骤**:
  1. 创建规则 `PermissionRule("TEST", ActionType.FILE_CREATE, "*.py", PermissionLevel.AUTO, "test")`
  2. 检查 rule_id, pattern, required_level 等字段
- **预期**: enabled 默认为 True; tags 默认空列表
- **优先级**: P0

**TC-T1.04** PermissionDecision 完整性
- **步骤**:
  1. 创建 `PermissionDecision(action=action, outcome=ALLOWED, reason="ok")`
  2. 检查 decision_id 格式 ("pd-" 前缀 + hex)
  3. 检查 decided_at 为近期时间
- **预期**: requires_confirmation 默认 False; confidence 默认 1.0
- **优先级**: P0

**TC-T1.05** DecisionOutcome 枚举
- **步骤**: 列出 DecisionOutcome 所有成员
- **预期**: 包含 ALLOWED, DENIED, PROMPT, ESCALATED 共4个
- **优先级**: P0

**TC-T1.06** ActionType 枚举覆盖
- **步骤**: 列出 ActionType 所有成员
- **预期**: FILE_READ, FILE_CREATE, FILE_MODIFY, FILE_DELETE, SHELL_EXECUTE, NETWORK_REQUEST, GIT_OPERATION, ENVIRONMENT, PROCESS_SPAWN 共9个
- **优先级**: P0

**TC-T1.07** PermissionLevel 4级枚举
- **步骤**: 列出 PermissionLevel 所有成员
- **预期**: DEFAULT, PLAN, AUTO, BYPASS 共4个
- **优先级**: P0

**TC-T1.08** AuditEntry 完整性
- **步骤**: 构造 AuditEntry 含 action+decision
- **预期**: entry_id 格式正确; session_id 非空
- **优先级**: P0

**TC-T1.09** 空字段默认值
- **步骤**: `ProposedAction()` 不传参
- **预期**: 不抛异常; 各字段有合理默认值(空字符串/0.0/None)
- **优先级**: P0

**TC-T1.10** Unicode 内容保留
- **步骤**: ProposedAction target="路径/中文文件名.py"
- **预期**: target 字段原样保留，无编码丢失
- **优先级**: P1

---

### T2: 4级行为测试

**TC-T2.01** PLAN → FILE_CREATE = DENIED
- **前置**: guard = PermissionGuard(PermissionLevel.PLAN)
- **步骤**: check(ProposedAction(FILE_CREATE, "new_file.py"))
- **预期**: outcome == DENIED; reason 提及 PLAN 或禁止写操作
- **优先级**: P0 | **对应US**: US-1.1

**TC-T2.02** PLAN → FILE_MODIFY = DENIED
- **前置**: guard = PermissionGuard(PermissionLevel.PLAN)
- **步骤**: check(ProposedAction(FILE_MODIFY, "existing.py"))
- **预期**: outcome == DENIED
- **优先级**: P0 | **对应US**: US-1.1

**TC-T2.03** PLAN → FILE_DELETE = DENIED
- **前置**: guard = PermissionGuard(PermissionLevel.PLAN)
- **步骤**: check(ProposedAction(FILE_DELETE, "old_file.py"))
- **预期**: outcome == DENIED
- **优先级**: P0 | **对应US**: US-1.1

**TC-T2.04** PLAN → SHELL_EXECUTE = DENIED
- **前置**: guard = PermissionGuard(PermissionLevel.PLAN)
- **步骤**: check(ProposedAction(SHELL_EXECUTE, "echo hello"))
- **预期**: outcome == DENIED
- **优先级**: P0 | **对应US**: US-1.1

**TC-T2.05** PLAN → FILE_READ = ALLOWED
- **前置**: guard = PermissionGuard(PermissionLevel.PLAN)
- **步骤**: check(ProposedAction(FILE_READ, "config.json"))
- **预期**: outcome == ALLOWED
- **优先级**: P0 | **对应US**: US-1.1

**TC-T2.06** PLAN → NETWORK_REQUEST = DENIED
- **前置**: guard = PermissionGuard(PermissionLevel.PLAN)
- **步骤**: check(ProposedAction(NETWORK_REQUEST, "https://api.example.com"))
- **预期**: outcome == DENIED
- **优先级**: P0 | **对应US**: US-1.1

**TC-T2.07** DEFAULT → .py创建 = ALLOWED/AUTO级别可放行
- **前置**: guard = PermissionGuard(PermissionLevel.DEFAULT)
- **步骤**: check(ProposedAction(FILE_CREATE, "utils/helper.py"))
- **预期**: outcome ∈ {ALLOWED, PROMPT}; 匹配 R002 规则
- **优先级**: P0 | **对应US**: US-1.2

**TC-T2.08** DEFAULT → .env修改 = PROMPT
- **前置**: guard = PermissionGuard(PermissionLevel.DEFAULT)
- **步骤**: check(ProposedAction(FILE_MODIFY, ".env"))
- **预期**: outcome == PROMPT; requires_confirmation == True; risk_score >= 0.7
- **优先级**: P0 | **对应US**: US-1.2

**TC-T2.09** DEFAULT → credentials修改 = PROMPT
- **前置**: guard = PermissionGuard(PermissionLevel.DEFAULT)
- **步骤**: check(ProposedAction(FILE_MODIFY, "credentials.json"))
- **预期**: outcome == PROMPT; risk_score >= 0.9
- **优先级**: P0 | **对应US**: US-1.2

**TC-T2.10** DEFAULT → rm命令 = PROMPT
- **前置**: guard = PermissionGuard(PermissionLevel.DEFAULT)
- **步骤**: check(ProposedAction(SHELL_EXECUTE, "rm -rf /tmp/cache"))
- **预期**: outcome == PROMPT; risk_score >= 0.9
- **优先级**: P0 | **对应US**: US-1.2

**TC-T2.11** DEFAULT → sudo命令 = PROMPT
- **前置**: guard = PermissionGuard(PermissionLevel.DEFAULT)
- **步骤**: check(ProposedAction(SHELL_EXECUTE, "sudo apt update"))
- **预期**: outcome == PROMPT; risk_score 接近 1.0
- **优先级**: P0 | **对应US**: US-1.2

**TC-T2.12** DEFAULT → 正常读取 = ALLOWED
- **前置**: guard = PermissionGuard(PermissionLevel.DEFAULT)
- **步骤**: check(ProposedAction(FILE_READ, "README.md"))
- **预期**: outcome == ALLOWED
- **优先级**: P0 | **对应US**: US-1.2

**TC-T2.13** AUTO → 安全操作(pip list) = ALLOWED
- **前置**: guard = PermissionGuard(PermissionLevel.AUTO)
- **步骤**: check(ProposedAction(SHELL_EXECUTE, "pip list"))
- **预期**: outcome == ALLOWED; 白名单匹配或 auto_classify 低分
- **优先级**: P1 | **对应US**: US-1.3

**TC-T2.14** AUTO → 可疑URL = PROMPT
- **前置**: guard = PermissionGuard(PermissionLevel.AUTO)
- **步骤**: check(ProposedAction(NETWORK_REQUEST, "http://unknown-site.xyz/data"))
- **预期**: outcome == PROMPT; auto_classify 返回较高风险分
- **优先级**: P1 | **对应US**: US-1.3

**TC-T2.15** BYPASS → 全部 ALLOWED
- **前置**: guard = PermissionGuard(PermissionLevel.BYPASS)
- **步骤**:
  1. check(ProposedAction(SHELL_EXECUTE, "rm -rf /")) → ALLOWED
  2. check(ProposedAction(FILE_DELETE, "/etc/passwd")) → ALLOWED
  3. check(ProposedAction(FILE_MODIFY, ".env")) → ALLOWED
- **预期**: 全部 ALLOWED
- **优先级**: P1 | **对应US**: US-1.4

**TC-T2.16** BYPASS → 审计仍记录
- **前置**: guard = PermissionGuard(PermissionLevel.BYPASS, audit_log=True)
- **步骤**: 执行5次任意 check()
- **预期**: get_audit_log() 返回5条; 每条 guard_level == BYPASS
- **优先级**: P1 | **对应US**: US-1.4

---

### T3: 规则引擎

**TC-T3.01** 默认30条规则加载
- **步骤**: guard = PermissionGuard(); 数量 len(guard.rules)
- **预期**: == 30
- **优先级**: P0 | **对应US**: US-2.1

**TC-T3.02** 覆盖8种ActionType
- **步骤**: 按 action_type 分组统计规则数
- **预期**: 每种 ≥1条; 总覆盖全部8种类型
- **优先级**: P0 | **对应US**: US-2.1

**TC-T3.03** add_rule 成功
- **步骤**: add_rule(custom); 再次计数
- **预期**: 规则数 == 31; 新规则在列表中
- **优先级**: P0 | **对应US**: US-2.2

**TC-T3.04** remove_rule 成功
- **步骤**: remove_rule("R009"); 计数
- **预期**: == 29; R009 不再存在
- **优先级**: P0 | **对应US**: US-2.2

**TC-T3.05** 移除后check行为变化
- **步骤**:
  1. check(.env修改) → PROMPT (R009生效时)
  2. remove_rule("R009")
  3. check(.env修改) → 回退到通用规则(R011)
- **预期**: 两次决策可能不同(取决于R011的级别)
- **优先级**: P0 | **对应US**: US-2.2

**TC-T3.06** export/import roundtrip
- **步骤**: export_rules() → import_rules(new_guard) → 对比
- **预期**: 规则数量和关键属性一致
- **优先级**: P1 | **对应US**: US-2.2

**TC-T3.07** Glob *.py 匹配
- **步骤**: 模式 `"*.py"` vs target `"src/utils/helper.py"`
- **预期**: 匹配成功
- **优先级**: P1 | **对应US**: US-2.3

**TC-T3.08** Glob 递归匹配
- **步骤**: 模式 `"src/**/*.py"` vs target `"src/core/engine.py"`
- **预期**: 匹配成功
- **优先级**: P1 | **对应US**: US-2.3

**TC-T3.09** 前缀匹配 Shell
- **步骤**: 模式 `"git "` vs target `"git status --short"`
- **预期**: 匹配成功
- **优先级**: P1 | **对应US**: US-2.3

**TC-T3.10** 正则匹配
- **步骤**: 模式 `r"rm\s+-` vs target `"rm -rf /tmp"`
- **预期**: 匹配成功
- **优先级**: P1 | **对应US**: US-2.3

**TC-T3.11** 多规则取最严格
- **步骤**: 同时匹配 R002(AUTO) 和 R005(DEFAULT) 的操作
- **预期**: 取更严格的结果(即需要更高权限级别)
- **优先级**: P1 | **对应US**: US-2.3

**TC-T3.12** 无匹配兜底
- **步骤**: 自定义一个不匹配任何规则的 ActionType+target
- **预期**: 有明确的兜底决策(非崩溃); 可能是 DEFAULT 级别的通用处理
- **优先级**: P0 | **对应US**: US-2.1

**TC-T3.13** .env 高风险分
- **步骤**: 检查 FILE_MODIFY ".env" 的风险评分
- **预期**: risk_score >= 0.7 (来自 R009.risk_boost)
- **优先级**: P0 | **对应US**: US-1.2

**TC-T3.14** credentials 最高风险
- **步骤**: 检查 FILE_MODIFY "credentials.json"
- **预期**: risk_score >= 0.9
- **优先级**: P0 | **对应US**: US-1.2

**TC-T3.15** rm/sudo 极高风险
- **步骤**: SHELL_EXECUTE "sudo rm -rf /"
- **预期**: risk_score >= 0.95
- **优先级**: P0 | **对应US**: US-1.2

**TC-T3.16** PyPI 低风险
- **步骤**: NETWORK_REQUEST "https://pypi.org/simple/requests/"
- **预期**: risk_score < 0.3 (R023)
- **优先级**: P1 | **对应US**: US-2.1

**TC-T3.17** Git只读低风险
- **步骤**: GIT_OPERATION "git log --oneline -10"
- **预期**: risk_score < 0.2 (R026)
- **优先级**: P1 | **对应US**: US-2.1

**TC-T3.18** 禁用规则跳过
- **步骤**: 将某条规则 enabled=False; 执行匹配该规则的操作
- **预期**: 该规则不影响决策结果
- **优先级**: P2 | **对应US**: US-2.2

---

### T4: AI自动分类器

**TC-T4.01** 分类器返回范围 [0.0, 1.0]
- **步骤**: 对多个不同操作调用 auto_classify()
- **预期**: 所有返回值 ∈ [0.0, 1.0]
- **优先级**: P0 | **对应US**: US-1.3

**TC-T4.02** 低风险操作 score < 0.3
- **步骤**: auto_classify(读普通文件、git status、ls目录)
- **预期**: score < 0.3
- **优先级**: P1 | **对应US**: US-1.3

**TC-T4.03** 中风险 0.3-0.7
- **步骤**: auto_classify(修改源码、创建新文件、网络请求)
- **预期**: 0.3 ≤ score < 0.7
- **优先级**: P1 | **对应US**: US-1.3

**TC-T4.04** 高风险 score ≥ 0.7
- **步骤**: auto_classify(rm命令、sudo、修改.env、删除重要文件)
- **预期**: score ≥ 0.7
- **优先级**: P1 | **对应US**: US-1.3

**TC-T4.05** 目标敏感度维度
- **步骤**: 比较 "config.py" vs "secret_key.pem" 的敏感度得分
- **预期**: secret_key.pem 得分显著更高
- **优先级**: P1 | **对应US**: US-1.3

**TC-T4.06** 操作破坏性维度
- **步骤**: 比较 "echo hello" vs "rm -rf /" 的破坏性得分
- **预期**: rm -rf 得分显著更高
- **优先级**: P1 | **对应US**: US-1.3

**TC-T4.07** 白名单直接放行
- **步骤**: 将 "python -m pytest" 加入白名单后 check
- **预期**: ALLOWED 且 confidence 高
- **优先级**: P1 | **对应US**: US-1.3

**TC-T4.08** 白名单管理
- **步骤**: add_whitelist()/remove_whitelist()/get_whitelist()
- **预期**: 增删查正常工作
- **优先级**: P2 | **对应US**: US-1.3

**TC-T4.09** 上下文合理性加分
- **步骤**: 同一操作在有合理 metadata vs 无 metadata 时对比
- **预期**: 有上下文的可能获得更低风险分
- **优先级**: P2 | **对应US**: US-1.3

**TC-T4.10** 来源可信度影响
- **步骤**: source_role_id="architect" vs "unknown-role" 对比
- **预期**: 已知角色可能有不同评分
- **优先级**: P2 | **对应US**: US-1.3

**TC-T4.11** 空内容分类器
- **步骤**: auto_classify(ProposedAction())
- **预期**: 返回默认值(可能是 0.5 或其他合理默认)，不崩溃
- **优先级**: P0 | **对应US**: US-5.1

**TC-T4.12** 特殊字符不影响分类
- **步骤**: auto_classify(target含 emoji/中文/XML特殊字符)
- **预期**: 正常返回数值，无异常
- **优先级**: P1 | **对应BS**: BS-01

---

### T5: 审计日志

**TC-T5.01** check产生审计条目
- **前置**: audit_log=True
- **步骤**: 调用1次 check(); get_audit_log()
- **预期**: 日志数 == 1; 条目字段完整
- **优先级**: P0 | **对应US**: US-3.1

**TC-T5.02** 条目完整性
- **步骤**: 检查最近一条审计日志的所有字段
- **预期**: entry_id, action, decision, duration_ms, guard_level, timestamp 都存在
- **优先级**: P0 | **对应US**: US-3.1

**TC-T5.03** duration_ms 非负
- **步骤**: 多次检查 duration_ms
- **预期**: 均 >= 0; 大多数 < 100ms
- **优先级**: P0 | **对应US**: US-3.1

**TC-T5.04** 按 outcome 过滤
- **步骤**: 执行混合操作; get_audit_log(outcome=DENIED)
- **预期**: 仅包含 DENIED 结果的条目
- **优先级**: P0 | **对应US**: US-3.1

**TC-T5.05** 按 action_type 过滤
- **步骤**: get_audit_log(action_type=SHELL_EXECUTE)
- **预期**: 仅包含 SHELL 类型
- **优先级**: P1 | **对应US**: US-3.1

**TC-T5.06** 时间范围过滤
- **步骤**: get_audit_log(since=t1, until=t2)
- **预期**: 仅返回 [t1, t2] 区间内的条目
- **优先级**: P1 | **对应US**: US-3.1

**TC-T5.07** 按 worker_id 过滤
- **步骤**: 用不同 worker_id 执行操作; 过滤
- **预期**: 仅返回指定 worker 的记录
- **优先级**: P1 | **对应US**: US-3.1

**TC-T5.08** limit 限制
- **步骤**: 执行50次; get_audit_log(limit=10)
- **预期**: 返回 <= 10 条
- **优先级**: P1 | **对应US**: US-3.1

**TC-T5.09** audit_log=False
- **前置**: PermissionGuard(audit_log=False)
- **步骤**: 执行多次 check(); get_audit_log()
- **预期**: 返回空列表或 None
- **优先级**: P2 | **对应US**: US-3.1

**TC-T5.10** 安全报告结构
- **步骤**: get_security_report()
- **预期**: 返回字典含 total_checks, allowed, denied, prompted, escalated, avg_risk_score
- **优先级**: P1 | **对应US**: US-3.2

**TC-T5.11** 报告数值一致性
- **步骤**: allowed + denied + prompted + escalated
- **预期**: == total_checks
- **优先级**: P1 | **对应US**: US-3.2

**TC-T5.12** top_denied 排序
- **步骤**: 触发多种被拒操作; 查看 top_denied_actions
- **预期**: 按拒绝次数或风险分降序排列
- **优先级**: P2 | **对应US**: US-3.2

**TC-T5.13** 连续调用日志递增
- **步骤**: 循环N次check(); 每次检查日志长度
- **预期**: 1, 2, 3, ..., N 递增
- **优先级**: P0 | **对应US**: US-3.1

**TC-T5.14** 日志时间排序
- **步骤**: 快速连续执行多次; 检查日志时间戳
- **预期**: 按时间升序排列
- **优先级**: P1 | **对应US**: US-3.1

---

### T6: 边界与异常

**TC-T6.01** 空 ProposedAction
- **步骤**: check(ProposedAction())
- **预期**: 返回有效 Decision; 不抛异常
- **优先级**: P0 | **对应US**: US-5.1

**TC-T6.02** 空目标字符串
- **步骤**: check(ProposedAction(FILE_READ, ""))
- **预期**: 有效 Decision; 可能 DENIED 或 ALLOWED 但不崩溃
- **优先级**: P0 | **对应US**: US-5.1

**TC-T6.03** None 字段
- **步骤**: ProposedAction 中部分字段显式传 None
- **预期**: 使用默认值; 不崩溃
- **优先级**: P0 | **对应US**: US-5.1

**TC-T6.04** 超长路径
- **步骤**: target = "a/" * 500 + "file.py"; check(...)
- **预期**: 不崩溃; 能完成检查
- **优先级**: P1 | **对应BS**: BS-02

**TC-T6.05** 路径遍历检测
- **步骤**: target = "../../../etc/passwd"; check(FILE_READ, target)
- **预期**: 风险评分提升 或 标记为可疑
- **优先级**: P0 | **对应BS**: BS-03

**TC-T6.06** Unicode中文路径
- **步骤**: target = "/项目/代码/用户数据.csv"; check(FILE_READ, target)
- **预期**: 正常处理; 不乱码
- **优先级**: P1 | **对应BS**: BS-01

**TC-T6.07** 连续重复提交
- **步骤**: 同一动作快速提交20次
- **预期**: 每次独立检查; 产生20条审计日志
- **优先级**: P1 | **对应BS**: BS-04

**TC-T6.08** 级别切换即时生效
- **步骤**:
  1. set_level(PLAN); check(创建文件) → DENIED
  2. set_level(BYPASS); check(创建文件) → ALLOWED
- **预期**: 第二次立即放行
- **优先级**: P0 | **对应BS**: BS-07

**TC-T6.09** set_level API
- **步骤**: set_level(每种级别); 检查 current_level
- **预期**: 立即切换成功
- **优先级**: P0 | **对应US**: US-1.1~1.4

**TC-T6.10** 重复 add_rule
- **步骤**: 两次添加相同 rule_id 的规则
- **预期**: 抛异常 or 覆盖 or 去重（任何一种明确行为）
- **优先级**: P1 | **对应US**: US-2.2

**TC-T6.11** 移除不存在规则
- **步骤**: remove_rule("NONEXISTENT")
- **预期**: 不崩溃; 返回 False 或忽略
- **优先级**: P1 | **对应US**: US-2.2

**TC-T6.12** 空规则集初始化
- **步骤**: PermissionGuard(rules=[])
- **预期**: 可正常工作; 使用内置兜底逻辑
- **优先级**: P1 | **对应US**: US-2.1

**TC-T6.13** risk_score 边界 0.0 和 1.0
- **步骤**: 验证极端值的决策结果合理
- **预期**: 0.0 → 可能ALLOWED; 1.0 → 可能PROMPT/DENIED
- **优先级**: P1 | **对应US**: US-1.3

**TC-T6.14** 特殊字符安全
- **步骤**: target 含 `<script>`, `' OR 1=1`, `\x00`
- **预期**: 不注入; 当作普通字符串处理
- **优先级**: P1 | **对应BS**: BS-01

**TC-T6.15** 大规模规则性能
- **步骤**: 加载1000+自定义规则; 执行单次 check
- **预期**: 耗时 < 100ms (宽松阈值)
- **优先级**: P2 | **对应BS**: BS-06

---

## Phase 2: 集成测试 (IT)

### IT1: Guard + Worker

**TC-IT1.01** Worker.execute_with_guard 基本流程
- **前置**: Guard(DEFAULT) + Worker + TaskDefinition
- **步骤**: worker.execute_with_guard(task, guard)
- **预期**: 正常执行; 结果中包含权限相关信息
- **优先级**: P0 | **对应US**: US-4.1

**TC-IT1.02** ALLOWED 操作执行成功
- **前置**: 任务仅包含读取操作
- **步骤**: execute_with_guard
- **预期**: success=True; output 非空
- **优先级**: P0 | **对应US**: US-4.1

**TC-IT1.03** DENIED 操作跳过
- **前置**: 任务包含删除操作(PLAN模式)
- **步骤**: execute_with_guard
- **预期**: 删除操作未执行; errors 中有相关记录
- **优先级**: P0 | **对应US**: US-4.1

**TC-IT1.04** PROMPT 操作暂停
- **前置**: 任务包含 .env 修改(DEFAULT模式)
- **步骤**: execute_with_guard 带 prompt_callback
- **预期**: 回调被触发; 用户确认后继续
- **优先级**: P1 | **对应US**: US-4.1

**TC-IT1.05** 被拒操作隔离
- **前置**: 5个操作序列 [读, 写, 删, 读, 写]; 删除被DENY
- **步骤**: execute_with_guard
- **预期**: 读1✅ 写2✅ 删❌ 读4✅ 写5✅
- **优先级**: P1 | **对应US**: US-4.1

**TC-IT1.06** 多Worker共享Guard
- **前置**: 1个Guard实例 + 3个Worker
- **步骤**: 并行执行任务
- **预期**: 审计日志包含3个worker的操作; 共享规则集
- **优先级**: P1 | **对应US**: US-4.1

**TC-IT1.07** WorkerResult 含权限信息
- **步骤**: 检查 result 中的 permission_decisions 字段
- **预期**: 包含每次操作的决策摘要
- **优先级**: P1 | **对应US**: US-4.1

**TC-IT1.08** Guard未配置降级
- **前置**: Coordinator 未传入 guard (guard=None)
- **步骤**: execute_plan
- **预期**: 正常执行(全ALLOWED降级); 不崩溃
- **优先级**: P2 | **对应US**: US-4.1

---

### IT2: Guard + Consensus 联动

**TC-IT2.01** ESCALATED → Scratchpad CONFLICT
- **步骤**: 触发 ESCALATED 决策; 检查 scratchpad
- **预期**: 新增 CONFLICT 条目; 内容包含操作详情
- **优先级**: P2 | **对应US**: US-4.2

**TC-IT2.02** Coordinator 发现升级
- **步骤**: coordinator._detect_escalations()
- **预期**: 返回待处理的 ESCALATED 列表
- **优先级**: P2 | **对应US**: US-4.2

**TC-IT2.03** 共识通过→临时放行
- **步骤**: 共识投票通过; 重新提交操作
- **预期**: 本次 ALLOWED
- **优先级**: P2 | **对应US**: US-4.2

**TC-IT2.04** 共识未通过→保持拒绝
- **步骤**: 共识投票否决
- **预期**: 保持 DENIED/PROMPT
- **优先级**: P2 | **对应US**: US-4.2

---

### IT3: Guard + Coordinator

**TC-IT3.01** Coordinator 注入 Guard
- **步骤**: Coordinator(permission_guard=guard)
- **预期**: coordinator.permission_guard == guard
- **优先级**: P0 | **对应US**: US-4.1

**TC-IT3.02** execute_plan 全流程
- **步骤**: 完整 plan_task → spawn_workers → execute_plan 流程
- **预期**: 每步操作都经过 guard.check()
- **优先级**: P0 | **对应US**: US-4.1

**TC-IT3.03** 报告含安全摘要
- **步骤**: generate_report()
- **预期**: 报告包含安全统计信息(检查次数/拦截次数等)
- **优先级**: P1 | **对应US**: US-3.2

---

## Phase 3: E2E测试

**TC-E2E-1** 旅程A: 安全开发工作流
- **场景**: 8步混合操作(读/写/确认/push)
- **预期**: 3次PROMPT被确认; 0次DENIED; 最终成功
- **优先级**: P0

**TC-E2E-2** 旅程B: PLAN预览
- **场景**: PLAN模式下完整多角色协作
- **预期**: 所有写操作DENIED; 读操作ALLOWED; 审计日志完整
- **优先级**: P1

**TC-E2E-3** 旅程C: 安全事件调查
- **场景**: 执行操作后查看报告和审计日志
- **预期**: 能定位到具体操作和决策原因
- **优先级**: P1

**TC-E2E-4** 100次操作压力测试
- **场景**: 快速循环100次不同类型操作
- **预期**: 无崩溃; 日志==100; 耗时<5s
- **优先级**: P1

**TC-E2E-5** 5角色+权限完整协作流
- **场景**: 5个Worker各执行3-5个操作
- **预期**: 每个操作经过权限检查; 结果符合预期
- **优先级**: P1

**TC-E2E-6** 动态热更新规则
- **场景**: 运行中 add_rule/remove_rule
- **预期**: 后续操作立即受新规则影响
- **优先级**: P2

**TC-E2E-7** 级别动态切换
- **场景**: PLAN → DEFAULT → AUTO → BYPASS → DEFAULT
- **预期**: 每次切换后行为立即改变
- **优先级**: P2

**TC-E2E-8** 全量审计导出验证
- **场景**: 大量操作后 export/import 审计数据
- **预期**: 数据完整性一致
- **优先级**: P2

---

## 用例统计总表

| 阶段 | 模块 | 用例数 | P0 | P1 | P2 |
|------|------|--------|----|----|-----|
| L1单元 | T1 数据模型 | 10 | 7 | 3 | 0 |
| L1单元 | T2 4级行为 | 16 | 12 | 4 | 0 |
| L1单元 | T3 规则引擎 | 18 | 9 | 8 | 1 |
| L1单元 | T4 AI分类器 | 12 | 2 | 8 | 2 |
| L1单元 | T5 审计日志 | 14 | 7 | 6 | 1 |
| L1单元 | T6 边界异常 | 15 | 6 | 8 | 1 |
| L2集成 | IT1 Guard+Worker | 8 | 4 | 3 | 1 |
| L2集成 | IT2 Guard+Consensus | 4 | 0 | 0 | 4 |
| L2集成 | IT3 Guard+Coordinator | 3 | 2 | 1 | 0 |
| L3端到端 | E2E 旅程测试 | 8 | 2 | 4 | 2 |
| **总计** | | **108** | **51** | **45** | **12** |
