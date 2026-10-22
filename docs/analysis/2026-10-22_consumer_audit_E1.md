# V4.8.0 P1-E1 消费者审计——六项三态清单（已裁定）

> 文档类型：消费者审计（D4 治理件）| 日期：2026-10-22
> 依据：[执行计划](../planning/2026-10-20_value_proposal_execution_plan.md) §5.1 P1-E1（对象：teach / prototype / live-browser / meta-skill-layering / impeccable 词表 / taste-dials）
> 方法：逐项以仓库证据回答"谁在什么场景用"（实现位置 / 生产消费方 / 测试 / 文档 / 触达路径），据实给出 keep / freeze / remove 建议
> 状态：**已裁定（2026-10-22）**——裁定记录见执行计划 §10；裁定前用户追问消费前景（暂时无消费 vs 将来也不会有消费 + 是否符合整体方向），据前瞻性分析裁定如下

---

## 1. 审计方法

每项核查五个维度（全部为仓库事实，可复现命令见 §4）：

- **实现位置**：主实现文件与功能定位
- **生产消费方**：非测试代码中谁 import / 引用它（"被测试调用 ≠ 被用户需要"，方案文档 §2 原则）
- **测试**：自身测试文件
- **文档**：README×3 / QUICKSTART / SKILL.md / docs/ 的提及面
- **触达路径**：CLI 子命令 / REST 端点 / Python API / skill 系统

三态定义：**keep**（有真实消费面，继续维护）｜**freeze**（无消费证据但有激活价值或删除成本，冻结不投入）｜**remove**（无消费方且无激活路径，删除）。

## 2. 逐项审计

### 2.1 teach —— 建议 KEEP

| 维度 | 证据 |
|---|---|
| 实现 | [skills/teach/skill-manifest.yaml](../../skills/teach/skill-manifest.yaml)：onboarding 教学技能（角色协作 / 生命周期 / Iron Rules 入门） |
| 生产消费方 | [meta_skill_layering.py](../../scripts/collaboration/meta_skill_layering.py) 将其列为 foundation 层（注意：meta-skill-layering 本身无消费方，见 2.4） |
| 测试 | tests/test_teach_skill.py |
| 文档 | README×3 各 1 处；SKILL.md 列为 8 个 atomic sub-skills 之一 |
| 触达 | Python API `get_skill("teach")`；无 CLI 子命令 / REST 端点 |

**判断**：无终端用户直连证据，但（a）零维护成本的静态内容型 skill；（b）onboarding 定位与 V4.8.0 workflow-entry 主线（降低新用户门槛）方向一致；（c）删除会破坏 SKILL.md 的 sub-skills 声明与 meta_skill_layering 引用。

### 2.2 prototype —— 建议 FREEZE

| 维度 | 证据 |
|---|---|
| 实现 | [skills/prototype/skill-manifest.yaml](../../skills/prototype/skill-manifest.yaml)：快速原型生成（UI / logic / api） |
| 生产消费方 | meta_skill_layering 列为 evolution 层（同 2.1 的注意） |
| 测试 | tests/test_prototype_skill.py |
| 文档 | README×3 各 1 处；SKILL.md sub-skills 之一 |
| 触达 | Python API `get_skill("prototype")` |

**判断**：与"工作流常驻层"主线无直接关联，无消费证据；但与 teach 同构（skill 系统可触达、零维护成本、删除破坏文档面）。冻结——保留能力面但不投入，待主线（P2 缺陷台账）后再评估激活。

### 2.3 live-browser —— 建议 REMOVE

| 维度 | 证据 |
|---|---|
| 实现 | [dashboard_live_mode.py](../../scripts/collaboration/dashboard_live_mode.py)：`LiveBrowserMode` 会话式 UI review loop |
| 生产消费方 | **无**——全仓非测试代码零引用 |
| 测试 | tests/test_dashboard_live_mode.py（仅自身测试） |
| 文档 | 仅 docs/ROADMAP.md 有段落；README×3 / QUICKSTART / SKILL.md 零提及 |
| 触达 | **无** CLI 子命令 / REST 端点 / skill 注册 |

**判断**：六项中消费者证据最弱——无生产消费方、无触达路径、无用户文档面。删除影响面 = 自身测试文件 + CHANGELOG 历史记录（历史留痕不受影响）。

### 2.4 meta-skill-layering —— 建议 FREEZE

| 维度 | 证据 |
|---|---|
| 实现 | [meta_skill_layering.py](../../scripts/collaboration/meta_skill_layering.py)：`MetaSkillGrouper` 在扁平 skill_registry 上提供 6 层组织（文档 / 发现 / 渐进披露） |
| 生产消费方 | **无**——无人 import `MetaSkillGrouper`（它单向消费 teach / prototype，自身无下游） |
| 测试 | tests/test_meta_skill_layering.py（仅自身测试） |
| 文档 | 仅 docs/ROADMAP.md |
| 触达 | 无 CLI / API；纯 Python 内部模块 |

**判断**：与 live-browser 同为"无生产消费方"，但它有组织性价值主张（技能发现）且被两个真实 skill 的定位引用。倾向 freeze 而非 remove：若 P2 期间技能数量增长，分层发现可能被激活；若裁定 remove，其删除不破坏 teach / prototype 本体（依赖方向是它依赖别人）。

### 2.5 impeccable 词表（cli_command_classifier）—— 建议 FREEZE

