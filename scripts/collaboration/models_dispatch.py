#!/usr/bin/env python3
"""
协作系统数据模型 — 角色派发相关定义。

本模块包含角色权重、角色注册表（ROLE_REGISTRY）、角色别名解析以及
角色查询辅助函数，供 Coordinator / Dispatcher 进行角色匹配与派发使用。
"""

from dataclasses import dataclass, field

# V4.4.2 P1-1: Anti-ghost counter — incremented every time
# ``RoleDefinition.get_localized_prompt`` is called. Tests assert this
# counter > 0 after a dispatch to prove the i18n path is wired in.
_call_counter: int = 0

ROLE_WEIGHTS = {
    "architect": 1.5,
    "product-manager": 1.2,
    "security": 1.1,
    "tester": 1.0,
    "solo-coder": 1.0,
    "devops": 1.0,
    "ui-designer": 0.9,
}
"""Default voting weights by role for consensus decisions.

Higher weight means more influence in consensus voting.
Architect has highest weight (1.5) due to technical decision importance.
"""


@dataclass
class RoleDefinition:
    """Complete definition of a collaboration role.

    Contains all metadata needed for role matching, prompt generation,
    and Worker creation in the multi-agent system.

    Attributes:
        role_id: Unique identifier (e.g., "architect", "tester")
        name: Human-readable display name (e.g., "架构师")
        aliases: Alternative identifiers or abbreviations (e.g., ["arch"])
        prompt: System prompt / instruction template for this role
        keywords: List of keywords for automatic role matching
        weight: Default voting weight in consensus (e.g., 1.5 for architect)
        description: Short description of the role's responsibilities
        status: Role status ("core"=active, "planned"=future)
        prompt_i18n: V4.4.2 P1-1 — localized prompts keyed by lang code
            (e.g., {"en": "...", "ja": "..."}). ``zh`` falls back to
            ``prompt``. Empty dict preserves backward compatibility.
        name_i18n: V4.4.2 P1-1 — localized display names keyed by lang
            code. ``zh`` falls back to ``name``.

    Example:
        >>> role = RoleDefinition(
        ...     role_id="architect",
        ...     name="架构师",
        ...     aliases=["arch"],
        ...     prompt="你是系统架构师...",
        ...     keywords=["架构", "设计"],
        ...     weight=1.5,
        ... )
    """
    role_id: str
    name: str
    aliases: list[str]
    prompt: str
    keywords: list[str]
    weight: float
    description: str
    status: str = "core"
    # V4.4.2 P1-1: localized prompt/name. Default empty dict keeps the
    # dataclass backward compatible (existing callers that construct
    # RoleDefinition without these fields continue to work).
    prompt_i18n: dict[str, str] = field(default_factory=dict)
    name_i18n: dict[str, str] = field(default_factory=dict)

    def get_localized_prompt(self, lang: str) -> str:
        """Return the role prompt for the requested language.

        Lookup order:
        1. ``prompt_i18n[lang]`` if present
        2. ``self.prompt`` (the original Chinese prompt) for ``zh`` and
           any unrecognized lang — preserves backward compatibility.

        Increments the module-level ``_call_counter`` on every call so
        tests can verify the i18n code path is actually exercised.

        Args:
            lang: ISO language code ("zh", "en", "ja").

        Returns:
            Localized prompt string, or ``self.prompt`` as fallback.
        """
        global _call_counter
        _call_counter += 1
        if lang in self.prompt_i18n:
            return self.prompt_i18n[lang]
        return self.prompt

    def get_localized_name(self, lang: str) -> str:
        """Return the role display name for the requested language.

        ``zh`` and any unrecognized lang fall back to ``self.name``,
        preserving backward compatibility.

        Args:
            lang: ISO language code ("zh", "en", "ja").

        Returns:
            Localized name string, or ``self.name`` as fallback.
        """
        if lang in self.name_i18n:
            return self.name_i18n[lang]
        return self.name


