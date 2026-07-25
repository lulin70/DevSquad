# V4.3.0 P1-7 DependencyHallucinationChecker — 7-Role 评审共识

**日期**: 2026-07-25
**阶段**: Phase 1（B 线 — SDLC 用户故事 #58 防 Slopsquatting）
**输入文档**:
- [V4.3.0_PRD.md §9.2 P1-7](../prd/V4.3.0_PRD.md)
- [V4.3.0_ARCHITECTURE.md §9.2](../architecture/V4.3.0_ARCHITECTURE.md)
- [V4.3.0_TEST_PLAN.md §11](../testing/V4.3.0_TEST_PLAN.md)
- [V4.3.0_ROADMAP.md §4](../planning/V4.3.0_ROADMAP.md)
- Slopsquatting 检测最佳实践调研报告（Security Role 输入，含 USENIX 2025 + arXiv:2605.17062 + CSA 2026）

---

## 一、需求边界（P1 — PM Role）

### 1.1 用户故事

> 作为使用 DevSquad 的开发者，我希望 AI 生成的代码在执行前自动校验 import 语句对应的包真实存在，以避免 Slopsquatting 供应链攻击，让我能放心使用 AI 输出。

### 1.2 范围（In Scope）

- 检测 Python `import` / `from ... import` 语句中的包名
- 检测 JavaScript/TypeScript `import ... from` / `require(...)` 语句中的包名
- 三级分类：`KNOWN_GOOD` / `UNKNOWN` / `SUSPICIOUS`
- 本地静态数据集（不调用 PyPI/npm API）
- 集成到 SecuritySkill + dispatch post-worker hook
- 默认 non-blocking（仅报告），可通过配置升级为 blocking

### 1.3 不做（Out of Scope — V4.4.0+）

- 不调用 PyPI/npm API 实时验证（V4.4.0 扩展，预留 hook）
- 不修改 InputValidator（复用而非修改）
- 不实现 LLM-based 语义检测（V4.4.0 扩展）
- 不阻断 dispatch（默认 non-blocking，仅报告 + 审计日志）

### 1.4 验收标准（与 PRD §9.2 P1-7 对齐）

1. `dependency_hallucination_checker.py` 实现，单元测试覆盖率 ≥80%（7 维度）
2. SecuritySkill 集成测试通过（`security_scan_dependencies(code)` 可调用）
3. dispatch pipeline post-worker hook 集成测试通过（零回归）
4. E2E-04 测试骨架 pass（给定幻觉包 import，检测并报警）
5. 红队测试 ≥10 条幻觉包用例
6. SKILL.md 模块数 +1，SecuritySkill 描述更新

---

## 二、架构设计（P2 — Architect Role）

### 2.1 模块定位

`scripts/collaboration/dependency_hallucination_checker.py` 作为 **SecuritySkill 扩展**，校验 AI 生成代码中的 import 语句对应真实存在的 PyPI/npm 包。

### 2.2 架构位置（与 ARCHITECTURE §9.2 一致）

```
[Dispatcher]
   ↓
[Workers 执行] → [post-worker hook] ← P1-7 集成点
   ↓                    │
[ConsensusEngine]       ▼
   ↓            DependencyHallucinationChecker
[post-dispatch hooks]   │
   ↓                    ▼
[ReportFormatter] → 用户可见报告
   └─ "安全检查"章节（P1-7）
```

### 2.3 复用策略（参考 deployment_compliance_checker.py 模式）

| 复用对象 | 复用方式 |
|---------|---------|
| `deployment_compliance_checker.py` | 数据类模式参考（ComplianceReport / Violation / ViolationSeverity） |
| `InputValidator` | 不修改，仅参考其模式匹配架构 |
| `OperationClassifier` | 不修改，参考其三级分类模式 |
| `UnifiedGateEngine` | 不集成（P1-7 是 post-worker hook，非 lifecycle gate） |

### 2.4 Skill 调用链（防幽灵功能核心）

```
SecuritySkill.scan_dependencies(code)
    ↓
DependencyHallucinationChecker.scan(code)
    ↓
DependencyScanResult { findings: list[DependencyFinding], summary }
    ↓
post-worker hook 自动触发（dispatch_hooks.py 新增 check_dependency_hallucination）
    ↓
Markdown 报告"安全检查"章节 + 审计日志
```

