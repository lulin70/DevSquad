# DevSquad 术语表 (GLOSSARY)

> **文档类型**: 纯术语表 (Pure Glossary)
> **来源理念**: Matt Pocock domain-modeling — CONTEXT.md as pure terminology reference
> **规则**: 仅术语定义，禁止实现细节。实现细节见 [SPEC.md](SPEC.md)。
> **最后更新**: 2026-07-15 (V4.1.0)

---

## 一、架构词汇 (Matt Pocock)

| 术语 | 定义 | 来源 |
|------|------|------|
| **Deep module** | 小接口 + 大实现，高 leverage + 高 locality。最佳模块设计。 | Matt codebase-design / John Ousterhout |
| **Shallow module** | 大接口 + 小实现，pass-through。应避免的设计。 | Matt codebase-design / John Ousterhout |
| **Seam** | 不编辑原地即可改变行为的位置。测试和重构的关键点。 | Matt codebase-design / Michael Feathers |
| **Deletion test** | 想象删除模块，若复杂度消失则为 pass-through（shallow）。用于识别冗余模块。 | Matt improve-codebase-architecture |
| **Red-capable** | 能在特定 bug 上变红的反馈循环。调试命令必须 red-capable 才有效。 | Matt diagnosing-bugs |
| **Tautological test** | 断言重算实现逻辑，永远通过但无价值。测试反模式。 | Matt tdd |
| **Grilling** | one-question-at-a-time 访谈法，带 recommended-answer。用于需求对齐。 | Matt grilling / grill-me / grill-with-docs |
| **ADR** | Architecture Decision Record。三准则全满足才写：1)影响多模块 2)有替代方案 3)未来可能被推翻。 | Matt domain-modeling |
| **GLOSSARY** | 纯术语表，禁止实现细节。与 SPEC.md 职责分离。 | Matt domain-modeling / CONTEXT.md |
| **No-op test** | 验证 skill/命令在无操作时正确返回无操作结果，而非报错。 | Matt writing-great-skills |
| **Progressive disclosure** | 信息分层呈现：先概览，按需展开细节。避免一次性信息过载。 | Matt writing-great-skills |
| **Vertical slice** | 端到端的功能切片（UI+逻辑+数据），而非水平分层。任务分解方式。 | Matt to-issues |
| **HITL** | Human-In-The-Loop。需要人类确认的步骤。 | Matt to-issues |
| **AFK** | Away-From-Keyboard。可异步执行的步骤。 | Matt to-issues |
| **Seams-up-front** | 在编码前先识别 seams（可变点）。测试先行的基础。 | Matt tdd |
| **Leading words** | SKILL.md 开头的动词词组，快速传达技能用途。 | Matt writing-great-skills |
| **Failure modes** | 技能可能失败的场景列表。SKILL.md 必备章节。 | Matt writing-great-skills |

---

## 二、UI/UX 设计词汇 (impeccable + taste-skill)

| 术语 | 定义 | 来源 |
|------|------|------|
| **Design Pillars** | 7 个设计支柱：Typography / Color / Spatial / Responsiveness / Interactions / Motion / UX writing。UI/UX 评估的词汇框架。 | impeccable |
| **Deterministic Rule** | 确定性检测规则，纯 if/else + AST 分析，不需要 LLM。共 46 条。 | impeccable |
| **Taste Dials** | 视觉品味旋钮（0.0-1.0）：DESIGN_VARIANCE / MOTION_INTENSITY / VISUAL_DENSITY。控制 UI 审计阈值。 | taste-skill |
| **PromptDials** | Prompt 调优旋钮（1-5）：VERBOSITY / CREATIVITY / RISK_TOLERANCE。控制 Worker prompt。与 TasteDials 职责分离。 | DevSquad (inspired by taste-skill) |
| **DESIGN.md** | 项目设计准则文档。UIUXAnalyzer 审计时加载作为上下文。 | impeccable PRODUCT+DESIGN |
| **PRODUCT.md** | 产品上下文文档（用户/目标/场景）。impeccable 的上下文协议。DevSquad 中由 PRD 覆盖。 | impeccable |
| **Anti-pattern Bans** | AI 前端反模式禁令（6 类）：border-left accent / gradient text / glassmorphism overuse / overused fonts / purple-blue gradient / nested cards。 | taste-skill |
| **OKLCH** | 感知均匀色彩空间，替代 sRGB。比 HSV 更符合人眼感知。 | taste-skill |
| **4pt grid** | 4 像素为基准的间距网格系统。语义间距：xs=4, sm=8, md=16, lg=24, xl=32。 | taste-skill |
| **Live browser mode** | 实时浏览器迭代模式，与设计稿实时对照。 | impeccable |
| **Craft** | impeccable 的创建命令，分阶段创建 UI。 | impeccable |
| **Polish** | impeccable 的优化命令，提升现有 UI 质量。 | impeccable |

---

## 三、DevSquad 词汇

| 术语 | 定义 | 来源 |
|------|------|------|
| **Consensus** | 五轴加权投票 + 否决权。7 角色达成共识的机制。 | DevSquad |
| **Gate** | 阶段门禁，证据驱动验收。P1-P11 每阶段有门禁。 | DevSquad |
| **Anchor** | 目标锚定，实时检测任务执行是否偏离原始目标。 | DevSquad V3.6.0 |
| **Worker** | 工作单元，每个角色一个实例，独立执行。 | DevSquad |
| **Scratchpad** | 共享记忆板，Worker 间实时信息交换。 | DevSquad |
| **DispatchResult** | 调度结果，包含 worker_results/consensus_records/errors 等。 | DevSquad |
| **Iron Rule** | 铁律，不可违反的规则。如"文档先行"、"失败即报告"。 | DevSquad |
| **Loop Engineering** | 五步闭环：Discovery → Handoff → Verification → Persistence → Scheduling。 | DevSquad V4.0.0 |
| **Adversarial Verify** | 红蓝对抗 + 裁判仲裁三阶段验证。 | DevSquad V4.0.0 |
| **DAG Visualizer** | Mermaid/JSON/DOT 三格式依赖图可视化。 | DevSquad V4.0.0 |
| **Autonomous Loop** | plan → dev → verify → fix 4 阶段自主迭代。 | DevSquad V4.0.0 |
| **Plugin Hot Loader** | 插件热加载，3 加载路径 + 路径穿越防护。 | DevSquad V4.0.0 |
| **SRP** | Single Responsibility Principle，单一职责原则。God Class 判断的可靠标准（而非行数/方法数阈值）。 | DevSquad lesson learned D13 |
| **Internal tool template** | 生命周期模板，跳过 P4/P5/P6/P11。用于内部工具开发。 | DevSquad V3.6.0 |

---

## 四、文档体系职责边界

| 文档 | 职责 | 禁止 |
|------|------|------|
| **GLOSSARY.md** (本文件) | 纯术语定义 | 实现细节、API 规范、代码示例 |
| **ADR** (`docs/adr/`) | 架构决策记录（三准则全满足） | 日常变更、无替代方案的决策 |
| **DESIGN.md** (`docs/spec/DESIGN.md`) | 项目设计准则（UI/UX 审计上下文） | 技术规范、模块清单 |
| **SPEC.md** (`docs/spec/SPEC.md`) | 技术规范（模块/API/数据模型） | 纯术语、设计准则 |

---

> **维护规则**: 每次新增术语时更新本文件。术语必须有明确的来源标注。
> **一致性检查**: CI 会检查 GLOSSARY.md 中的术语在 SPEC.md 和代码注释中的一致性。