ROLE_REGISTRY: dict[str, RoleDefinition] = {
    "architect": RoleDefinition(
        role_id="architect",
        name="架构师",
        aliases=["arch"],
        prompt="你是系统架构师。负责：\n1. 系统架构设计（分层、模块化、接口定义）\n2. 技术选型和评估\n3. 性能架构设计（缓存架构、CDN策略、分库分表方案）\n4. 安全架构设计（认证授权方案、加密策略、安全边界）\n5. 数据架构设计（数据模型、数据仓库架构、ETL架构）\n6. 输出：架构文档、技术方案、模块设计",
        keywords=[
            "架构",
            "设计",
            "选型",
            "性能",
            "模块",
            "接口",
            "微服务",
            "数据架构",
            "architecture",
            "design",
            "microservice",
            "module",
            "interface",
            "performance",
            "scalability",
            "system",
        ],
        weight=1.5,
        description="System design, tech stack, API design, performance/security/data architecture",
        status="core",
        prompt_i18n={
            "en": "You are a System Architect. Responsible for:\n1. System architecture design (layering, modularization, interface definition)\n2. Technology selection and evaluation\n3. Performance architecture design (caching architecture, CDN strategies, sharding schemes)\n4. Security architecture design (authentication/authorization schemes, encryption strategies, security boundaries)\n5. Data architecture design (data models, data warehouse architecture, ETL architecture)\n6. Output: architecture documents, technical proposals, module designs",
            "ja": "あなたはシステムアーキテクトです。担当：\n1. システムアーキテクチャ設計（レイヤリング、モジュール化、インターフェース定義）\n2. 技術選定と評価\n3. パフォーマンスアーキテクチャ設計（キャッシュアーキテクチャ、CDN戦略、シャーディング方式）\n4. セキュリティアーキテクチャ設計（認証・認可方式、暗号化戦略、セキュリティ境界）\n5. データアーキテクチャ設計（データモデル、データウェアハウスアーキテクチャ、ETLアーキテクチャ）\n6. 出力：アーキテクチャドキュメント、技術提案、モジュール設計",
        },
        name_i18n={"en": "Architect", "ja": "アーキテクト"},
    ),
    "product-manager": RoleDefinition(
        role_id="product-manager",
        name="产品经理",
        aliases=["pm"],
        prompt="你是产品经理。负责：\n1. 需求分析和PRD编写\n2. 用户故事和验收标准\n3. 竞品分析\n4. 输出：需求文档、用户故事、功能规格",
        keywords=[
            "需求",
            "PRD",
            "用户故事",
            "竞品",
            "验收",
            "体验",
            "功能",
            "requirement",
            "prd",
            "user story",
            "acceptance",
            "feature",
            "product",
            "specification",
        ],
        weight=1.2,
        description="Requirements analysis, user stories, acceptance criteria",
        status="core",
        prompt_i18n={
            "en": "You are a Product Manager. Responsible for:\n1. Requirements analysis and PRD writing\n2. User stories and acceptance criteria\n3. Competitive analysis\n4. Output: requirements documents, user stories, functional specifications",
            "ja": "あなたはプロダクトマネージャーです。担当：\n1. 要件分析とPRD作成\n2. ユーザーストーリーと受け入れ基準\n3. 競合分析\n4. 出力：要件ドキュメント、ユーザーストーリー、機能仕様",
        },
        name_i18n={"en": "Product Manager", "ja": "プロダクトマネージャー"},
    ),
    "tester": RoleDefinition(
        role_id="tester",
        name="测试专家",
        aliases=["test", "qa"],
        prompt="你是测试专家。负责：\n1. 测试策略和用例设计\n2. 自动化测试方案\n3. 质量评估和缺陷追踪\n4. 输出：测试计划、测试用例、质量报告",
        keywords=[
            "测试",
            "质量",
            "验收",
            "自动化",
            "性能测试",
            "缺陷",
            "门禁",
            "test",
            "quality",
            "qa",
            "automated",
            "coverage",
            "bug",
            "validation",
        ],
        weight=1.0,
        description="Test strategy, quality assurance, edge cases",
        status="core",
        prompt_i18n={
            "en": "You are a Test Expert. Responsible for:\n1. Test strategy and case design\n2. Automated testing solutions\n3. Quality assessment and defect tracking\n4. Output: test plans, test cases, quality reports",
            "ja": "あなたはテスト専門家です。担当：\n1. テスト戦略とケース設計\n2. 自動化テスト方案\n3. 品質評価と欠陥追跡\n4. 出力：テスト計画、テストケース、品質レポート",
        },
        name_i18n={"en": "Test Expert", "ja": "テスト専門家"},
    ),
    "solo-coder": RoleDefinition(
        role_id="solo-coder",
        name="独立开发者",
        aliases=["coder", "dev"],
        prompt="你是全栈开发者。负责：\n1. 功能实现和代码编写\n2. 代码审查与质量把关（风格一致性、最佳实践、设计模式合规）\n3. 性能优化实现（算法优化、内存优化、并发优化、SQL调优）\n4. 代码重构和优化\n5. Bug修复\n6. 数据迁移实现\n7. 输出：源代码、测试、技术文档",
        keywords=[
            "实现",
            "开发",
            "代码",
            "修复",
            "优化",
            "重构",
            "审查",
            "最佳实践",
            "implement",
            "develop",
            "code",
            "fix",
            "optimize",
            "refactor",
            "review",
            "debug",
        ],
        weight=1.0,
        description="Implementation, code review, performance optimization, refactoring",
        status="core",
        prompt_i18n={
            "en": "You are a Full-Stack Developer. Responsible for:\n1. Feature implementation and code writing\n2. Code review and quality control (style consistency, best practices, design-pattern compliance)\n3. Performance optimization implementation (algorithm optimization, memory optimization, concurrency optimization, SQL tuning)\n4. Code refactoring and optimization\n5. Bug fixing\n6. Data migration implementation\n7. Output: source code, tests, technical documentation",
            "ja": "あなたはフルスタック開発者です。担当：\n1. 機能実装とコード作成\n2. コードレビューと品質管理（スタイル一致性、ベストプラクティス、デザインパターン準拠）\n3. パフォーマンス最適化の実装（アルゴリズム最適化、メモリ最適化、並行最適化、SQLチューニング）\n4. コードリファクタリングと最適化\n5. バグ修正\n6. データ移行の実装\n7. 出力：ソースコード、テスト、技術ドキュメント",
        },
        name_i18n={"en": "Full-Stack Developer", "ja": "フルスタック開発者"},
    ),
    "ui-designer": RoleDefinition(
        role_id="ui-designer",
        name="UI设计师",
        aliases=["ui"],
        prompt="你是UI/UX设计师。负责：\n1. 界面设计和交互原型\n2. 设计系统和组件规范\n3. 视觉稿和设计交付\n4. 输出：设计稿、原型、设计规范",
        keywords=[
            "UI",
            "界面",
            "前端",
            "视觉",
            "交互",
            "原型",
            "设计",
            "ui",
            "interface",
            "frontend",
            "visual",
            "interaction",
            "prototype",
            "ux",
            "accessibility",
        ],
        weight=0.9,
        description="UX design, interaction logic, accessibility",
        status="core",
        prompt_i18n={
            "en": "You are a UI/UX Designer. Responsible for:\n1. Interface design and interaction prototypes\n2. Design systems and component specifications\n3. Visual mockups and design deliverables\n4. Output: design mockups, prototypes, design specifications",
            "ja": "あなたはUI/UXデザイナーです。担当：\n1. インターフェース設計とインタラクションプロトタイプ\n2. デザインシステムとコンポーネント仕様\n3. ビジュアルモックアップとデザイン成果物\n4. 出力：デザインモックアップ、プロトタイプ、デザイン仕様",
        },
        name_i18n={"en": "UI/UX Designer", "ja": "UI/UXデザイナー"},
    ),
    "devops": RoleDefinition(
        role_id="devops",
        name="DevOps工程师",
        aliases=["infra"],
        prompt="你是DevOps工程师。负责：\n1. CI/CD流水线设计与实现（GitHub Actions、GitLab CI、Jenkins）\n2. 容器化与编排（Docker、Kubernetes、Docker Compose）\n3. 基础设施即代码（Terraform、Pulumi、CloudFormation）\n4. 监控告警体系搭建（Prometheus、Grafana、ELK、Sentry）\n5. 部署策略设计（蓝绿部署、金丝雀发布、滚动更新）\n6. 环境管理（开发/测试/预生产/生产环境配置与隔离）\n7. 输出：CI/CD配置、Dockerfile、K8s Manifests、监控配置、部署文档",
        keywords=[
            "CI/CD",
            "部署",
            "监控",
            "运维",
            "Docker",
            "Kubernetes",
            "基础设施",
            "容器",
            "deploy",
            "monitor",
            "infrastructure",
            "container",
            "pipeline",
            "devops",
            "ci/cd",
            "cloud",
        ],
        weight=1.0,
        description="CI/CD pipeline, containerization, monitoring, infrastructure",
        status="core",
        prompt_i18n={
            "en": "You are a DevOps Engineer. Responsible for:\n1. CI/CD pipeline design and implementation (GitHub Actions, GitLab CI, Jenkins)\n2. Containerization and orchestration (Docker, Kubernetes, Docker Compose)\n3. Infrastructure as code (Terraform, Pulumi, CloudFormation)\n4. Monitoring and alerting system setup (Prometheus, Grafana, ELK, Sentry)\n5. Deployment strategy design (blue-green deployment, canary release, rolling update)\n6. Environment management (dev/test/staging/production configuration and isolation)\n7. Output: CI/CD configs, Dockerfile, K8s manifests, monitoring configs, deployment docs",
            "ja": "あなたはDevOpsエンジニアです。担当：\n1. CI/CDパイプライン設計と実装（GitHub Actions、GitLab CI、Jenkins）\n2. コンテナ化とオーケストレーション（Docker、Kubernetes、Docker Compose）\n3. Infrastructure as Code（Terraform、Pulumi、CloudFormation）\n4. 監視・アラート体系の構築（Prometheus、Grafana、ELK、Sentry）\n5. デプロイ戦略設計（ブルーグリーンデプロイ、カナリアリリース、ローリングアップデート）\n6. 環境管理（開発/テスト/ステージング/本番環境の設定と分離）\n7. 出力：CI/CD設定、Dockerfile、K8sマニフェスト、監視設定、デプロイドキュメント",
        },
        name_i18n={"en": "DevOps Engineer", "ja": "DevOpsエンジニア"},
    ),
    "security": RoleDefinition(
        role_id="security",
        name="安全专家",
        aliases=["sec"],
        prompt="你是安全专家。负责：\n1. 威胁建模（STRIDE、DREAD攻击树分析）\n2. 漏洞审计（OWASP Top 10、CWE常见弱点枚举）\n3. 认证与授权安全审查（OAuth2、JWT、RBAC/ABAC）\n4. 数据安全评估（加密方案、密钥管理、数据脱敏）\n5. 依赖安全扫描与供应链安全（Snyk、Dependabot、SBOM）\n6. 合规性检查（GDPR、SOC2、HIPAA、PCI-DSS）\n7. 安全编码规范与最佳实践\n8. 输出：威胁模型、漏洞报告、安全建议、合规评估",
        keywords=[
            "安全",
            "漏洞",
            "审计",
            "威胁",
            "加密",
            "认证",
            "授权",
            "OWASP",
            "security",
            "vulnerability",
            "audit",
            "threat",
            "encrypt",
            "auth",
            "compliance",
            "owasp",
        ],
        weight=1.1,
        description="Threat modeling, vulnerability audit, compliance, security review",
        status="core",
        prompt_i18n={
            "en": "You are a Security Expert. Responsible for:\n1. Threat modeling (STRIDE, DREAD attack-tree analysis)\n2. Vulnerability audit (OWASP Top 10, CWE common weakness enumeration)\n3. Authentication and authorization security review (OAuth2, JWT, RBAC/ABAC)\n4. Data security assessment (encryption schemes, key management, data masking)\n5. Dependency security scanning and supply-chain security (Snyk, Dependabot, SBOM)\n6. Compliance checks (GDPR, SOC2, HIPAA, PCI-DSS)\n7. Secure coding standards and best practices\n8. Output: threat models, vulnerability reports, security recommendations, compliance assessments",
            "ja": "あなたはセキュリティ専門家です。担当：\n1. 脅威モデリング（STRIDE、DREAD攻撃ツリー分析）\n2. 脆弱性監査（OWASP Top 10、CWE共通弱点列挙）\n3. 認証・認可セキュリティレビュー（OAuth2、JWT、RBAC/ABAC）\n4. データセキュリティ評価（暗号化方式、鍵管理、データマスキング）\n5. 依存関係セキュリティスキャンとサプライチェーンセキュリティ（Snyk、Dependabot、SBOM）\n6. コンプライアンスチェック（GDPR、SOC2、HIPAA、PCI-DSS）\n7. セキュアコーディング規範とベストプラクティス\n8. 出力：脅威モデル、脆弱性レポート、セキュリティ推奨事項、コンプライアンス評価",
        },
        name_i18n={"en": "Security Expert", "ja": "セキュリティ専門家"},
    ),
}