---

## 三、技术设计（P3 — Architect + Coder Role）

### 3.1 公共 API 签名

```python
# scripts/collaboration/dependency_hallucination_checker.py

class DependencyCategory(Enum):
    """Three-tier classification for imported packages."""
    KNOWN_GOOD = "known_good"      # In whitelist (Top-N or project lockfile)
    UNKNOWN = "unknown"            # Not in whitelist/blacklist, no heuristic hit
    SUSPICIOUS = "suspicious"      # In blacklist or heuristic hit (typo/confusion)

class DependencySeverity(Enum):
    """Severity levels for dependency findings."""
    INFO = "info"                  # KNOWN_GOOD
    WARNING = "warning"            # UNKNOWN
    CRITICAL = "critical"          # SUSPICIOUS

@dataclass
class DependencyFinding:
    """Single dependency finding."""
    package_name: str
    ecosystem: str                  # "pypi" | "npm"
    category: DependencyCategory
    severity: DependencySeverity
    import_statement: str           # Original import line
    line_number: int
    reason: str                     # Why this classification
    suggested_fix: str | None       # Suggested real package (if known)

@dataclass
class DependencyScanResult:
    """Result of dependency hallucination scan."""
    is_clean: bool                  # True if no SUSPICIOUS/UNKNOWN
    findings: list[DependencyFinding]
    summary: str
    stats: dict[str, int]           # {"known_good": N, "unknown": N, "suspicious": N}
    scan_duration_ms: float
    timestamp: str

def security_scan_dependencies(
    code: str,
    ecosystem: str = "auto",        # "pypi" | "npm" | "auto" (detect from code)
    blocking: bool = False,         # If True, SUSPICIOUS raises RuntimeError
) -> DependencyScanResult:
    """
    Scan code for dependency hallucination (Slopsquatting attack).

    Args:
        code: Source code to scan (Python or JavaScript/TypeScript)
        ecosystem: Package ecosystem; "auto" detects from code content
        blocking: If True, SUSPICIOUS findings raise RuntimeError instead of returning

    Returns:
        DependencyScanResult with findings and statistics

    Raises:
        RuntimeError: If blocking=True and SUSPICIOUS findings detected
    """
```

### 3.2 检测流水线（6 步，按优先级降序）

| Step | 检测项 | 输出 |
|------|--------|------|
| 1 | 精确匹配 `SUSPICIOUS_BLACKLIST`（53 跨模型幻觉集 + Socket 公开恶意包） | SUSPICIOUS |
| 2 | 精确匹配 `KNOWN_GOOD_WHITELIST`（Top-5000 PyPI + Top-2000 npm） | KNOWN_GOOD |
| 3 | Levenshtein 编辑距离 ≤2 接近 Top-1000 包 | SUSPICIOUS (typo) |
| 4 | 混淆规则匹配（两真实包名拼接，如 `react-codeshift`） | SUSPICIOUS (confusion) |
| 5 | 命名后缀模式匹配（`-helper`/`-utils`/`-sdk`/`-validator`/`-middleware`） | UNKNOWN (high-priority) |
| 6 | 以上皆未命中 | UNKNOWN |

**优先级顺序**: SUSPICIOUS > KNOWN_GOOD > UNKNOWN（安全优先，宁错杀不漏放）

### 3.3 本地静态数据集

文件位置：`scripts/collaboration/data/dependency_hallucination/`

| 文件 | 内容 | 大小预估 |
|------|------|---------|
| `known_good.json` | Top-5000 PyPI + Top-2000 npm 包名（含最低版本 + 发布年份） | ~150 KB |
| `suspicious.json` | 53 跨模型幻觉集 + Socket 公开恶意包 + 高频幻觉后缀模式 | ~10 KB |
| `top_targets.json` | Top-1000 包名（用于 Levenshtein 计算） | ~30 KB |

**fail-secure**: 数据集缺失或损坏时，所有非白名单包降级为 UNKNOWN，绝不 fail-open。

### 3.4 import 语句提取（正则）

