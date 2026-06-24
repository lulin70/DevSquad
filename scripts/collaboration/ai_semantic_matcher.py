#!/usr/bin/env python3
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .models import ROLE_REGISTRY

logger = logging.getLogger(__name__)


@dataclass
class SemanticMatchResult:
    role_id: str
    role_name: str
    confidence: float
    reasoning: str
    matched_capabilities: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    explanation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class AISemanticMatcher:
    """
    AI-powered semantic role matcher.

    Uses LLM backend for deep semantic understanding of task requirements,
    falling back to keyword matching when no LLM is available.

    Workflow:
    1. Analyze task requirements, extract key semantic info
    2. Understand role capabilities and responsibilities
    3. Match based on semantic similarity
    4. Generate explainable matching results
    """

    MATCH_PROMPT_TEMPLATE = """You are an intelligent role matching expert. Analyze the following task and match the most suitable roles.

## Task
**Description**: {task_description}
**Required capabilities**: {required_capabilities}

## Available Roles
{role_descriptions}

## Requirements
1. Analyze the core needs and key capability requirements of the task
2. Evaluate each role's match with the task
3. Consider the role's professional capabilities and experience
4. Provide matching reasons and confidence scores

Return the matching results in JSON format:
{{
    "matches": [
        {{
            "role_id": "role ID",
            "role_name": "role name",
            "confidence": 0.0-1.0,
            "reasoning": "matching reasoning",
            "matched_capabilities": ["matched capability list"],
            "relevance_score": 0.0-1.0,
            "explanation": "detailed explanation"
        }}
    ],
    "best_match": "best match role ID",
    "analysis": "overall analysis"
}}"""

    def __init__(self, llm_backend: Any = None) -> None:
        self.llm_backend = llm_backend
        self.match_cache: dict[str, SemanticMatchResult] = {}
        self.match_history: list[dict[str, Any]] = []

    def match(
        self,
        task_description: str,
        required_capabilities: list[str] | None = None,
        _preferred_skills: list[str] | None = None,
        use_cache: bool = True,
    ) -> list[SemanticMatchResult]:
        """
        Perform intelligent role matching using AI.

        Args:
            task_description: Task description text
            required_capabilities: Required capability list
            preferred_skills: Preferred skill list
            use_cache: Whether to use cached results

        Returns:
            List[SemanticMatchResult]: Matched results sorted by confidence
        """
        cache_key = self._generate_cache_key(task_description)

        if use_cache and cache_key in self.match_cache:
            logger.info("Using cached match result")
            return [self.match_cache[cache_key]]

        roles = self._build_role_list()
        role_descriptions = self._build_role_descriptions(roles)

        if self.llm_backend:
            try:
                prompt = self.MATCH_PROMPT_TEMPLATE.format(
                    task_description=task_description,
                    required_capabilities=required_capabilities or [],
                    role_descriptions=role_descriptions,
                )
                ai_response = self.llm_backend.generate(prompt)
                results = self._parse_ai_response(ai_response, roles)

                if results and use_cache:
                    self.match_cache[cache_key] = results[0]

                self._record_match(task_description, results)
                return results
            except (RuntimeError, ValueError, TypeError, ConnectionError) as e:
                logger.warning("AI matching failed, falling back to keyword: %s", e)

        results = self._keyword_match(task_description, roles)
        self._record_match(task_description, results)
        return results

    def _build_role_list(self) -> list[dict[str, Any]]:
        roles = []
        for role_id, rdef in ROLE_REGISTRY.items():
            if rdef.status == "core":
                roles.append(
                    {
                        "id": role_id,
                        "name": rdef.name,
                        "description": rdef.description,
                        "capabilities": rdef.keywords,
                        "skills": rdef.keywords[:3],
                        "keywords": rdef.keywords,
                    }
                )
        return roles

    def _build_role_descriptions(self, roles: list[dict[str, Any]]) -> str:
        descriptions = []
        for i, role in enumerate(roles, 1):
            desc = f"{i}. **{role.get('name', 'Unknown')}** ({role.get('id', 'unknown')})\n"
            desc += f"   - Responsibilities: {role.get('description', '')}\n"
            desc += f"   - Capabilities: {', '.join(role.get('capabilities', []))}\n"
            descriptions.append(desc)
        return "\n".join(descriptions)

    EN_KEYWORD_MAP = {
        "architect": [
            "architecture",
            "design",
            "system",
            "microservice",
            "tech stack",
            "api design",
            "performance",
            "module",
            "interface",
        ],
        "product-manager": [
            "requirement",
            "prd",
            "user story",
            "product",
            "feature",
            "acceptance",
            "competitive",
            "experience",
        ],
        "tester": [
            "test",
            "quality",
            "qa",
            "automated",
            "performance test",
            "bug",
            "defect",
            "verification",
            "edge case",
        ],
        "solo-coder": ["implement", "develop", "code", "fix", "optimize", "refactor", "review", "best practice"],
        "ui-designer": ["ui", "interface", "frontend", "visual", "interaction", "prototype", "ux", "accessibility"],
        "devops": ["ci/cd", "deploy", "monitor", "infrastructure", "docker", "kubernetes", "container", "devops"],
        "security": ["security", "vulnerability", "audit", "threat", "encryption", "auth", "owasp", "compliance"],
    }

    def _keyword_match(self, task_description: str, roles: list[dict[str, Any]]) -> list[SemanticMatchResult]:
        task_lower = task_description.lower()
        results = []

        for role in roles:
            role_id = role.get("id", "")
            keywords = role.get("keywords", [])
            en_keywords = self.EN_KEYWORD_MAP.get(role_id, [])

            cn_match = sum(1 for kw in keywords if kw.lower() in task_lower)
            en_match = sum(1 for kw in en_keywords if kw.lower() in task_lower)
            match_count = cn_match + en_match

            if match_count > 0:
                confidence = min(0.5 + match_count * 0.1, 0.95)
                result = SemanticMatchResult(
                    role_id=role_id,
                    role_name=role.get("name", ""),
                    confidence=confidence,
                    reasoning=f"Keyword match: {match_count} keywords matched",
                    matched_capabilities=role.get("capabilities", [])[:3],
                    relevance_score=match_count / 10.0,
                    explanation="Task requirements are highly related to this role's responsibilities",
                )
                results.append(result)

        results.sort(key=lambda r: r.confidence, reverse=True)

        if not results:
            results.append(
                SemanticMatchResult(
                    role_id="solo-coder",
                    role_name="Solo Developer",
                    confidence=0.5,
                    reasoning="Default role: no specific keyword match",
                    matched_capabilities=["general development"],
                    relevance_score=0.3,
                    explanation="No specific role matched, using default developer role",
                )
            )

        return results

    def _parse_ai_response(self, response: str, _roles: list[dict[str, Any]]) -> list[SemanticMatchResult]:
        try:
            data = json.loads(response) if isinstance(response, str) else response

            results = []
            for match_data in data.get("matches", []):
                result = SemanticMatchResult(
                    role_id=match_data.get("role_id", ""),
                    role_name=match_data.get("role_name", ""),
                    confidence=float(match_data.get("confidence", 0.0)),
                    reasoning=match_data.get("reasoning", ""),
                    matched_capabilities=match_data.get("matched_capabilities", []),
                    relevance_score=float(match_data.get("relevance_score", 0.0)),
                    explanation=match_data.get("explanation", ""),
                    metadata={
                        "best_match": data.get("best_match"),
                        "analysis": data.get("analysis"),
                    },
                )
                results.append(result)

            results.sort(key=lambda r: r.confidence, reverse=True)
            return results
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning("Failed to parse AI response: %s", e)
            return []

    def _generate_cache_key(self, task_description: str) -> str:
        content = f"{task_description}|{len(ROLE_REGISTRY)}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _record_match(self, task_description: str, results: list[SemanticMatchResult]) -> None:
        record = {
            "task_description": task_description[:100],
            "timestamp": datetime.now().isoformat(),
            "results_count": len(results),
            "top_role": results[0].role_id if results else None,
            "top_confidence": results[0].confidence if results else 0.0,
        }
        self.match_history.append(record)

    def get_match_history(self, limit: int = 10) -> list[dict]:
        """Return the most recent semantic match records.

        Args:
            limit: Maximum number of recent records to return. Defaults to 10.

        Returns:
            List of match record dictionaries, newest last, up to ``limit``.
        """
        return self.match_history[-limit:]

    def clear_cache(self) -> None:
        """Clear all cached semantic match results."""
        self.match_cache.clear()

    def explain_match(self, result: SemanticMatchResult) -> str:
        """Build a human-readable explanation of a semantic match result.

        Args:
            result: The SemanticMatchResult to explain.

        Returns:
            Multi-line string describing role, confidence, relevance,
            reasoning, explanation, and matched capabilities.
        """
        explanation = (
            f"Match: {result.role_name} ({result.role_id})\n"
            f"Confidence: {result.confidence:.1%}\n"
            f"Relevance: {result.relevance_score:.1%}\n\n"
            f"Reasoning:\n{result.reasoning}\n\n"
            f"Explanation:\n{result.explanation}\n\n"
            f"Matched capabilities: {', '.join(result.matched_capabilities) if result.matched_capabilities else 'None'}"
        )
        return explanation
