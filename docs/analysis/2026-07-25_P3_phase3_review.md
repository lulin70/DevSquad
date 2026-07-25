# Phase 3 推进评审共识 — 质量补强 + 用户模拟 E2E

> **文档类型**: V4.3.0 Phase 3 7-Role 评审共识
> **创建日期**: 2026-07-25
> **基线版本**: V4.2.9 (Phase 2 已完成 commit `d440c5f`)
> **目标**: 完成 Phase 3.1-3.5 + 用户模拟 E2E，达成 V4.2.9 → V4.3.0 出口条件
> **关联**: [V4.3.0_ROADMAP.md §6](../planning/V4.3.0_ROADMAP.md) | [P1-8 评审](./2026-07-25_P1-8_output_validator_review.md)

---

## 一、范围与门禁

### 1.1 任务清单（ROADMAP §6.1 + 用户决策新增 3.5 用户模拟 E2E）

| 任务 | 文件路径 | 现状 | 目标 |
|------|---------|------|------|
| 3.1 增强 `check_async_coverage.py` | `scripts/check_async_coverage.py` | 仅 AST 扫描 + 文本报告 | +Markdown 报告 +阈值门禁 +单元测试 +忽略列表 |
| 3.2 新建红队用例库 | `tests/security/red_team.py` | 不存在 | ≥20 跨模块用例，4 类场景（注入/越权/数据泄露/拒绝服务） |
| 3.3 增强 `DispatchAuditLogger` 审计留痕 | `scripts/collaboration/dispatch_audit.py` | HMAC + verify_chain 已有 | +Markdown 导出 +按事件类型/时间查询 +篡改检测单测 |
| 3.4 让 E2E-07 脱 xfail | `scripts/collaboration/five_axis_consensus.py` | 缺 `evaluate(artifacts)` API | +`evaluate()` +`FiveAxisEvaluationResult` +Markdown 报告章节 |
| 3.5 AI 模拟用户旅程 E2E（新增） | `tests/e2e/test_real_user_journey.py` | 不存在 | PM/开发/运维 3 角色 × 旅程 E2E + NPS 报告 |
| 3.6 SKILL.md + CHANGELOG + ROADMAP 同步 | 多文件 | 待更新 | 文档一致性 30+/30+ PASS |

### 1.2 门禁（ROADMAP §6.2）

- [ ] 现有模块覆盖率不下降
- [ ] 红队测试 4 类场景全部通过
- [ ] 审计链篡改测试通过
- [ ] CI 全绿（pytest + ruff + mypy + radon + version consistency）
- [ ] E2E 骨架测试累计 ≥5 个 pass（E2E-02/04/05/06/07）
- [ ] 用户模拟 E2E 3 角色全通过 + NPS 报告产出

---

## 二、7-Role 共识矩阵

| 角色 | 关键审查点 | 结论 |
|------|----------|------|
| Architect | 3.4 `evaluate(artifacts)` 不破坏现有 `compute_consensus(reviews)` API；新增 `FiveAxisEvaluationResult` dataclass 独立于 `ConsensusResult` | ✅ 同意：API 分离，向后兼容 |
| Security | 3.2 红队 4 类场景覆盖现有 8 模块（dispatcher/audit/validator/dep_check/gate_engine/auth/permission/llm_backend）；3.3 篡改检测必须包含 HMAC 失败 + 旧 SHA256 兼容双路径 | ✅ 同意：4 类 × 5 模块 ≥20 用例 |
| Tester | 3.1 单元测试覆盖 7 维度（提取/匹配/报告/阈值/忽略/JSON/Markdown）；3.5 NPS 报告含定量（完成率/耗时）+ 定性（痛点 top 3） | ✅ 同意：测试金字塔不破坏 |
| Coder | 3.4 `evaluate()` 默认 heuristic 评分（无 LLM 调用），支持 artifacts={"code": str, "tests": list, "docs": str}；复杂度 ≤C 级 | ✅ 同意：heuristic 实现，复杂度可控 |
| Reviewer | 3.6 SKILL.md 模块数 155→156（新增 `FiveAxisEvaluationResult` 不算新模块，是 5 轴评估扩展）；CHANGELOG 增 Phase 3 条目 | ✅ 同意：模块数不变，描述更新 |
| DevOps | 3.5 用户模拟 E2E 必须可在 CI 跑（无外部依赖）；3.6 ROADMAP §6.2 门禁全部打勾 | ✅ 同意：E2E 自包含，CI 可跑 |
| PM | 3.5 NPS 报告作为 V4.3.0 发布材料附件；3.6 ROADMAP §7.1 出口条件清单更新 | ✅ 同意：NPS 报告归档 `docs/release/V4.3.0_user_simulation_report.md` |

**共识达成**: 7/7 ✅，可进入实施。

---

## 三、3.1 check_async_coverage 增强设计

### 3.1.1 新增 API