def _build_role_aliases() -> dict[str, str]:
    aliases = {}
    for rid, rdef in ROLE_REGISTRY.items():
        for alias in rdef.aliases:
            aliases[alias] = rid
    return aliases


ROLE_ALIASES: dict[str, str] = _build_role_aliases()


def resolve_role_id(role_id: str) -> str:
    """Resolve role identifier to canonical form.

    Converts aliases or abbreviations to the canonical role_id.
    If the input is already a valid role_id, returns it unchanged.
    Otherwise returns the input as-is (for custom/unknown roles).

    Args:
        role_id: Role identifier or alias to resolve (e.g., "arch", "architect")

    Returns:
        Canonical role_id string (e.g., "architect")

    Example:
        >>> resolve_role_id("arch")
        'architect'
        >>> resolve_role_id("unknown-role")
        'unknown-role'
    """
    if role_id in ROLE_REGISTRY:
        return role_id
    return ROLE_ALIASES.get(role_id, role_id)


def get_core_roles() -> dict[str, RoleDefinition]:
    """Get all core (active) role definitions.

    Filters ROLE_REGISTRY to return only roles with status="core".

    Returns:
        Dictionary mapping role_id to RoleDefinition for active roles.
    """
    return {rid: rdef for rid, rdef in ROLE_REGISTRY.items() if rdef.status == "core"}


