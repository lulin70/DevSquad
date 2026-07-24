"""TeachSkill — DevSquad onboarding educational skill.

Guides new users through the DevSquad 7-role collaboration model,
11-phase lifecycle, and Iron Rules. Provides structured lessons with
examples, exercises, and assessment.

Topics:
    - overview: One-sentence DevSquad understanding
    - seven_roles: 7-role collaboration model
    - lifecycle: 11-phase lifecycle
    - iron_rules: 3 Iron Rules (Documentation First / Test Iron Rules / Delivery Workflow)
    - sub_skills: 6 atomic sub-skills
    - glossary: Glossary terms
    - quickstart: 5-minute quickstart
    - full_curriculum: Full ordered curriculum

Integration:
    Reads GLOSSARY.md (if present) for terminology definitions; falls back
    to built-in canonical terms sourced from SKILL.md and GLOSSARY.md.

Example:
    >>> from skills.teach.handler import TeachSkill
    >>> skill = TeachSkill()
    >>> result = skill.teach("overview")
    >>> print(result["title"])
    >>> print(result["estimated_minutes"])
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from skills.registry import BaseSkill  # noqa: I001


# ===== Canonical content sourced from SKILL.md (read, not memorized) =====

SEVEN_ROLES = [
    {
        "id": "architect",
        "name": "Architect",
        "name_zh": "架构师",
        "name_ja": "アーキテクト",
        "triggers": "architecture, design, selection, performance, module, interface, data architecture",
        "responsibility": "System architecture, tech selection, performance/security/data architecture",
    },
    {
        "id": "product-manager",
        "name": "Product Manager",
        "name_zh": "产品经理",
        "name_ja": "プロダクトマネージャー",
        "triggers": "requirements, PRD, user story, competitor, acceptance",
        "responsibility": "Requirements analysis, PRD writing, product planning",
    },
    {
        "id": "security",
        "name": "Security Expert",
        "name_zh": "安全专家",
        "name_ja": "セキュリティ専門家",
        "triggers": "security, vulnerability, audit, threat, encryption, OWASP",
        "responsibility": "Threat modeling, vulnerability audit, compliance, security review",
    },
    {
        "id": "tester",
        "name": "Test Expert",
        "name_zh": "测试专家",
        "name_ja": "テスト専門家",
        "triggers": "test, quality, acceptance, automation, defect",
        "responsibility": "Test strategy, case design, quality assurance",
    },
    {
        "id": "solo-coder",
        "name": "Coder",
        "name_zh": "开发工程师",
        "name_ja": "開発エンジニア",
        "triggers": "implementation, development, code, fix, optimize, refactor",
        "responsibility": "Feature dev, code review, performance optimization, refactoring",
    },
    {
        "id": "devops",
        "name": "DevOps Engineer",
        "name_zh": "DevOps 工程师",
        "name_ja": "DevOpsエンジニア",
        "triggers": "CI/CD, deploy, monitor, Docker, Kubernetes, infrastructure",
        "responsibility": "CI/CD pipeline, containerization, monitoring, infrastructure",
    },
    {
        "id": "ui-designer",
        "name": "UI Designer",
        "name_zh": "UI 设计师",
        "name_ja": "UIデザイナー",
        "triggers": "UI, interface, frontend, visual, prototype, accessibility",
        "responsibility": "UI design, interaction design, prototyping, accessibility",
    },
]


LIFECYCLE_PHASES = [
    {"phase": "P1", "name": "Requirements Analysis", "lead": "pm", "reviewers": "arch+test+sec+ui", "optional": False, "gate": "Acceptance criteria quantifiable"},
    {"phase": "P2", "name": "Architecture Design", "lead": "arch", "reviewers": "pm+sec+infra", "optional": False, "gate": "Weighted consensus >=70%"},
    {"phase": "P3", "name": "Technical Design", "lead": "arch+coder", "reviewers": "coder+test", "optional": False, "gate": "API specs unambiguous"},
    {"phase": "P4", "name": "Data Design", "lead": "arch+coder", "reviewers": "arch+sec", "optional": True, "gate": "3NF or denormalization justified"},
    {"phase": "P5", "name": "Interaction Design", "lead": "ui", "reviewers": "pm+test+sec", "optional": True, "gate": "Core flow usability verified"},
    {"phase": "P6", "name": "Security Review", "lead": "sec", "reviewers": "arch+infra", "optional": True, "gate": "No P0/P1 vulns, compliance green"},
    {"phase": "P7", "name": "Test Planning", "lead": "test", "reviewers": "arch+sec+infra+pm", "optional": False, "gate": "Test plan review passed"},
    {"phase": "P8", "name": "Implementation", "lead": "coder", "reviewers": "arch+sec+test+coder", "optional": False, "gate": "Code review passed, no P0 defects"},
    {"phase": "P9", "name": "Test Execution", "lead": "test", "reviewers": "arch+pm+sec+infra", "optional": False, "gate": "Coverage>=80% + P7 plan 100% executed"},
    {"phase": "P10", "name": "Deployment & Release", "lead": "infra", "reviewers": "arch+sec+test", "optional": False, "gate": "Deployment drill passed"},
    {"phase": "P11", "name": "Operations & Assurance", "lead": "infra+sec", "reviewers": "arch+infra", "optional": True, "gate": "P99<target, alerts 100%"},
]


LIFECYCLE_TEMPLATES = [
    {"template": "full", "phases": "P1-P11", "use_case": "Complete project"},
    {"template": "backend", "phases": "No P5", "use_case": "Backend services"},
    {"template": "frontend", "phases": "No P4,P6", "use_case": "Frontend applications"},
    {"template": "internal_tool", "phases": "No P4,P5,P6,P11", "use_case": "Internal tools"},
    {"template": "minimal", "phases": "P1,P3,P7,P8,P9", "use_case": "Minimum set"},
]


IRON_RULES = [
    {
        "id": "documentation_first",
        "name": "Documentation First, Trace Everything",
        "name_zh": "文档先行，万事留痕",
        "name_ja": "ドキュメント先行、すべて記録",
        "principle": "Before any code is written -> Plan/Spec document must exist. Before any change is made -> Impact analysis must be documented. After any work is done -> Results must be recorded in docs. After any decision is made -> Rationale must be traceable.",
        "violation_consequence": "Violating this rule is a critical error that invalidates all work done. CI check will fail; PR reviewer will block; consensus will not approve.",
        "type": "supreme_law",
    },
    {
        "id": "test_iron_rules",
        "name": "Testing Iron Rules",
        "name_zh": "测试铁律",
        "name_ja": "テスト鉄則",
        "principle": "1) Documentation First -- Never write API calls from memory (read source first). 2) Failure Means Report -- Never modify assertions to pass (analyze root cause). 3) Dimension Completeness -- Never only test happy path (cover all 7 dimensions: Happy/Error/Boundary/Performance/Configuration/Integration/Security).",
        "violation_consequence": "Tests written from memory will fail due to wrong param names. Modified assertions hide real bugs. Happy-path-only tests miss 50%+ of issues. TestQualityGuard auto-detects anti-patterns.",
        "type": "testing_discipline",
    },
    {
        "id": "delivery_workflow",
        "name": "Delivery Workflow Iron Rules",
        "name_zh": "交付工作流铁律",
        "name_ja": "デリバリーワークフロー鉄則",
        "principle": "Mandatory post-push closed loop: Implement -> Test(Regression All) -> Code Walkthrough -> Annotate -> Docs Update -> Cleanup -> Git Push. Doc Coverage Checklist must check ALL categories (Requirements/Design/Planning/SKILL/README/CHANGELOG/Status). Cleanup Rules delete temp/debug/draft/deprecated files.",
        "violation_consequence": "Skipping any step creates technical debt. Missing docs update = stale documentation. Temp files left = repo pollution. Commit without test = potential regression. Reviewer will request changes.",
        "type": "delivery_discipline",
    },
]


SUB_SKILLS = [
    {"name": "dispatch", "class": "DispatchSkill", "core_method": "run(task, roles, mode)", "wraps": "MultiAgentDispatcher", "description": "7-role orchestration entry point"},
    {"name": "intent", "class": "IntentSkill", "core_method": "detect(text, lang)", "wraps": "IntentWorkflowMapper", "description": "6 intents x 3 languages detection"},
    {"name": "review", "class": "ReviewSkill", "core_method": "review(code, axes)", "wraps": "FiveAxisConsensusEngine", "description": "5-axis code review"},
    {"name": "security", "class": "SecuritySkill", "core_method": "scan_input(text)", "wraps": "InputValidator + OpClassifier", "description": "40-pattern security scan"},
    {"name": "test", "class": "TestSkill", "core_method": "generate_strategy(module)", "wraps": "TestQualityGuard", "description": "Test strategy + quality audit"},
    {"name": "retrospective", "class": "RetrospectiveSkill", "core_method": "run_retrospective(results)", "wraps": "RetrospectiveEngine", "description": "Post-dispatch pattern extraction"},
]


# Built-in glossary (fallback if GLOSSARY.md not parseable)
BUILTIN_GLOSSARY = [
    {"term": "Coordinator", "definition": "Global orchestrator: decompose tasks, assign Workers, collect results, resolve conflicts."},
    {"term": "Worker", "definition": "Working unit, one instance per role, independent execution with Scratchpad writes."},
    {"term": "Scratchpad", "definition": "Shared blackboard for real-time info exchange between Workers."},
    {"term": "ConsensusEngine", "definition": "Consensus engine: weighted voting + veto power + escalation mechanism."},
    {"term": "DispatchResult", "definition": "Dispatch result containing worker_results/consensus_records/errors etc."},
    {"term": "Iron Rule", "definition": "Ironclad rule that cannot be violated. e.g., 'Documentation First', 'Failure Means Report'."},
    {"term": "Gate", "definition": "Phase gate, evidence-driven acceptance. P1-P11 each has a gate."},
    {"term": "Anchor", "definition": "Goal anchoring, real-time detection of task execution deviation from original goal."},
    {"term": "Loop Engineering", "definition": "Five-step closed loop: Discovery -> Handoff -> Verification -> Persistence -> Scheduling."},
    {"term": "Adversarial Verify", "definition": "Red-blue team + judge arbitration three-stage verification."},
    {"term": "DAG Visualizer", "definition": "Mermaid/JSON/DOT three-format dependency graph visualization."},
    {"term": "Autonomous Loop", "definition": "plan -> dev -> verify -> fix 4-stage autonomous iteration."},
    {"term": "Plugin Hot Loader", "definition": "Plugin hot loading, 3 loading paths + path traversal protection."},
    {"term": "Deep module", "definition": "Small interface + large implementation, high leverage + high locality. Optimal module design."},
    {"term": "Shallow module", "definition": "Large interface + small implementation, pass-through. Should be avoided."},
    {"term": "Seam", "definition": "A place where behavior can be changed without editing in-place. Key for testing and refactoring."},
    {"term": "Deletion test", "definition": "Imagine deleting a module; if complexity disappears, it is pass-through (shallow)."},
    {"term": "Red-capable", "definition": "Able to turn red on a specific bug. Debug commands must be red-capable to be valid."},
    {"term": "Tautological test", "definition": "Assertion re-computes implementation logic, always passes but valueless. Test anti-pattern."},
    {"term": "Grilling", "definition": "one-question-at-a-time interview method with recommended-answer. For requirement alignment."},
    {"term": "ADR", "definition": "Architecture Decision Record. Write only when all 3 criteria met: affects multi-modules, has alternatives, may be overturned in future."},
    {"term": "HITL", "definition": "Human-In-The-Loop. Steps requiring human confirmation."},
    {"term": "AFK", "definition": "Away-From-Keyboard. Steps that can be executed asynchronously."},
    {"term": "Vertical slice", "definition": "End-to-end functional slice (UI+logic+data), not horizontal layering. Task decomposition method."},
    {"term": "Progressive disclosure", "definition": "Layered information presentation: overview first, expand details on demand. Avoids information overload."},
]


CURRICULUM_ORDER = [
    "overview",
    "seven_roles",
    "lifecycle",
    "iron_rules",
    "sub_skills",
    "glossary",
    "quickstart",
]


TOPIC_TITLES = {
    "overview": {"zh": "DevSquad 概览：一句话理解", "en": "DevSquad Overview: One-Sentence Understanding", "ja": "DevSquad概要：一文理解"},
    "seven_roles": {"zh": "7 角色协作模型", "en": "7-Role Collaboration Model", "ja": "7役割協力モデル"},
    "lifecycle": {"zh": "11 阶段项目生命周期", "en": "11-Phase Project Lifecycle", "ja": "11フェーズプロジェクトライフサイクル"},
    "iron_rules": {"zh": "三大 Iron Rules 铁律", "en": "Three Iron Rules", "ja": "三大鉄則"},
    "sub_skills": {"zh": "6 个原子 Sub-Skill", "en": "6 Atomic Sub-Skills", "ja": "6個の原子サブスキル"},
    "glossary": {"zh": "术语表 Glossary", "en": "Glossary", "ja": "用語集"},
    "quickstart": {"zh": "5 分钟快速上手", "en": "5-Minute Quickstart", "ja": "5分クイックスタート"},
    "full_curriculum": {"zh": "完整课程", "en": "Full Curriculum", "ja": "完全カリキュラム"},
}


TOPIC_MINUTES = {
    "overview": {"beginner": 5, "intermediate": 3, "advanced": 2},
    "seven_roles": {"beginner": 15, "intermediate": 10, "advanced": 5},
    "lifecycle": {"beginner": 20, "intermediate": 12, "advanced": 6},
    "iron_rules": {"beginner": 18, "intermediate": 12, "advanced": 6},
    "sub_skills": {"beginner": 12, "intermediate": 8, "advanced": 4},
    "glossary": {"beginner": 8, "intermediate": 5, "advanced": 3},
    "quickstart": {"beginner": 10, "intermediate": 7, "advanced": 5},
    "full_curriculum": {"beginner": 88, "intermediate": 57, "advanced": 31},
}


NEXT_TOPIC = {
    "overview": "seven_roles",
    "seven_roles": "lifecycle",
    "lifecycle": "iron_rules",
    "iron_rules": "sub_skills",
    "sub_skills": "quickstart",
    "glossary": "quickstart",
    "quickstart": None,
    "full_curriculum": None,
}


class TeachSkill(BaseSkill):
    """DevSquad onboarding educational skill.

    Guides new users through the DevSquad 7-role collaboration model,
    11-phase lifecycle, and Iron Rules. Provides structured lessons with
    examples, exercises, and assessment. Distinct from grilling (P0-7):
    TeachSkill transfers knowledge rather than collecting requirements.

    Attributes:
        name: Skill identifier ("teach")
        description: Human-readable skill description
        version: Skill semantic version (inherited from BaseSkill)
        TOPICS: List of supported teaching topics

    Example:
        >>> skill = TeachSkill()
        >>> result = skill.teach("overview", user_level="beginner", lang="zh")
        >>> print(result["title"])
        >>> print(result["estimated_minutes"])
    """

    name = "teach"
    description = "DevSquad onboarding - guide new users through 7-role collaboration model, 11-phase lifecycle, and Iron Rules"

    TOPICS = [
        "overview",
        "seven_roles",
        "lifecycle",
        "iron_rules",
        "sub_skills",
        "glossary",
        "quickstart",
        "full_curriculum",
    ]

    USER_LEVELS = ["beginner", "intermediate", "advanced"]
    LANGS = ["auto", "zh", "en", "ja"]

    # Path to GLOSSARY.md (canonical source; lazy-loaded)
    _GLOSSARY_PATH = Path(__file__).parent.parent.parent / "docs" / "spec" / "GLOSSARY.md"

    def teach(self, topic: str = "overview", user_level: str = "beginner", lang: str = "auto") -> dict:
        """Teach a specific DevSquad topic to a new user.

        Args:
            topic: One of TOPICS (overview/seven_roles/lifecycle/iron_rules/
                sub_skills/glossary/quickstart/full_curriculum)
            user_level: "beginner" | "intermediate" | "advanced"
            lang: "auto" | "zh" | "en" | "ja"

        Returns:
            Dict with keys:
                - topic: str -- taught topic
                - user_level: str
                - lang: str
                - title: str -- lesson title
                - content: str -- lesson content (markdown)
                - examples: list[dict] -- list of {scenario, code, explanation}
                - exercises: list[str] -- practice exercises
                - next_topic: str -- recommended next topic (or None)
                - glossary_terms: list[dict] -- related terms from GLOSSARY.md
                - estimated_minutes: int -- estimated learning time

        Raises:
            ValueError: If topic or user_level is invalid.
        """
        if topic not in self.TOPICS:
            raise ValueError(f"Unknown topic: {topic}. Available: {self.TOPICS}")
        if user_level not in self.USER_LEVELS:
            raise ValueError(f"Unknown user_level: {user_level}. Available: {self.USER_LEVELS}")

        resolved_lang = self._resolve_lang(lang)

        if topic == "full_curriculum":
            return self._teach_full_curriculum(user_level, resolved_lang)

        title = TOPIC_TITLES[topic][resolved_lang]
        content = self._build_content(topic, user_level, resolved_lang)
        examples = self._build_examples(topic, resolved_lang)
        exercises = self._build_exercises(topic, user_level, resolved_lang)
        next_topic = NEXT_TOPIC.get(topic)
        glossary_terms = self._related_glossary_terms(topic)
        estimated_minutes = TOPIC_MINUTES[topic][user_level]

        return {
            "topic": topic,
            "user_level": user_level,
            "lang": resolved_lang,
            "title": title,
            "content": content,
            "examples": examples,
            "exercises": exercises,
            "next_topic": next_topic,
            "glossary_terms": glossary_terms,
            "estimated_minutes": estimated_minutes,
        }

    def assess(self, topic: str, user_answers: dict) -> dict:
        """Assess user's understanding of a topic.

        Args:
            topic: The topic to assess
            user_answers: Dict of {question_id: answer}

        Returns:
            Dict with keys:
                - topic: str
                - score: float (0.0-1.0)
                - passed: bool (score >= 0.7)
                - correct_answers: list[str]
                - incorrect_answers: list[str]
                - recommendations: list[str]

        Raises:
            ValueError: If topic is invalid.
        """
        if topic not in self.TOPICS:
            raise ValueError(f"Unknown topic: {topic}. Available: {self.TOPICS}")

        answer_key = self._assessment_key(topic)
        total = len(answer_key)
        if total == 0:
            return {
                "topic": topic,
                "score": 0.0,
                "passed": False,
                "correct_answers": [],
                "incorrect_answers": [],
                "recommendations": ["No assessment questions for this topic."],
            }

        correct: list[str] = []
        incorrect: list[str] = []
        for qid, expected in answer_key.items():
            user_ans = user_answers.get(qid)
            if user_ans is not None and self._answers_match(user_ans, expected):
                correct.append(qid)
            else:
                incorrect.append(qid)

        score = len(correct) / total
        passed = score >= 0.7
        recommendations = self._build_recommendations(topic, score, incorrect)

        return {
            "topic": topic,
            "score": round(score, 4),
            "passed": passed,
            "correct_answers": correct,
            "incorrect_answers": incorrect,
            "recommendations": recommendations,
        }

    def curriculum(self, user_level: str = "beginner") -> dict:
        """Return a structured curriculum for the given user level.

        Args:
            user_level: "beginner" | "intermediate" | "advanced"

        Returns:
            Dict with keys:
                - user_level: str
                - modules: list[dict] -- ordered list of
                  {topic, title, estimated_minutes, prerequisites}
                - total_estimated_minutes: int
                - graduation_criteria: list[str]

        Raises:
            ValueError: If user_level is invalid.
        """
        if user_level not in self.USER_LEVELS:
            raise ValueError(f"Unknown user_level: {user_level}. Available: {self.USER_LEVELS}")

        # Advanced skips basic modules (overview, glossary, quickstart)
        if user_level == "advanced":
            module_topics = ["seven_roles", "lifecycle", "iron_rules", "sub_skills"]
        elif user_level == "intermediate":
            module_topics = ["overview", "seven_roles", "lifecycle", "iron_rules", "sub_skills", "quickstart"]
        else:  # beginner
            module_topics = CURRICULUM_ORDER.copy()

        modules = []
        total = 0
        for i, topic in enumerate(module_topics):
            prereqs = [module_topics[j] for j in range(i)] if i > 0 else []
            minutes = TOPIC_MINUTES[topic][user_level]
            modules.append({
                "topic": topic,
                "title": TOPIC_TITLES[topic]["zh"],
                "estimated_minutes": minutes,
                "prerequisites": prereqs,
            })
            total += minutes

        graduation_criteria = self._graduation_criteria(user_level)

        return {
            "user_level": user_level,
            "modules": modules,
            "total_estimated_minutes": total,
            "graduation_criteria": graduation_criteria,
        }

    def run(self, *args: Any, **kwargs: Any) -> dict:
        """Default entry point -- delegates to teach()."""
        return self.teach(*args, **kwargs)

    # ===== Language resolution =====

    @staticmethod
    def _resolve_lang(lang: str) -> str:
        """Resolve language code. 'auto' defaults to 'zh'."""
        if lang == "auto":
            return "zh"
        if lang not in ("zh", "en", "ja"):
            return "zh"
        return lang

    # ===== Content builders =====

    def _build_content(self, topic: str, user_level: str, lang: str) -> str:
        """Build markdown content for a topic, adjusted for user_level and lang."""
        builder = getattr(self, f"_content_{topic}", None)
        if builder is None:
            return ""
        result: str = builder(user_level, lang)
        return result

    def _content_overview(self, user_level: str, lang: str) -> str:
        if lang == "en":
            base = "# DevSquad Overview\n\n**DevSquad = Upgrade a single AI assistant into a 7-person AI professional team.**\n\n"
            base += "## Single AI vs DevSquad\n\n"
            base += "| Dimension | Single AI (ChatGPT/Claude) | DevSquad |\n|-----------|---------------------------|----------|\n"
            base += "| Perspective | One role answers | **7 professional roles in parallel** |\n"
            base += "| Quality | May miss security/testing | **Multi-dimensional cross-validation** |\n"
            base += "| Traceability | None | **Complete audit chain (SHA256)** |\n"
            base += "| Use Case | Simple Q&A | **Complex engineering tasks** |\n\n"
            base += "## Core Workflow\n\n"
            base += "```\nUser Task -> [InputValidator] -> [RoleMatcher] -> [Coordinator Orchestration]\n"
            base += "           -> [ThreadPoolExecutor Parallel Workers] -> [Scratchpad Real-time Sharing]\n"
            base += "           -> [ConsensusEngine] -> [ReportFormatter] -> [Structured Report]\n```\n"
            if user_level == "beginner":
                base += "\n## Why DevSquad?\n\n- **Parallel roles**: 7 experts work simultaneously, not sequentially.\n- **Consensus**: Weighted voting + veto power ensures quality.\n- **Audit trail**: Every decision is traceable via SHA-256.\n- **Mock mode**: Works offline without API keys.\n"
            elif user_level == "intermediate":
                base += "\n## Key Insight\n\nDevSquad shifts from single-role Q&A to multi-role consensus, ensuring completeness on complex tasks.\n"
            else:
                base += "\n## TL;DR\n\nMulti-role consensus orchestration with full audit trail. Mock-mode by default.\n"
            return base
        if lang == "ja":
            base = "# DevSquad概要\n\n**DevSquad = 単一のAIアシスタントを7人のAIプロチームにアップグレード。**\n\n"
            base += "## 単一AI vs DevSquad\n\n"
            base += "| 次元 | 単一AI | DevSquad |\n|------|--------|----------|\n"
            base += "| 視点 | 1役割が回答 | **7役割が並行** |\n"
            base += "| 品質 | セキュリティ/テスト漏れあり | **多次元交差検証** |\n"
            base += "| 追跡性 | なし | **完全監査チェーン(SHA256)** |\n"
            base += "| ユースケース | 簡単Q&A | **複雑エンジニアリングタスク** |\n"
            if user_level == "beginner":
                base += "\n## なぜDevSquad?\n\n- **並行役割**: 7人の専門家が同時に作業。\n- **合意形成**: 重み付き投票 + 否決権が品質を保証。\n- **監査トレイル**: すべての決定がSHA-256で追跡可能。\n- **モックモード**: APIキーなしでオフライン動作。\n"
            else:
                base += "\n## 要点\n\n複数役割の合意形成オーケストレーション + 完全監査トレイル。デフォルトでモックモード。\n"
            return base
        # Default: zh
        base = "# DevSquad 概览\n\n**DevSquad = 把「单个 AI 助手」升级成「7 人 AI 专业团队」。**\n\n"
        base += "## 对比：单 AI vs DevSquad\n\n"
        base += "| 维度 | 单个 AI (ChatGPT/Claude) | DevSquad |\n|------|---------------------------|----------|\n"
        base += "| 视角 | 一个角色回答 | **7 个专业角色并行** |\n"
        base += "| 质量 | 可能遗漏安全/测试 | **多维度交叉验证** |\n"
        base += "| 可追溯 | 无 | **完整审计链 (SHA256)** |\n"
        base += "| 适用场景 | 简单问答 | **复杂工程任务** |\n\n"
        base += "## 核心工作流\n\n"
        base += "```\nUser Task -> [InputValidator] -> [RoleMatcher] -> [Coordinator Orchestration]\n"
        base += "           -> [ThreadPoolExecutor Parallel Workers] -> [Scratchpad Real-time Sharing]\n"
        base += "           -> [ConsensusEngine] -> [ReportFormatter] -> [Structured Report]\n```\n"
        if user_level == "beginner":
            base += "\n## 为什么选择 DevSquad？\n\n- **并行角色**：7 位专家同时工作，而非串行。\n- **共识机制**：加权投票 + 否决权确保质量。\n- **审计链**：每个决策都可通过 SHA-256 追溯。\n- **Mock 模式**：无需 API key 即可离线运行。\n"
        elif user_level == "intermediate":
            base += "\n## 核心洞见\n\nDevSquad 从单角色问答转向多角色共识，确保复杂任务的完整性。\n"
        else:
            base += "\n## TL;DR\n\n多角色共识编排，完整审计链。默认 Mock 模式。\n"
        return base

    def _content_seven_roles(self, user_level: str, lang: str) -> str:
        if lang == "en":
            header = "# 7-Role Collaboration Model\n\nDevSquad uses 7 professional roles working in parallel. Each role has trigger keywords and core responsibilities.\n\n"
            table_header = "| Role ID | Name | Trigger Keywords | Core Responsibility |\n|---------|------|-------------------|---------------------|\n"
            name_key = "name"
        elif lang == "ja":
            header = "# 7役割協力モデル\n\nDevSquadは7つの専門役割を並行して使用します。各役割にはトリガーキーワードと核心責任があります。\n\n"
            table_header = "| 役割ID | 名前 | トリガーキーワード | 核心責任 |\n|--------|------|---------------------|----------|\n"
            name_key = "name_ja"
        else:
            header = "# 7 角色协作模型\n\nDevSquad 使用 7 个专业角色并行工作。每个角色有触发关键词和核心职责。\n\n"
            table_header = "| 角色 ID | 名称 | 触发关键词 | 核心职责 |\n|---------|------|-----------|----------|\n"
            name_key = "name_zh"

        rows = ""
        for r in SEVEN_ROLES:
            rows += f"| `{r['id']}` | {r[name_key]} | {r['triggers']} | {r['responsibility']} |\n"

        notes = ""
        if user_level == "beginner":
            if lang == "en":
                notes = "\n## CLI Short IDs\n\n`arch`, `pm`, `sec`, `test`, `coder`, `infra`, `ui`\n\n## Auto-match Rule\n\nWhen roles are not specified, the system automatically matches the best role combination based on task keywords.\n"
            elif lang == "ja":
                notes = "\n## CLI短縮ID\n\n`arch`, `pm`, `sec`, `test`, `coder`, `infra`, `ui`\n\n## 自動マッチルール\n\n役割が指定されていない場合、タスクキーワードに基づいて最適な役割組み合わせを自動マッチします。\n"
            else:
                notes = "\n## CLI 短 ID\n\n`arch`, `pm`, `sec`, `test`, `coder`, `infra`, `ui`\n\n## 自动匹配规则\n\n当未指定角色时，系统会根据任务关键词自动匹配最佳角色组合。\n"
        elif user_level == "intermediate":
            if lang == "en":
                notes = "\n**Auto-match**: Roles auto-selected from task keywords. CLI short IDs: arch/pm/sec/test/coder/infra/ui.\n"
            else:
                notes = "\n**自动匹配**：根据任务关键词自动选择角色。CLI 短 ID: arch/pm/sec/test/coder/infra/ui。\n"
        else:
            notes = "\n7 roles, auto-match by keywords. CLI: arch/pm/sec/test/coder/infra/ui.\n"

        return header + table_header + rows + notes

    def _content_lifecycle(self, user_level: str, lang: str) -> str:
        if lang == "en":
            header = "# 11-Phase Project Lifecycle\n\nDevSquad projects follow an 11-phase lifecycle with mandatory gates.\n\n"
            table_header = "| # | Phase | Lead | Reviewers | Optional | Gate |\n|---|-------|------|-----------|----------|------|\n"
            dep_header = "\n## Dependency Graph\n\n```\n"
            template_header = "\n## Lifecycle Templates\n\n"
            template_table_header = "| Template | Phases | Use Case |\n|----------|--------|----------|\n"
        elif lang == "ja":
            header = "# 11フェーズプロジェクトライフサイクル\n\nDevSquadプロジェクトは必須ゲートを持つ11フェーズライフサイクルに従います。\n\n"
            table_header = "| # | フェーズ | リード | レビューアー | オプション | ゲート |\n|---|---------|--------|-------------|-----------|--------|\n"
            dep_header = "\n## 依存グラフ\n\n```\n"
            template_header = "\n## ライフサイクルテンプレート\n\n"
            template_table_header = "| テンプレート | フェーズ | ユースケース |\n|-------------|---------|-------------|\n"
        else:
            header = "# 11 阶段项目生命周期\n\nDevSquad 项目遵循 11 阶段生命周期，每阶段有强制门禁。\n\n"
            table_header = "| # | 阶段 | 主导 | 评审人 | 可选 | 门禁 |\n|---|------|------|--------|------|------|\n"
            dep_header = "\n## 依赖图\n\n```\n"
            template_header = "\n## 生命周期模板\n\n"
            template_table_header = "| 模板 | 阶段 | 用例 |\n|------|------|------|\n"

        dep_graph = "P1 -> P2 --+--> P3 --> P6 --> P7 --> P8 --> P9 --> P10 --> P11\n"
        dep_graph += "           |--> P4(parallel P3) --^\n"
        dep_graph += "           +--> P5(dep P1+P3) --^\n```\n"

        rows = ""
        for p in LIFECYCLE_PHASES:
            opt = "yes" if p["optional"] else "no"
            rows += f"| {p['phase']} | {p['name']} | {p['lead']} | {p['reviewers']} | {opt} | {p['gate']} |\n"

        template_rows = ""
        for t in LIFECYCLE_TEMPLATES:
            template_rows += f"| `{t['template']}` | {t['phases']} | {t['use_case']} |\n"

        notes = ""
        if user_level == "beginner":
            if lang == "en":
                notes = "\n## Gate Mechanism\n\n- **Mandatory**: Every phase gate must be checked.\n- **Non-blocking on failure**: Generate gap report -> user decides.\n- **Traceability**: All gate results recorded to checkpoints.\n"
            else:
                notes = "\n## 门禁机制\n\n- **强制**：每阶段门禁必须检查。\n- **失败非阻塞**：生成 gap 报告 -> 用户决定。\n- **可追溯**：所有门禁结果记录到 checkpoints。\n"
        elif user_level == "intermediate":
            notes = "\nGate: mandatory check, non-blocking on failure with gap report.\n"
        else:
            notes = "\n11 phases, 5 templates (full/backend/frontend/internal_tool/minimal). Gates non-blocking with gap reports.\n"

        return header + table_header + rows + dep_header + dep_graph + template_header + template_table_header + template_rows + notes

    def _content_iron_rules(self, user_level: str, lang: str) -> str:
        if lang == "en":
            header = "# Three Iron Rules\n\nDevSquad enforces three Iron Rules. Violating any rule is a serious error.\n\n"
            rule_template = "## Iron Rule {n}: {name}\n\n**Core Principle**: {principle}\n\n**Violation Consequence**: {consequence}\n\n"
            closing = "## Why Iron Rules?\n\nIron Rules prevent: undocumented changes, hidden bugs via assertion modification, and happy-path-only tests that miss 50%+ of issues.\n"
        elif lang == "ja":
            header = "# 三大鉄則\n\nDevSquadは3つの鉄則を強制します。いずれかの違反は深刻なエラーです。\n\n"
            rule_template = "## 鉄則 {n}: {name}\n\n**核心原則**: {principle}\n\n**違反結果**: {consequence}\n\n"
            closing = "## なぜ鉄則?\n\n鉄則は防止します: 未文書化の変更、アサーション変更による隠蔽バグ、ハッピーパスのみのテスト。\n"
        else:
            header = "# 三大 Iron Rules 铁律\n\nDevSquad 强制执行三条 Iron Rules。违反任何一条都是严重错误。\n\n"
            rule_template = "## Iron Rule {n}: {name}\n\n**核心原则**：{principle}\n\n**违规后果**：{consequence}\n\n"
            closing = "## 为什么需要 Iron Rules？\n\nIron Rules 防止：未文档化的变更、通过修改断言隐藏 bug、只测 happy path 而遗漏 50%+ 的问题。\n"

        body = ""
        name_key = "name" if lang == "en" else ("name_ja" if lang == "ja" else "name_zh")
        for i, rule in enumerate(IRON_RULES, 1):
            body += rule_template.format(
                n=i,
                name=rule[name_key],
                principle=rule["principle"],
                consequence=rule["violation_consequence"],
            )

        if user_level == "advanced":
            closing = "\n3 Iron Rules: Documentation First (supreme), Test (3 sub-rules), Delivery (closed-loop).\n"

        return header + body + closing

    def _content_sub_skills(self, user_level: str, lang: str) -> str:
        if lang == "en":
            header = "# 6 Atomic Sub-Skills\n\nDevSquad provides 6 atomic sub-skills usable independently or together. Each is a thin wrapper (~50 lines) importing existing core modules.\n\n"
            table_header = "| Skill | Class | Core Method | Wraps | Description |\n|-------|-------|-------------|-------|-------------|\n"
            usage = "\n## Usage\n\n```python\nfrom skills import get_skill, list_skills\nprint(list_skills())  # ['dispatch', 'intent', 'review', 'security', 'test', 'retrospective', 'teach']\n\nskill = get_skill('security')\nresult = skill.scan_input('DROP TABLE users; --')\nprint(result['risk_level'])  # 'critical'\n```\n"
        elif lang == "ja":
            header = "# 6個の原子サブスキル\n\nDevSquadは6個の原子サブスキルを提供します。それぞれは~50行の薄いラッパーで既存コアモジュールをインポートします。\n\n"
            table_header = "| スキル | クラス | コアメソッド | ラップ | 説明 |\n|--------|--------|-------------|--------|------|\n"
            usage = "\n## 使用方法\n\n```python\nfrom skills import get_skill, list_skills\nprint(list_skills())\n\nskill = get_skill('security')\nresult = skill.scan_input('DROP TABLE users; --')\nprint(result['risk_level'])  # 'critical'\n```\n"
        else:
            header = "# 6 个原子 Sub-Skill\n\nDevSquad 提供 6 个原子 sub-skill，可独立或组合使用。每个是 ~50 行的薄包装，导入现有核心模块。\n\n"
            table_header = "| Skill | Class | Core Method | Wraps | 描述 |\n|-------|-------|-------------|-------|------|\n"
            usage = "\n## 使用示例\n\n```python\nfrom skills import get_skill, list_skills\nprint(list_skills())  # ['dispatch', 'intent', 'review', 'security', 'test', 'retrospective', 'teach']\n\nskill = get_skill('security')\nresult = skill.scan_input('DROP TABLE users; --')\nprint(result['risk_level'])  # 'critical'\n```\n"

        rows = ""
        for s in SUB_SKILLS:
            rows += f"| `{s['name']}` | `{s['class']}` | `{s['core_method']}` | {s['wraps']} | {s['description']} |\n"

        mock_note = ""
        if user_level == "beginner":
            if lang == "en":
                mock_note = "\n## Mock Mode\n\nAll 6 sub-skills work **without any API key** in Mock mode. Output is template-based but structurally identical to real mode.\n"
            else:
                mock_note = "\n## Mock 模式\n\n所有 6 个 sub-skill 在 Mock 模式下**无需 API key**即可工作。输出基于模板，但结构与真实模式一致。\n"
        elif user_level == "advanced":
            mock_note = "\nAll sub-skills: Mock-mode default, structurally identical to real mode.\n"

        return header + table_header + rows + usage + mock_note

    def _content_glossary(self, user_level: str, lang: str) -> str:
        if lang == "en":
            header = "# Glossary\n\nKey DevSquad terminology. Source: GLOSSARY.md (canonical).\n\n"
            table_header = "| Term | Definition |\n|------|------------|\n"
        elif lang == "ja":
            header = "# 用語集\n\nDevSquad主要用語。出典: GLOSSARY.md。\n\n"
            table_header = "| 用語 | 定義 |\n|------|------|\n"
        else:
            header = "# 术语表 Glossary\n\nDevSquad 核心术语。来源：GLOSSARY.md（权威）。\n\n"
            table_header = "| 术语 | 定义 |\n|------|------|\n"

        terms = self._load_glossary_terms()
        # For advanced, show only DevSquad-specific terms (skip UI/UX and architecture vocabulary)
        if user_level == "advanced":
            terms = [t for t in terms if t["term"] in (
                "Coordinator", "Worker", "Scratchpad", "ConsensusEngine",
                "Iron Rule", "Gate", "Loop Engineering", "Adversarial Verify",
                "Autonomous Loop", "Plugin Hot Loader", "DispatchResult", "Anchor",
            )]

        rows = ""
        for t in terms:
            rows += f"| **{t['term']}** | {t['definition']} |\n"

        return header + table_header + rows

    def _content_quickstart(self, user_level: str, lang: str) -> str:
        if lang == "en":
            content = "# 5-Minute Quickstart\n\n## Step 1: Install\n\n```bash\npip install devsquad\n```\n\n## Step 2: Dispatch (Mock Mode)\n\n```python\nfrom scripts.collaboration.dispatcher import MultiAgentDispatcher\n\ndisp = MultiAgentDispatcher()\nresult = disp.dispatch('Design a secure user authentication system')\nprint(result.to_markdown())\ndisp.shutdown()\n```\n\n## Step 3: View Result\n\nThe structured report includes:\n- Architect recommendation: JWT + Refresh Token scheme\n- Security review: defend against CSRF, XSS, SQL injection\n- Test strategy: unit test coverage >= 90%\n- Implementation: complete code framework\n- Consensus: feasible, risk controllable\n\n## Step 4: CLI Usage\n\n```bash\npython3 scripts/cli.py dispatch -t 'Design a simple REST API'\n```\n"
            if user_level == "beginner":
                content += "\n## Tips\n\n- Mock mode works offline (no API key needed).\n- Use `disp.shutdown()` for clean resource cleanup.\n- For real LLM output, set `OPENAI_API_KEY` env var.\n"
        elif lang == "ja":
            content = "# 5分クイックスタート\n\n## ステップ1: インストール\n\n```bash\npip install devsquad\n```\n\n## ステップ2: ディスパッチ(モックモード)\n\n```python\nfrom scripts.collaboration.dispatcher import MultiAgentDispatcher\n\ndisp = MultiAgentDispatcher()\nresult = disp.dispatch('安全なユーザー認証システムを設計')\nprint(result.to_markdown())\ndisp.shutdown()\n```\n\n## ステップ3: 結果確認\n\n構造化レポートには以下が含まれます:\n- アーキテクト推奨: JWT + Refresh Token\n- セキュリティレビュー: CSRF/XSS/SQLインジェクション対策\n- テスト戦略: カバレッジ >= 90%\n- 実装: 完全コードフレームワーク\n- 合意: 実行可能、リスク管理可能\n\n## ステップ4: CLI使用\n\n```bash\npython3 scripts/cli.py dispatch -t 'REST APIを設計'\n```\n"
        else:
            content = "# 5 分钟快速上手\n\n## 步骤 1：安装\n\n```bash\npip install devsquad\n```\n\n## 步骤 2：运行 dispatch（Mock 模式）\n\n```python\nfrom scripts.collaboration.dispatcher import MultiAgentDispatcher\n\ndisp = MultiAgentDispatcher()\nresult = disp.dispatch('设计一个安全的用户认证系统')\nprint(result.to_markdown())\ndisp.shutdown()\n```\n\n## 步骤 3：查看结果\n\n结构化报告包含：\n- 架构师建议：JWT + Refresh Token 方案\n- 安全专家审查：防范 CSRF、XSS、SQL 注入\n- 测试策略：单元测试覆盖率 >= 90%\n- 开发实现：完整代码框架\n- 共识结论：方案可行，风险可控\n\n## 步骤 4：CLI 用法\n\n```bash\npython3 scripts/cli.py dispatch -t '设计一个简单的 REST API'\n```\n"
            if user_level == "beginner":
                content += "\n## 小贴士\n\n- Mock 模式离线可用（无需 API key）。\n- 使用 `disp.shutdown()` 清理资源。\n- 真实 LLM 输出需设置 `OPENAI_API_KEY` 环境变量。\n"
        return content

    def _teach_full_curriculum(self, user_level: str, lang: str) -> dict:
        """Teach all topics in order, adjusted for user_level."""
        sections = []
        total_minutes = 0
        all_examples: list[dict] = []
        all_exercises: list[str] = []
        all_glossary: list[dict] = []

        for topic in CURRICULUM_ORDER:
            result = self.teach(topic, user_level=user_level, lang=lang)
            sections.append(f"## {result['title']}\n\n{result['content']}")
            total_minutes += result["estimated_minutes"]
            all_examples.extend(result["examples"])
            all_exercises.extend(result["exercises"])
            all_glossary.extend(result["glossary_terms"])

        # Deduplicate glossary terms by term name
        seen: set[str] = set()
        unique_glossary: list[dict] = []
        for t in all_glossary:
            if t["term"] not in seen:
                seen.add(t["term"])
                unique_glossary.append(t)

        title = TOPIC_TITLES["full_curriculum"][lang]
        content = f"# {title}\n\n" + "\n\n---\n\n".join(sections)

        return {
            "topic": "full_curriculum",
            "user_level": user_level,
            "lang": lang,
            "title": title,
            "content": content,
            "examples": all_examples,
            "exercises": all_exercises,
            "next_topic": None,
            "glossary_terms": unique_glossary,
            "estimated_minutes": total_minutes,
        }

    # ===== Examples builders =====

    def _build_examples(self, topic: str, lang: str) -> list[dict]:
        """Build examples for a topic."""
        examples_map = {
            "overview": self._examples_overview(lang),
            "seven_roles": self._examples_seven_roles(lang),
            "lifecycle": self._examples_lifecycle(lang),
            "iron_rules": self._examples_iron_rules(lang),
            "sub_skills": self._examples_sub_skills(lang),
            "glossary": self._examples_glossary(lang),
            "quickstart": self._examples_quickstart(lang),
        }
        return examples_map.get(topic, [])

    def _examples_overview(self, lang: str) -> list[dict]:
        if lang == "en":
            return [
                {
                    "scenario": "User submits a complex engineering task",
                    "code": "from scripts.collaboration.dispatcher import MultiAgentDispatcher\ndisp = MultiAgentDispatcher()\nresult = disp.dispatch('Design user authentication system')\nprint(result.to_markdown())",
                    "explanation": "Single dispatch triggers 7-role parallel collaboration with consensus.",
                },
            ]
        return [
            {
                "scenario": "用户提交一个复杂工程任务",
                "code": "from scripts.collaboration.dispatcher import MultiAgentDispatcher\ndisp = MultiAgentDispatcher()\nresult = disp.dispatch('设计用户认证系统')\nprint(result.to_markdown())",
                "explanation": "单次 dispatch 触发 7 角色并行协作与共识。",
            },
        ]

    def _examples_seven_roles(self, lang: str) -> list[dict]:
        if lang == "en":
            return [
                {
                    "scenario": "Specify roles explicitly",
                    "code": "result = disp.dispatch('Design auth system', roles=['architect', 'security', 'tester'])",
                    "explanation": "Override auto-match by specifying roles: architect + security + tester for auth design.",
                },
                {
                    "scenario": "Auto-match by keywords",
                    "code": "result = disp.dispatch('Fix the SQL injection vulnerability')",
                    "explanation": "Keywords 'SQL injection' auto-trigger security role.",
                },
            ]
        return [
            {
                "scenario": "显式指定角色",
                "code": "result = disp.dispatch('设计认证系统', roles=['architect', 'security', 'tester'])",
                "explanation": "通过指定角色覆盖自动匹配：架构师 + 安全 + 测试用于认证设计。",
            },
            {
                "scenario": "通过关键词自动匹配",
                "code": "result = disp.dispatch('修复 SQL 注入漏洞')",
                "explanation": "关键词 'SQL 注入' 自动触发 security 角色。",
            },
        ]

    def _examples_lifecycle(self, lang: str) -> list[dict]:
        if lang == "en":
            return [
                {
                    "scenario": "Use minimal template for quick MVP",
                    "code": "# Minimal template: P1, P3, P7, P8, P9\n# Skips architecture/data/UI/security/deployment/ops phases",
                    "explanation": "Minimal template is ideal for prototyping or quick MVP validation.",
                },
            ]
        return [
            {
                "scenario": "使用 minimal 模板快速 MVP",
                "code": "# minimal 模板: P1, P3, P7, P8, P9\n# 跳过架构/数据/UI/安全/部署/运维阶段",
                "explanation": "minimal 模板适合原型或快速 MVP 验证。",
            },
        ]

    def _examples_iron_rules(self, lang: str) -> list[dict]:
        if lang == "en":
            return [
                {
                    "scenario": "Iron Rule 1 violation: guessing API params from memory",
                    "code": "# WRONG: result = obj.method(bad_param='value')\n# CORRECT: Read source to confirm signature first\nfrom scripts.collaboration.test_quality_guard import quick_audit\nreport = quick_audit('module.py', 'module_test.py')",
                    "explanation": "Always read source before writing tests. Use TestQualityGuard.quick_audit() for auto-detection.",
                },
                {
                    "scenario": "Iron Rule 2 violation: modifying assertions to pass",
                    "code": "# WRONG: assertTrue(result > 0)  # 0.0 threshold always passes\n# CORRECT: assertEqual(result, expected_value)",
                    "explanation": "On failure, analyze root cause. Never weaken assertions to make tests pass.",
                },
            ]
        return [
            {
                "scenario": "Iron Rule 1 违规：从记忆猜测 API 参数",
                "code": "# 错误: result = obj.method(bad_param='value')\n# 正确: 先读源码确认签名\nfrom scripts.collaboration.test_quality_guard import quick_audit\nreport = quick_audit('module.py', 'module_test.py')",
                "explanation": "写测试前必须读源码。使用 TestQualityGuard.quick_audit() 自动检测。",
            },
            {
                "scenario": "Iron Rule 2 违规：修改断言以通过",
                "code": "# 错误: assertTrue(result > 0)  # 0.0 阈值永远通过\n# 正确: assertEqual(result, expected_value)",
                "explanation": "失败时分析根因，绝不通过弱化断言让测试通过。",
            },
        ]

    def _examples_sub_skills(self, lang: str) -> list[dict]:
        if lang == "en":
            return [
                {
                    "scenario": "Use intent skill standalone",
                    "code": "from skills.intent.handler import IntentSkill\nintent = IntentSkill().detect('Fix login bug', lang='en')\nprint(intent['intent'])  # 'bug_fix'",
                    "explanation": "Each sub-skill is independently usable via direct import or registry.",
                },
            ]
        return [
            {
                "scenario": "独立使用 intent skill",
                "code": "from skills.intent.handler import IntentSkill\nintent = IntentSkill().detect('修复登录bug', lang='zh')\nprint(intent['intent'])  # 'bug_fix'",
                "explanation": "每个 sub-skill 可通过直接导入或 registry 独立使用。",
            },
        ]

    def _examples_glossary(self, lang: str) -> list[dict]:  # noqa: ARG002
        return [
            {
                "scenario": "Look up 'Scratchpad' meaning",
                "code": "# Scratchpad: Shared blackboard for real-time info exchange between Workers.",
                "explanation": "Glossary provides canonical definitions for DevSquad terminology.",
            },
        ]

    def _examples_quickstart(self, lang: str) -> list[dict]:
        if lang == "en":
            return [
                {
                    "scenario": "Run first dispatch in Mock mode",
                    "code": "from scripts.collaboration.dispatcher import MultiAgentDispatcher\ndisp = MultiAgentDispatcher()\nresult = disp.dispatch('Design a simple REST API')\nprint(f'Success: {result.success}')\ndisp.shutdown()",
                    "explanation": "Mock mode works offline. Always call disp.shutdown() for cleanup.",
                },
            ]
        return [
            {
                "scenario": "Mock 模式首次运行 dispatch",
                "code": "from scripts.collaboration.dispatcher import MultiAgentDispatcher\ndisp = MultiAgentDispatcher()\nresult = disp.dispatch('设计一个简单的 REST API')\nprint(f'Success: {result.success}')\ndisp.shutdown()",
                "explanation": "Mock 模式离线可用。务必调用 disp.shutdown() 清理资源。",
            },
        ]

    # ===== Exercises builders =====

    def _build_exercises(self, topic: str, user_level: str, lang: str) -> list[str]:
        """Build practice exercises for a topic."""
        exercises_map = {
            "overview": self._exercises_overview(user_level, lang),
            "seven_roles": self._exercises_seven_roles(user_level, lang),
            "lifecycle": self._exercises_lifecycle(user_level, lang),
            "iron_rules": self._exercises_iron_rules(user_level, lang),
            "sub_skills": self._exercises_sub_skills(user_level, lang),
            "glossary": self._exercises_glossary(user_level, lang),
            "quickstart": self._exercises_quickstart(user_level, lang),
        }
        return exercises_map.get(topic, [])

    def _exercises_overview(self, user_level: str, lang: str) -> list[str]:
        if lang == "en":
            base = [
                "Describe in one sentence what DevSquad does.",
                "List 3 advantages of DevSquad over single AI.",
                "Run your first dispatch in Mock mode and print the markdown report.",
            ]
            if user_level == "advanced":
                base.append("Identify the 5 core modules in the workflow chain.")
        else:
            base = [
                "用一句话描述 DevSquad 是什么。",
                "列出 DevSquad 相比单 AI 的 3 个优势。",
                "在 Mock 模式下运行你的第一次 dispatch 并打印 markdown 报告。",
            ]
            if user_level == "advanced":
                base.append("识别工作流链中的 5 个核心模块。")
        return base

    def _exercises_seven_roles(self, user_level: str, lang: str) -> list[str]:
        if lang == "en":
            base = [
                "List all 7 roles with their core responsibilities.",
                "Match task keywords to appropriate roles: 'Fix SQL injection', 'Design microservice', 'Add unit tests'.",
                "Use CLI short IDs to dispatch a task with 3 specific roles.",
            ]
            if user_level == "beginner":
                base.append("Explain when to use auto-match vs explicit role specification.")
        else:
            base = [
                "列出全部 7 个角色及其核心职责。",
                "将任务关键词匹配到合适角色：'修复 SQL 注入'、'设计微服务'、'添加单元测试'。",
                "使用 CLI 短 ID dispatch 一个任务，指定 3 个角色。",
            ]
            if user_level == "beginner":
                base.append("解释何时使用自动匹配 vs 显式指定角色。")
        return base

    def _exercises_lifecycle(self, user_level: str, lang: str) -> list[str]:
        if lang == "en":
            base = [
                "List all 11 phases in order with their leads.",
                "Identify which phases are optional vs mandatory.",
                "Choose the right template for: a backend service, an internal tool, a complete product.",
            ]
            if user_level == "advanced":
                base.append("Draw the dependency graph from memory and explain P4/P5 parallelism.")
        else:
            base = [
                "按顺序列出全部 11 个阶段及其主导角色。",
                "识别哪些阶段是可选的，哪些是强制的。",
                "为以下场景选择正确模板：后端服务、内部工具、完整产品。",
            ]
            if user_level == "advanced":
                base.append("凭记忆画出依赖图，解释 P4/P5 并行性。")
        return base

    def _exercises_iron_rules(self, user_level: str, lang: str) -> list[str]:
        if lang == "en":
            base = [
                "State the 3 Iron Rules and their core principles.",
                "Give an example of violating each Iron Rule.",
                "Run TestQualityGuard.quick_audit() on a test file and report findings.",
            ]
            if user_level == "beginner":
                base.append("Explain why 'modify assertions to pass' is a critical error.")
        else:
            base = [
                "陈述 3 条 Iron Rules 及其核心原则。",
                "举例说明每条 Iron Rule 的违规场景。",
                "对一个测试文件运行 TestQualityGuard.quick_audit() 并报告发现。",
            ]
            if user_level == "beginner":
                base.append("解释为什么'修改断言以通过'是严重错误。")
        return base

    def _exercises_sub_skills(self, user_level: str, lang: str) -> list[str]:  # noqa: ARG002
        if lang == "en":
            return [
                "List all 6 sub-skills with their core methods.",
                "Use the registry to list available skills and call get_skill('intent').",
                "Run IntentSkill.detect() on a sample task and interpret the result.",
            ]
        return [
            "列出全部 6 个 sub-skill 及其核心方法。",
            "使用 registry 列出可用 skill 并调用 get_skill('intent')。",
            "对示例任务运行 IntentSkill.detect() 并解释结果。",
        ]

    def _exercises_glossary(self, user_level: str, lang: str) -> list[str]:  # noqa: ARG002
        if lang == "en":
            return [
                "Define: Coordinator, Worker, Scratchpad, ConsensusEngine.",
                "Explain the difference between Deep module and Shallow module.",
                "What is the 'Deletion test' and when to use it?",
            ]
        return [
            "定义：Coordinator、Worker、Scratchpad、ConsensusEngine。",
            "解释 Deep module 和 Shallow module 的区别。",
            "什么是 'Deletion test'？何时使用？",
        ]

    def _exercises_quickstart(self, user_level: str, lang: str) -> list[str]:  # noqa: ARG002
        if lang == "en":
            return [
                "Install DevSquad and run the status command.",
                "Dispatch your first task in Mock mode and verify the report.",
                "Try the CLI dispatch command with a custom task.",
            ]
        return [
            "安装 DevSquad 并运行 status 命令。",
            "在 Mock 模式下 dispatch 你的第一个任务并验证报告。",
            "使用 CLI dispatch 命令运行自定义任务。",
        ]

    # ===== Glossary helpers =====

    def _load_glossary_terms(self) -> list[dict]:
        """Load glossary terms from GLOSSARY.md or fall back to built-in."""
        try:
            if self._GLOSSARY_PATH.exists():
                content = self._GLOSSARY_PATH.read_text(encoding="utf-8")
                parsed = self._parse_glossary_md(content)
                if parsed:
                    return parsed
        except Exception:
            pass
        return BUILTIN_GLOSSARY

    @staticmethod
    def _parse_glossary_md(content: str) -> list[dict]:
        """Parse GLOSSARY.md table rows into term/definition dicts.

        Supports 2-column (| term | definition |) and 3-column
        (| term | definition | source |) tables. Skips separator rows.
        """
        terms: list[dict] = []
        in_table = False
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                in_table = False
                continue
            # Skip separator rows (e.g., |---|---|---|) without resetting state
            if all(c in "|-: " for c in stripped):
                continue
            parts = [p.strip() for p in stripped.strip("|").split("|")]
            if len(parts) < 2:
                continue
            term_raw = parts[0]
            definition = parts[1]
            # Detect header row (term/definition/术语/定义)
            lower_term = term_raw.lower()
            if "term" in lower_term or "术语" in term_raw or "用語" in term_raw:
                in_table = True
                continue
            if not in_table:
                continue
            # Strip markdown bold markers
            term = term_raw.strip("*").strip()
            if term and definition:
                terms.append({"term": term, "definition": definition})
        return terms

    def _related_glossary_terms(self, topic: str) -> list[dict]:
        """Return glossary terms related to a specific topic."""
        all_terms = self._load_glossary_terms()
        topic_keywords = {
            "overview": ["Coordinator", "Worker", "Scratchpad", "ConsensusEngine", "DispatchResult"],
            "seven_roles": ["Worker", "Coordinator", "ConsensusEngine"],
            "lifecycle": ["Gate", "Anchor", "Loop Engineering"],
            "iron_rules": ["Iron Rule", "Tautological test", "Red-capable", "ADR"],
            "sub_skills": ["DispatchResult", "Coordinator", "Worker"],
            "glossary": [t["term"] for t in all_terms[:10]],
            "quickstart": ["Coordinator", "DispatchResult", "Worker"],
        }
        keywords = topic_keywords.get(topic, [])
        return [t for t in all_terms if t["term"] in keywords]

    # ===== Assessment helpers =====

    def _assessment_key(self, topic: str) -> dict[str, str]:
        """Return the answer key for a topic assessment."""
        keys = {
            "overview": {
                "q1": "7",
                "q2": "consensus",
                "q3": "mock",
            },
            "seven_roles": {
                "q1": "architect",
                "q2": "security",
                "q3": "tester",
            },
            "lifecycle": {
                "q1": "11",
                "q2": "pm",
                "q3": "minimal",
            },
            "iron_rules": {
                "q1": "documentation",
                "q2": "3",
                "q3": "regression",
            },
            "sub_skills": {
                "q1": "6",
                "q2": "intent",
                "q3": "security",
            },
            "glossary": {
                "q1": "shared",
                "q2": "veto",
                "q3": "iron",
            },
            "quickstart": {
                "q1": "pip",
                "q2": "mock",
                "q3": "shutdown",
            },
            "full_curriculum": {
                "q1": "7",
                "q2": "11",
                "q3": "3",
            },
        }
        return keys.get(topic, {})

    @staticmethod
    def _answers_match(user_ans: Any, expected: str) -> bool:
        """Check if user answer matches expected (case-insensitive substring)."""
        if user_ans is None:
            return False
        user_str = str(user_ans).strip().lower()
        expected_lower = expected.lower()
        return expected_lower in user_str or user_str in expected_lower

    def _build_recommendations(self, topic: str, score: float, incorrect: list[str]) -> list[str]:
        """Build recommendations based on assessment score."""
        recs: list[str] = []
        if score >= 0.9:
            recs.append(f"Excellent! You've mastered {topic}. Ready for next topic.")
        elif score >= 0.7:
            recs.append(f"Good understanding of {topic}. Review incorrect answers and proceed.")
        else:
            recs.append(f"Needs improvement on {topic}. Re-read the lesson and try again.")

        if incorrect:
            next_topic = NEXT_TOPIC.get(topic)
            if next_topic:
                recs.append(f"Recommended next: study '{next_topic}' after reviewing.")
            recs.append(f"Focus on questions: {', '.join(incorrect)}")
        return recs

    def _graduation_criteria(self, user_level: str) -> list[str]:
        """Return graduation criteria for a user level."""
        if user_level == "beginner":
            return [
                "Pass assessment on all 7 topics with score >= 0.7",
                "Run first dispatch in Mock mode successfully",
                "Explain 7 roles and 3 Iron Rules from memory",
                "Complete 5-minute quickstart without errors",
            ]
        if user_level == "intermediate":
            return [
                "Pass assessment on 6 core topics with score >= 0.7",
                "Choose correct lifecycle template for given scenario",
                "Identify Iron Rule violations in code samples",
            ]
        return [
            "Pass assessment on 4 advanced topics with score >= 0.8",
            "Design a complete DevSquad workflow for a real project",
            "Architect custom role combinations for niche scenarios",
        ]