```python
@dataclass
class CoverageReport:
    # ... 现有字段
    markdown_report: str = ""  # 新增

def generate_markdown(report: CoverageReport) -> str:
    """生成 Markdown 覆盖率报告。"""

def check_with_threshold(
    source_dir: Path,
    test_dir: Path,
    min_coverage_percent: float = 80.0,
    ignore: list[str] | None = None,
) -> tuple[CoverageReport, bool]:
    """带阈值的检查，返回 (report, passed)。"""
```

### 3.1.2 新增单元测试

文件: `tests/unit/test_async_coverage.py`（新建）

| 测试类 | 用例数 | 覆盖维度 |
|--------|------|---------|
| `TestExtractAsyncFunctions` | 3 | 提取 async/private/dunder |
| `TestExtractTestedNames` | 3 | 直接调用/属性访问/测试名 |
| `TestCheckAsyncCoverage` | 3 | 全覆盖/部分覆盖/全未覆盖 |
| `TestMarkdownReport` | 2 | 格式/空报告 |
| `TestThresholdCheck` | 3 | 通过/未通过/忽略列表 |

---

## 四、3.2 red_team.py 红队用例库设计

### 3.2.1 4 类场景 × 5 模块 ≥20 用例

| 类别 | 模块 | 用例 |
|------|------|------|
| **注入攻击** | InputValidator | RT-01 prompt injection "ignore previous" / RT-02 SQL injection / RT-03 shell injection |
| 注入攻击 | dispatch_hooks | RT-04 worker output contains code injection markers |
| 注入攻击 | output_validator | RT-05 LLM output with embedded prompt injection |
| **越权访问** | PermissionGuard | RT-06 BYPASS mode without dev flag / RT-07 AUTO mode destructive op |
| 越权访问 | DispatchRBAC | RT-08 user without role attempts admin dispatch |
| 越权访问 | unified_gate_engine | RT-09 P10 gate bypass attempt |
| **数据泄露** | output_validator | RT-10 OpenAI key leak / RT-11 JWT leak / RT-12 DB password leak |
| 数据泄露 | dispatch_audit | RT-13 audit log contains sensitive data / RT-14 chain tamper attempt |
| 数据泄露 | dependency_hallucination_checker | RT-15 hallucinated package with typo of popular lib |
| **拒绝服务** | AsyncCoordinator | RT-16 1000 parallel workers / RT-17 return_exceptions=True failure |
| 拒绝服务 | LLMCache | RT-18 cache flooding / RT-19 TTL bypass |
| 拒绝服务 | ContextCompressor | RT-20 1MB context input |

### 3.2.2 测试文件结构

```python
# tests/security/red_team.py
class RT01to05_InjectionAttacks(unittest.TestCase): ...
class RT06to09_PrivilegeEscalation(unittest.TestCase): ...
class RT10to15_DataLeakage(unittest.TestCase): ...
class RT16to20_DenialOfService(unittest.TestCase): ...
```

---

## 五、3.3 DispatchAuditLogger 增强设计

### 3.3.1 新增 API

```python
def export_markdown(self, limit: int = 100) -> str:
    """导出 Markdown 审计报告。"""

def query(
    self,
    event_type: str | None = None,
    since: float | None = None,
    until: float | None = None,
    user_id: str | None = None,
    limit: int = 100,
) -> list[AuditEntry]:
    """按条件查询审计条目。"""

def detect_tamper(self) -> list[AuditEntry]:
    """检测链中篡改条目（返回可疑条目列表，空列表表示无篡改）。"""
```

### 3.3.2 新增单元测试（扩展现有 `tests/test_dispatch_audit.py`）

| 测试类 | 用例数 | 覆盖维度 |
|--------|------|---------|
| `TestMarkdownExport` | 3 | 格式/空链/limit |
| `TestQuery` | 4 | event_type/since/user_id/组合 |
| `TestTamperDetection` | 3 | 无篡改/单条篡改/HMAC 失败 |

---

## 六、3.4 FiveAxisConsensusEngine.evaluate() 设计

### 3.4.1 新增 API

```python
@dataclass
class FiveAxisEvaluationResult:
    """5 轴评估结果（heuristic，无 LLM 调用）。"""
    correctness: float    # 0.0-1.0
    readability: float
    architecture: float
    security: float
    performance: float
    overall: float
    verdict: str          # APPROVE / CONDITIONAL / REJECT
    notes: dict[str, str] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """生成 Markdown 报告章节。"""

class FiveAxisConsensusEngine:
    def evaluate(
        self,
        artifacts: dict[str, Any],
        reviewer_id: str = "heuristic",
    ) -> FiveAxisEvaluationResult:
        """对 artifacts 做 5 轴 heuristic 评估。

        Args:
            artifacts: {"code": str, "tests": list[str], "docs": str}
                code 必填，tests/docs 可选。

        Returns:
            FiveAxisEvaluationResult，5 轴分数 + verdict + notes。
        """
```

### 3.4.2 Heuristic 评分规则