def get_planned_roles() -> dict[str, RoleDefinition]:
    """Get all planned (future) role definitions.

    Filters ROLE_REGISTRY to return only roles with status="planned".
    These roles are defined but not yet fully implemented.

    Returns:
        Dictionary mapping role_id to RoleDefinition for planned roles.
    """
    return {rid: rdef for rid, rdef in ROLE_REGISTRY.items() if rdef.status == "planned"}


def get_all_role_ids() -> list[str]:
    """Get list of all registered role IDs.

    Returns:
        Sorted list of all role identifiers in registry.
    """
    return list(ROLE_REGISTRY.keys())


def get_cli_role_list() -> list[str]:
    """Get role list formatted for CLI display.

    Returns primary alias (first in list) for each role,
    suitable for command-line argument completion.

    Returns:
        List of short role identifiers/aliases for CLI use.
    """
    result = []
    for rid, rdef in ROLE_REGISTRY.items():
        result.append(rdef.aliases[0] if rdef.aliases else rid)
    return result


# =============================================================================
# V4.4.4 — WorkflowTrace & GitContext (block/buzz-inspired)
#
# The module-level ``_call_counter`` (declared at the top of this file) is
# shared by ``RoleDefinition.get_localized_prompt`` and the two new V4.4.4
# dataclasses below. It is incremented on every ``WorkflowTrace`` /
# ``GitContext`` construction and every ``GitContext.auto_detect`` call so
# ``check_module_activation.py`` can verify the V4.4.4 code path is wired in
# (anti-ghost guarantee).
# =============================================================================