**Python**:
```python
PATTERNS_PYTHON = [
    r"^\s*import\s+([a-zA-Z_][a-zA-Z0-9_]*)",           # import foo
    r"^\s*from\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s+import",   # from foo.bar import baz
]
```

**JavaScript/TypeScript**:
```python
PATTERNS_JS = [
    r"^\s*import\s+.*\s+from\s+['\"]([^'\"./]+)['\"]",  # import x from 'pkg'
    r"^\s*require\(\s*['\"]([^'\"./]+)['\"]\s*\)",       # require('pkg')
]
```

**注意**: 排除相对路径（`./` / `../`）和标准库模块（Python `os`/`sys`/`json` 等，Node.js `fs`/`path`/`http` 等）。

---

## 四、测试计划（P7 — Tester Role）

### 4.1 单元测试（7 维度，≥25 tests）

**文件**: `tests/unit/test_dependency_hallucination_checker.py`

| 维度 | 测试数 | 覆盖内容 |
|------|--------|---------|
| Happy Path | ≥8 | KNOWN_GOOD 包通过 / 三级分类正确 / 多 import 同时检测 |
| Error Case | ≥4 | 无效代码 / 空 code / 阻塞模式 SUSPICIOUS 抛 RuntimeError |
| Boundary | ≥4 | 空 import / 超长代码 / 单字符包名 / 跨生态检测 |
| Performance | ≥2 | 1000 行代码 <200ms / 数据集加载 <50ms |
| Configuration | ≥3 | ecosystem=auto / blocking=True/False / 自定义白名单 |
| Integration | ≥3 | SecuritySkill 集成 / dispatch hook 集成 / 报告渲染 |
| Security | ≥3 | 数据集损坏 fail-secure / 路径穿越 / 注入测试 |

### 4.2 红队测试（≥15 条，覆盖真实 + 合成案例）

**文件**: `tests/security/test_dep_hallucination_redteam.py`

| # | 包名 | 生态 | 期望分类 | 场景 |
|---|------|------|---------|------|
| 1 | `huggingface-cli` | PyPI | SUSPICIOUS | 真实幻觉，真实包为 `huggingface_hub[cli]` |
| 2 | `react-codeshift` | npm | SUSPICIOUS | 真实混淆，237 仓库中招 |
| 3 | `aws-cdk` | PyPI | SUSPICIOUS | 真实幻觉，真实包 `aws-cdk-lib` |
| 4 | `rest-framework` | PyPI | SUSPICIOUS | 真实幻觉，真实包 `djangorestframework` |
| 5 | `ccxt-mexc-futures` | PyPI | SUSPICIOUS | 真实恶意包 |
| 6 | `reqeusts` | PyPI | SUSPICIOUS | 经典 typosquat，Levenshtein=1 |
| 7 | `numppy` | PyPI | SUSPICIOUS | numpy 拼错 |
| 8 | `crossenv` | npm | SUSPICIOUS | cross-env 拼错 |
| 9 | `aws-helper-sdk` | PyPI | UNKNOWN(高优) | 高频幻觉后缀模式 |
| 10 | `fastapi-middleware` | PyPI | UNKNOWN(高优) | 高频幻觉后缀模式 |
| 11 | `jwt-secure-validator` | PyPI | UNKNOWN(高优) | 高频幻觉后缀模式 |
| 12 | `crypto-secure-hash` | PyPI | UNKNOWN(高优) | 高频幻觉后缀模式 |
| 13 | `@solana-launchpad/sdk` | npm | SUSPICIOUS | APT 实战包 |
| 14 | `express` | npm | KNOWN_GOOD | Top-N 包，应通过 |
| 15 | `requests` | PyPI | KNOWN_GOOD | Top-N 包，应通过 |

### 4.3 集成测试

**文件 1**: `tests/integration/test_security_skill_with_dep_check.py`（≥5 tests）
- SecuritySkill.scan_dependencies(code) 可调用
- 返回 DependencyScanResult 结构正确
- Markdown 报告包含"安全检查"章节

**文件 2**: `tests/integration/test_dispatch_with_dep_check.py`（≥5 tests）
- dispatch post-worker hook 自动触发
- 零回归（现有测试全绿）
- blocking 模式阻断 dispatch

### 4.4 E2E 测试