| 轴 | 评分逻辑 |
|----|---------|
| correctness | code 中含 `raise`/`assert`/`try-except` +0.2 each（cap 0.9）；无 `pass` 占位 +0.1 |
| readability | 行长 < 100 +0.2；含注释/docstring +0.3；命名 snake_case +0.2 |
| architecture | 含 `class`/`def` 分层 +0.3；模块化 import +0.2；无 God Class（>500 行）+0.2 |
| security | 无 `eval`/`exec`/`os.system` +0.3；无硬编码密钥 +0.3；输入校验 +0.2 |
| performance | 无嵌套循环 > 2 层 +0.2；无 O(n²) list in list +0.2；使用生成器 +0.1 |

### 3.4.3 E2E-07 验证

```python
engine = FiveAxisConsensusEngine()
result = engine.evaluate(artifacts={"code": "print('hello')"})
assert result.correctness is not None  # 不为 None 即可（数值）
assert result.readability is not None
assert result.architecture is not None
assert result.security is not None
assert result.performance is not None
```

---

## 七、3.5 AI 模拟用户旅程 E2E 设计

### 3.5.1 3 角色 × 旅程

| 角色 | 旅程 | 验证点 |
|------|------|--------|
| **PM** | 创建 PRD → 触发 dispatch → 查看报告 | dispatch 成功 + Markdown 报告含 7 角色章节 |
| **开发者** | 调用 SecuritySkill → 触发依赖扫描 → 查看 audit | 安全扫描触发 + audit chain 完整 |
| **运维** | 触发 P10 部署门禁 → 合规/违规场景 | 合规通过 + 违规阻断 |

### 3.5.2 NPS 报告

文件: `docs/release/V4.3.0_user_simulation_report.md`

| 维度 | 标准 | 实际 |
|------|------|------|
| 完成率 | ≥90% | 待测 |
| 平均耗时 | ≤5 分钟/角色 | 待测 |
| NPS | ≥8/10 | 待测 |
| 痛点 Top 3 | - | 待收集 |

### 3.5.3 测试文件

文件: `tests/e2e/test_real_user_journey.py`

```python
class TestPMJourney(unittest.TestCase): ...
class TestDeveloperJourney(unittest.TestCase): ...
class TestOpsJourney(unittest.TestCase): ...
```

---

## 八、3.6 文档同步清单

| 文件 | 更新内容 |
|------|---------|
| `SKILL.md` | Version History +v4.3.0-phase3；test 数 8040+ → 8100+；模块描述 #44 FiveAxis +evaluate() |
| `CHANGELOG.md` | 新增 V4.3.0 Phase 3 章节 |
| `docs/planning/V4.3.0_ROADMAP.md` | §6.2 门禁全部打勾；§7.1 出口条件打勾；§11 变更历史 +v1.2 |
| `docs/analysis/2026-07-25_P3_phase3_review.md` | 出口门禁全 ✅ |
| `docs/release/V4.3.0_user_simulation_report.md` | 新建 NPS 报告 |

---

## 九、推进顺序与验证

| 步骤 | 任务 | 验证 |
|------|------|------|
| 3.0 | 7-Role 评审文档（本文档） | ✅ 用户确认 |
| 3.1 | check_async_coverage 增强 + 单测 | pytest tests/unit/test_async_coverage.py ✅ |
| 3.2 | red_team.py 新建 | pytest tests/security/red_team.py ✅ |
| 3.3 | DispatchAuditLogger 增强 + 单测扩展 | pytest tests/test_dispatch_audit.py ✅ |
| 3.4 | FiveAxisConsensusEngine.evaluate() + E2E-07 脱 xfail | pytest tests/e2e/test_user_stories_skeleton.py::test_e2e_07 ✅ |
| 3.5 | 用户模拟 E2E + NPS 报告 | pytest tests/e2e/test_real_user_journey.py ✅ |
| 3.6 | 文档同步 | check_version_consistency.py 30+/30+ ✅ |
| 3.7 | 全量回归 | pytest + ruff + mypy + radon ✅ |
| 4.0 | V4.3.0 升级（VERSION + 全量文档） | check_doc_consistency.sh ✅ |
| 4.1 | Git commit + tag v4.3.0 + push | git log ✅ |

---

## 十、风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 3.4 heuristic 评分过于简单被误用 | 中 | 中 | notes 字段说明评分依据；Markdown 报告含 "heuristic, not LLM" 标注 |
| 3.5 用户模拟 E2E 无法真实模拟用户认知 | 高 | 中 | NPS 报告诚实标注 "AI 模拟旅程，非真实用户测试"；V4.3.1 补真实用户测试 |
| 3.2 红队用例破坏现有模块 | 低 | 高 | 用例只读不写，使用 Public API；mock 外部依赖 |
| 3.3 篡改检测误报 | 低 | 低 | 提供 `detect_tamper()` 独立于 `verify_chain()`，返回可疑列表而非布尔 |

---

> **文档状态**: Phase 3 评审完成 2026-07-25，7/7 共识达成
> **下一步**: 启动 3.1 实施