@dataclass
class WorkflowStep:
    """Single step in a workflow trace.

    Captures one unit of work executed by a Worker during a dispatch.

    Attributes:
        step_name: Human-readable name of the step (e.g. "analyze-architecture").
        role_id: Role that executed the step (e.g. "architect").
        agent_id: V4.4.3 AgentIdentity of the executing Worker.
        status: Execution status — "success" / "running" / "failed".
        duration_ms: Wall-clock duration in milliseconds.
        details: Optional free-form detail string (default empty).
    """

    step_name: str
    role_id: str
    agent_id: str
    status: str
    duration_ms: float
    details: str = ""


@dataclass
class WorkflowTrace:
    """Trace of task decomposition + execution for transparency.

    V4.4.4 — Inspired by block/buzz's workflow trace transparency: users
    can see exactly how the agent team decomposed and executed a task.
    Populated by the dispatch pipeline and rendered into the Markdown
    report by ``ReportFormatter``.

    Attributes:
        task_description: Original task description provided to ``dispatch``.
        decomposition_tree: Structured task → subtasks → roles tree.
            Each dict has ``{"task": str, "subtasks": list, "roles": list}``.
        steps: Ordered list of ``WorkflowStep`` execution records.
        decision_points: List of ConsensusEngine invocation points
            (each dict has ``{"topic": str, "outcome": str, ...}``).
    """

    task_description: str
    decomposition_tree: list[dict] = field(default_factory=list)
    steps: list[WorkflowStep] = field(default_factory=list)
    decision_points: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Anti-ghost: increment the shared module-level counter so tests
        # and ``check_module_activation.py`` can prove the WorkflowTrace
        # code path was actually exercised (not dead code).
        global _call_counter
        _call_counter += 1

    @property
    def _call_counter_value(self) -> int:
        """Read-only access to the module-level call counter (anti-ghost)."""
        return _call_counter

    def to_markdown(self) -> str:
        """Render the workflow trace as a Markdown ``## Workflow Trace`` section.

        The section includes:
        - Task description header
        - Decomposition tree (bullet list)
        - Step execution table (step / role / agent / status / duration / details)
        - Decision points list

        Returns:
            Markdown string. Empty steps / decision_points produce a
            minimal-but-valid section so the report formatter can always
            include the section when a trace is present.
        """
        lines: list[str] = [
            "## 🔍 Workflow Trace",
            "",
            f"**Task**: {self.task_description}",
            "",
        ]

        # Decomposition tree
        if self.decomposition_tree:
            lines.append("### Decomposition Tree")
            for node in self.decomposition_tree:
                task = node.get("task", "(unnamed)")
                roles = node.get("roles", [])
                role_str = ", ".join(roles) if roles else "(unassigned)"
                lines.append(f"- **{task}** → roles: {role_str}")
                for sub in node.get("subtasks", []):
                    sub_str = sub if isinstance(sub, str) else sub.get("task", str(sub))
                    lines.append(f"  - {sub_str}")
            lines.append("")

        # Steps table
        if self.steps:
            lines.append("### Steps")
            lines.append("")
            lines.append("| Step | Role | Agent | Status | Duration (ms) | Details |")
            lines.append("|------|------|-------|--------|---------------|---------|")
            for step in self.steps:
                details = (step.details or "").replace("|", "\\|").replace("\n", " ")[:80]
                lines.append(
                    f"| {step.step_name} | {step.role_id} | {step.agent_id} "
                    f"| {step.status} | {step.duration_ms:.1f} | {details} |"
                )
            lines.append("")

        # Decision points
        if self.decision_points:
            lines.append("### Decision Points")
            for dp in self.decision_points:
                topic = dp.get("topic", "(unknown)")
                outcome = dp.get("outcome", "")
                lines.append(f"- **{topic}** — outcome: {outcome}")
            lines.append("")

        return "\n".join(lines)