**文件**: `tests/e2e/test_user_stories_skeleton.py::test_e2e_04_dependency_check`
- 给定幻觉包 import，检测并报警
- 移除 `@pytest.mark.xfail` 标记
- 验证 DependencyScanResult.findings 包含 SUSPICIOUS 项

---

## 五、7-Role 共识投票

| Role | 投票 | 关键意见 |
|------|------|---------|
| **Architect** | ✅ APPROVE | 复用 deployment_compliance_checker 模式，数据类清晰，不修改 InputValidator |
| **PM** | ✅ APPROVE | 需求边界清晰，non-blocking 默认降低用户摩擦 |
| **Security** | ✅ APPROVE（含 1 项修订） | 三级分类正确；**修订**：fail-secure 必须明确文档化，数据集损坏时降级为 UNKNOWN 而非 KNOWN_GOOD |
| **Tester** | ✅ APPROVE | 7 维度 + 15 红队用例覆盖充分；E2E-04 骨架就绪 |
| **Coder** | ✅ APPROVE | 正则提取 + 哈希查表 O(1) + Levenshtein O(N) 性能可控 |
| **DevOps** | ✅ APPROVE（含 1 项修订） | post-worker hook 集成点清晰；**修订**：必须新增 `check_module_activation.py` 检查项 |
| **UI** | ✅ APPROVE | Markdown 报告"安全检查"章节符合现有报告风格 |

**加权共识得分**: (0.30×1 + 0.20×1 + 0.25×1 + 0.15×1 + 0.10×1) = **1.000**（7/7 APPROVE）

---

## 六、修订项追踪

| 修订项 | 负责人 | 状态 | 实现位置 |
|--------|--------|------|---------|
| Security 修订：fail-secure 文档化 | Coder | 待实现 | `dependency_hallucination_checker.py` 模块 docstring |
| DevOps 修订：check_module_activation.py 新增检查项 | DevOps | 待实现 | `scripts/check_module_activation.py` 添加 `dependency_hallucination_checker` |

---

## 七、推进计划（P8-P10）

| 阶段 | 任务 | 文件 | 验证 |
|------|------|------|------|
| P8.1 | TDD: 先写单元测试（fail） | `tests/unit/test_dependency_hallucination_checker.py` | pytest 全 fail |
| P8.2 | 实现模块 + 静态数据集 | `scripts/collaboration/dependency_hallucination_checker.py` + `data/` | pytest 全 pass |
| P8.3 | SecuritySkill 集成 | `skills/security/handler.py` 添加 `scan_dependencies` | 集成测试 pass |
| P8.4 | dispatch hook 集成 | `scripts/collaboration/dispatch_hooks.py` 新增 `check_dependency_hallucination` | 集成测试 pass + 零回归 |
| P9.1 | 红队测试 ≥15 条 | `tests/security/test_dep_hallucination_redteam.py` | 全 pass |
| P9.2 | E2E-04 脱 xfail | `tests/e2e/test_user_stories_skeleton.py` | E2E-04 pass |
| P9.3 | 全量回归 | - | 7843+ tests passed, 0 regression |
| P10.1 | 防幽灵验证 | - | 模块调用计数 > 0 + 报告章节可见 |
| P10.2 | 文档同步 | SKILL.md / CHANGELOG.md / ROADMAP.md | 一致性 30+/30+ |

---

## 八、变更历史

| 日期 | 版本 | 变更 | 负责人 |
|------|------|------|--------|
| 2026-07-25 | v1.0 | 初始创建；7-Role 评审共识 1.000；含 P1-P3-P7 生命周期阶段产出 | DevSquad Team |

---

> **文档状态**: 7-Role 共识达成（1.000），进入 P8 实现阶段
> **下一步**: TDD 实现 `dependency_hallucination_checker.py`
> **关联文档**: [V4.3.0_PRD.md §9.2](../prd/V4.3.0_PRD.md) | [V4.3.0_ARCHITECTURE.md §9.2](../architecture/V4.3.0_ARCHITECTURE.md) | [V4.3.0_TEST_PLAN.md §11](../testing/V4.3.0_TEST_PLAN.md) | [V4.3.0_ROADMAP.md §4](../planning/V4.3.0_ROADMAP.md)
