#!/usr/bin/env python3
"""
协作系统数据模型 — 角色派发相关定义。

本模块包含角色权重、角色注册表（ROLE_REGISTRY）、角色别名解析以及
角色查询辅助函数，供 Coordinator / Dispatcher 进行角色匹配与派发使用。
"""

from dataclasses import dataclass

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