@dataclass
class GitContext:
    """Git context for dispatch — Branch-as-Context from block/buzz.

    V4.4.4 — When provided to ``dispatch(git_context=...)``, this is
    injected into the Coordinator prompt so Workers can reference the
    current branch / recent commits / open issues in their analysis.

    Attributes:
        branch: Current git branch name (empty if unknown).
        recent_commits: List of recent commit ``oneline`` strings.
        open_issues: List of open issue identifiers (e.g. ``#123``).
    """

    branch: str = ""
    recent_commits: list[str] = field(default_factory=list)
    open_issues: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Anti-ghost: increment the shared module-level counter so tests
        # can prove a GitContext was constructed through the dispatch path.
        global _call_counter
        _call_counter += 1

    @property
    def _call_counter_value(self) -> int:
        """Read-only access to the module-level call counter (anti-ghost)."""
        return _call_counter

    @classmethod
    def auto_detect(cls, timeout: float = 2.0) -> "GitContext | None":
        """Auto-detect git context from the current working directory.

        Uses ``git branch --show-current`` and ``git log --oneline -5``.
        Returns ``None`` if the cwd is not a git repo, the ``git`` binary
        is unavailable, or any other error occurs (timeout, permission, etc).

        Args:
            timeout: Subprocess timeout in seconds (default 2.0).

        Returns:
            A populated ``GitContext`` or ``None`` on any failure.
        """
        global _call_counter
        _call_counter += 1

        import subprocess

        try:
            branch_proc = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if branch_proc.returncode != 0:
                return None
            branch = branch_proc.stdout.strip()
            if not branch:
                return None

            log_proc = subprocess.run(
                ["git", "log", "--oneline", "-5"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            recent_commits: list[str] = []
            if log_proc.returncode == 0:
                recent_commits = [
                    line.strip() for line in log_proc.stdout.splitlines() if line.strip()
                ]

            return cls(branch=branch, recent_commits=recent_commits)
        except Exception:  # noqa: BLE001 — auto_detect must never raise
            # Catches subprocess.TimeoutExpired, FileNotFoundError (git not
            # installed), PermissionError, OSError, and any other unexpected
            # failure. The contract is "return None on any failure".
            return None

    def to_prompt_section(self) -> str:
        """Render this GitContext as a ``## Git Context`` prompt section.

        Designed to be appended to the Coordinator prompt so all Workers
        see the current branch / recent commits / open issues context.

        Returns:
            Markdown section string. Always returns a section (even if
            some fields are empty) so callers can blindly append.
        """
        lines: list[str] = [
            "## Git Context",
            "",
            f"- **Branch**: `{self.branch}`" if self.branch else "- **Branch**: (unknown)",
        ]
        if self.recent_commits:
            lines.append("- **Recent commits**:")
            for commit in self.recent_commits:
                lines.append(f"  - {commit}")
        if self.open_issues:
            lines.append("- **Open issues**:")
            for issue in self.open_issues:
                lines.append(f"  - {issue}")
        lines.append("")
        return "\n".join(lines)