| 维度 | 证据 |
|---|---|
| 实现 | [cli_command_classifier.py](../../scripts/collaboration/cli_command_classifier.py)：`CLICommandClassifier` 把 CLI 命令映射到 7 类词表（create / review / navigate / configure / execute / maintain / stop） |
| 生产消费方 | **无**——全仓非测试代码零 import（ROADMAP 所称"CLI 命令审计链路消费"未成立：scripts/cli*.py 与 api 路由均未接线） |
| 测试 | tests/test_cli_command_classifier.py（23-command 词表对齐测试，当前绿） |
| 文档 | docs/ROADMAP.md P2-UI-1（声称已落地——实际是"已实现未接线"） |
| 触达 | 无 CLI 子命令 / REST 端点 |

**判断**：已实现、已测试、未接线。与本次 R2 doc_command 门禁同属"命令治理"主题，存在低成本激活路径（如接入 doctor 子命令做拼写建议）；删除则丢弃一个已测试资产。建议 freeze 并在 P2 评估接线；或裁定后立即接线（≤ 半天工作量）。

**裁定后实施（2026-10-22）**：用户裁定升级为 P1 立即接线。已实施：`devsquad doctor --command WORD` 接入 `check_command_vocabulary()`（scripts/cli_doctor.py）——注册表归属检查（argparse 内省，与 R2 门禁同源）+ difflib 拼写近似 + impeccable 分类感知建议。测试 13 项新增于 tests/test_cli_doctor.py。本项由 FREEZE 转为**已接线激活**（首个生产消费方就位）。

### 2.6 taste-dials —— 建议 KEEP

| 维度 | 证据 |
|---|---|
| 实现 | [taste_dials.py](../../scripts/qa/taste_dials.py)：`TasteDials` 视觉设计阈值旋钮 |
| 生产消费方 | **有**——[uiux_analyzer.py](../../scripts/qa/uiux_analyzer.py) 与 [deterministic_rule_engine.py](../../scripts/qa/deterministic_rule_engine.py) 均 import；前者经 [scripts/qa/\_\_init\_\_.py](../../scripts/qa/__init__.py) 成为包公开 API，服务 ui-designer 角色的 uiux-audit 技能链 |
| 测试 | tests/test_taste_dials.py |
| 文档 | docs/ROADMAP.md；ui-designer 角色技能文档（uiux-audit/SKILL.md）含使用示例 |
| 触达 | 经 UI/UX 审计链（Python API）；无独立 CLI 子命令 |

**判断**：六项中唯一有真实生产消费链的模块（taste_dials → uiux_analyzer / rule_engine → ui-designer 审计）。删除会破坏 UI/UX 审计功能，不适用。

## 3. 汇总与建议

| # | 对象 | 生产消费方 | 触达路径 | 建议 | **裁定（2026-10-22）** | 删除影响面 |
|---|---|---|---|---|---|---|
| 1 | teach | meta_skill_layering 引用 | skill API | **KEEP** | ✅ KEEP | SKILL.md / README×3 / meta_skill_layering |
| 2 | prototype | meta_skill_layering 引用 | skill API | **FREEZE** | ✅ FREEZE | 同上 |
| 3 | live-browser | 无 | 无 | **REMOVE** | ✅ REMOVE | 仅自身测试 |
| 4 | meta-skill-layering | 无 | 无 | **FREEZE** | ✅ FREEZE | 仅自身测试（不影响 teach/prototype 本体） |
| 5 | impeccable 词表 | 无（未接线） | 无 | **FREEZE**（P2 评估接线） | ✅ **升级：P1 立即接线 doctor**（用户裁定） | 仅自身测试 |
| 6 | taste-dials | 有（qa 审计链） | Python API | **KEEP** | ✅ KEEP | UI/UX 审计链断裂 |

**裁定依据（前瞻性判定）**：仅 live-browser 一项判定"将来也不会有消费且不符合整体方向"（impeccable 借鉴实验，从未产品化；DevSquad ui-designer 走静态审计链；将来若需浏览器自动化会用 MCP browser 工具生态重做）。prototype 与 meta-skill-layering 属"激活条件目前不成立"而非"永不激活"——冻结零投入。teach 有贴主线的激活路径（workflow-entry 后的新用户教育）；taste-dials 有现有生产消费链。

**净效果（按裁定执行）**：删除 1 项（live-browser：1 模块 + 1 测试文件）；冻结 2 项（零维护投入）；保留 2 项；接线激活 1 项（impeccable 词表→doctor 命令拼写建议，P1 末位小 PR）。

## 4. 复现命令

```bash
# 反向依赖（以 live-browser 为例，其余同法替换模块名）
grep -rn "dashboard_live_mode\|LiveBrowserMode" scripts/ skills/ --include="*.py" | grep -v test_
grep -rn "MetaSkillGrouper\|meta_skill_layering" scripts/ skills/ --include="*.py" | grep -v test_
grep -rn "CLICommandClassifier\|cli_command_classifier" scripts/ skills/ --include="*.py" | grep -v test_
grep -rn "TasteDials\|taste_dials" scripts/ skills/ --include="*.py" | grep -v test_

# 文档提及面
grep -rni "teach\|prototype\|live.browser\|meta.skill\|impeccable\|taste.dial" README.md README-CN.md README-JP.md QUICKSTART.md SKILL.md
```

---

> **已裁定（2026-10-22）**：六项裁定记录于执行计划 §10。实施动作：①live-browser 删除随本 PR 落地；②impeccable 词表接线 doctor 走独立 P1 小 PR；③扩张冻结解除（D4 出口门通过）。
