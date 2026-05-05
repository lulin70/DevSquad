#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent Briefing System

Provides intelligent briefing generation for agents to understand:
- Project context and goals
- Current task requirements
- Historical decisions and patterns
- Team collaboration context

Usage:
    from scripts.collaboration.agent_briefing import AgentBriefing
    
    briefing = AgentBriefing(
        agent_role="Architect",
        project_context={"name": "DevSquad", "version": "3.5.0-Prod"}
    )
    
    # Generate briefing
    content = briefing.generate_briefing(
        task="Design Protocol interface system",
        context={"priority": "high"}
    )
    
    # Generate project overview
    overview = briefing.generate_project_overview(".")
    
    # Generate role-specific understanding
    understanding = briefing.generate_role_understanding("security", ".")
    
    # Update with new information
    briefing.update_briefing(
        key="decisions",
        value="Use Python Protocol for interface definition"
    )
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


logger = logging.getLogger(__name__)

_SAFE_FILENAME_RE = re.compile(r'[^\w\-.]')


@dataclass
class BriefingSection:
    """Briefing section data structure"""
    title: str
    content: str
    priority: int = 1  # 1=high, 2=medium, 3=low
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class AgentContext:
    """Agent context information"""
    role: str
    capabilities: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class AgentBriefing:
    """
    Agent Briefing Generator
    
    Features:
    - Context-aware briefing generation
    - Historical pattern recognition
    - Priority-based information filtering
    - Incremental updates
    - Persistence support
    - Project overview generation (V3.5.0)
    - Role-specific understanding generation (V3.5.0)
    """
    
    def __init__(
        self,
        agent_role: str,
        project_context: Optional[Dict[str, Any]] = None,
        storage_dir: Optional[str] = None
    ):
        self.agent_role = agent_role
        self.project_context = project_context or {}
        self.storage_dir = Path(storage_dir or "data/briefings")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.sections: Dict[str, BriefingSection] = {}
        self.agent_context = AgentContext(role=agent_role)
        
        self._load_briefing()
    
    def generate_briefing(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        max_length: Optional[int] = None
    ) -> str:
        context = context or {}
        
        briefing_parts = []
        
        briefing_parts.append(self._generate_role_section())
        briefing_parts.append(self._generate_project_section())
        briefing_parts.append(self._generate_task_section(task, context))
        
        if self.agent_context.history:
            briefing_parts.append(self._generate_history_section())
        
        sorted_sections = sorted(
            self.sections.values(),
            key=lambda s: (s.priority, -s.timestamp)
        )
        for section in sorted_sections:
            briefing_parts.append(f"## {section.title}\n\n{section.content}")
        
        full_briefing = "\n\n".join(briefing_parts)
        
        if max_length and len(full_briefing) > max_length:
            full_briefing = full_briefing[:max_length] + "\n\n[Briefing truncated...]"
        
        self._add_to_history(task, context, full_briefing)
        
        return full_briefing
    
    def generate_project_overview(self, project_root: str = ".") -> str:
        """
        Generate project overview document.

        Analyzes project structure to produce a module-level understanding
        document covering tech stack, module structure, core components,
        and dependency relationships.

        Args:
            project_root: Root directory of the project to analyze

        Returns:
            Markdown-formatted project overview document
        """
        root = Path(project_root)

        tech_stack = self._analyze_tech_stack(root)
        modules = self._identify_modules(root)
        core_components = self._identify_core_components(root)

        lines = ["# Project Overview", ""]

        lines.append("## Tech Stack")
        for category, items in tech_stack.items():
            lines.append(f"- **{category}**: {', '.join(items)}")
        lines.append("")

        lines.append("## Module Structure")
        for mod in modules:
            indent = "  " * mod.get("depth", 0)
            lines.append(f"{indent}- {mod['icon']} **{mod['name']}** — {mod['description']}")
        lines.append("")

        lines.append("## Core Components")
        for comp in core_components:
            lines.append(f"- **{comp['name']}** ({comp['file']}): {comp['description']}")
        lines.append("")

        return "\n".join(lines)

    def generate_role_understanding(
        self, role: str, project_root: str = "."
    ) -> str:
        """
        Generate role-specific project understanding document.

        Produces a tailored understanding document for a specific role,
        highlighting aspects most relevant to that role's responsibilities.

        Args:
            role: Role identifier (e.g., "architect", "security", "tester")
            project_root: Root directory of the project to analyze

        Returns:
            Markdown-formatted role-specific understanding document
        """
        root = Path(project_root)
        tech_stack = self._analyze_tech_stack(root)
        modules = self._identify_modules(root)

        role_focus = {
            "architect": {
                "title": "Architecture Understanding",
                "focus_areas": ["Module Structure", "Dependency Graph", "Design Patterns"],
                "key_questions": [
                    "Is the module decomposition following high cohesion / low coupling?",
                    "Are there circular dependencies?",
                    "Is the abstraction level appropriate?",
                ],
            },
            "security": {
                "title": "Security Understanding",
                "focus_areas": ["Authentication", "Authorization", "Data Protection", "Input Validation"],
                "key_questions": [
                    "Where are the authentication and authorization checks?",
                    "How is sensitive data protected at rest and in transit?",
                    "Are all external inputs validated?",
                ],
            },
            "tester": {
                "title": "Testing Understanding",
                "focus_areas": ["Test Coverage", "Test Strategy", "Critical Paths"],
                "key_questions": [
                    "What is the current test coverage?",
                    "Are boundary conditions and error paths tested?",
                    "What are the most critical code paths to test?",
                ],
            },
            "solo-coder": {
                "title": "Development Understanding",
                "focus_areas": ["Code Conventions", "Hot Spots", "Technical Debt"],
                "key_questions": [
                    "What are the coding conventions used?",
                    "Where are the most complex functions?",
                    "What technical debt exists?",
                ],
            },
            "devops": {
                "title": "Operations Understanding",
                "focus_areas": ["Deployment", "Monitoring", "Configuration", "Logging"],
                "key_questions": [
                    "How is the application deployed?",
                    "What metrics are monitored?",
                    "How is configuration managed across environments?",
                ],
            },
            "product-manager": {
                "title": "Product Understanding",
                "focus_areas": ["Features", "User Flows", "Acceptance Criteria"],
                "key_questions": [
                    "What features are currently implemented?",
                    "What are the core user flows?",
                    "Are all acceptance criteria met?",
                ],
            },
            "ui-designer": {
                "title": "UI/UX Understanding",
                "focus_areas": ["Component Library", "Interaction Patterns", "Accessibility"],
                "key_questions": [
                    "What UI components are available?",
                    "Are interaction patterns consistent?",
                    "Is accessibility supported?",
                ],
            },
        }

        focus = role_focus.get(role, role_focus.get("solo-coder", {}))

        lines = [f"# {focus.get('title', 'Project Understanding')}", ""]
        lines.append(f"**Role**: {role}")
        lines.append("")

        lines.append("## Focus Areas")
        for area in focus.get("focus_areas", []):
            lines.append(f"- {area}")
        lines.append("")

        lines.append("## Key Questions to Answer")
        for q in focus.get("key_questions", []):
            lines.append(f"- [ ] {q}")
        lines.append("")

        lines.append("## Tech Stack Summary")
        for category, items in tech_stack.items():
            lines.append(f"- **{category}**: {', '.join(items)}")
        lines.append("")

        lines.append("## Relevant Modules")
        for mod in modules:
            indent = "  " * mod.get("depth", 0)
            lines.append(f"{indent}- {mod['icon']} **{mod['name']}** — {mod['description']}")
        lines.append("")

        return "\n".join(lines)

    def _analyze_tech_stack(self, root: Path) -> Dict[str, List[str]]:
        """Analyze project tech stack from config files."""
        stack: Dict[str, List[str]] = {}

        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            stack["Language"] = ["Python"]
            try:
                content = pyproject.read_text(encoding="utf-8")
                if "fastapi" in content.lower():
                    stack.setdefault("Web Framework", []).append("FastAPI")
                if "streamlit" in content.lower():
                    stack.setdefault("Web Framework", []).append("Streamlit")
                if "openai" in content.lower():
                    stack.setdefault("AI Backend", []).append("OpenAI")
                if "anthropic" in content.lower():
                    stack.setdefault("AI Backend", []).append("Anthropic")
                if "sqlite" in content.lower():
                    stack.setdefault("Database", []).append("SQLite")
                if "pyyaml" in content.lower() or "yaml" in content.lower():
                    stack.setdefault("Config", []).append("YAML")
            except Exception:
                pass

        dockerfile = root / "Dockerfile"
        if dockerfile.exists():
            stack.setdefault("Deployment", []).append("Docker")

        github_dir = root / ".github"
        if github_dir.exists():
            stack.setdefault("CI/CD", []).append("GitHub Actions")

        if not stack:
            stack["Language"] = ["Unknown"]

        return stack

    def _identify_modules(self, root: Path) -> List[Dict[str, Any]]:
        """Identify project modules and their descriptions."""
        modules: List[Dict[str, Any]] = []

        known_dirs = {
            "scripts/collaboration": {"icon": "🔧", "description": "Core collaboration engine"},
            "scripts/cli": {"icon": "💻", "description": "CLI interface"},
            "scripts/dashboard": {"icon": "📊", "description": "Web dashboard"},
            "scripts/api": {"icon": "🌐", "description": "REST API server"},
            "templates/concerns": {"icon": "📦", "description": "Concern packs"},
            "docs": {"icon": "📄", "description": "Documentation"},
            "tests": {"icon": "🧪", "description": "Test suite"},
            "benchmarks": {"icon": "⚡", "description": "Performance benchmarks"},
        }

        for dir_path, info in known_dirs.items():
            full_path = root / dir_path
            if full_path.exists() and full_path.is_dir():
                py_files = list(full_path.rglob("*.py"))
                modules.append({
                    "name": dir_path,
                    "icon": info["icon"],
                    "description": f"{info['description']} ({len(py_files)} files)",
                    "depth": dir_path.count("/"),
                })

        return modules

    def _identify_core_components(self, root: Path) -> List[Dict[str, str]]:
        """Identify core components from key source files."""
        components: List[Dict[str, str]] = []

        known_components = [
            ("dispatcher.py", "MultiAgentDispatcher", "Unified dispatch entry point"),
            ("coordinator.py", "Coordinator", "Global orchestrator for multi-agent collaboration"),
            ("worker.py", "Worker", "Role execution unit"),
            ("scratchpad.py", "Scratchpad", "Shared blackboard for inter-agent communication"),
            ("consensus.py", "ConsensusEngine", "Weighted voting consensus mechanism"),
            ("five_axis_consensus.py", "FiveAxisConsensusEngine", "Five-axis code review consensus"),
            ("llm_backend.py", "LLMBackend", "Multi-backend LLM abstraction layer"),
            ("permission_guard.py", "PermissionGuard", "4-level permission control system"),
            ("input_validator.py", "InputValidator", "Input validation and injection detection"),
            ("memory_bridge.py", "MemoryBridge", "Cross-session memory management"),
            ("workflow_engine.py", "WorkflowEngine", "Task-to-workflow orchestration"),
            ("context_compressor.py", "ContextCompressor", "4-level context compression"),
            ("anti_rationalization.py", "AntiRationalizationEngine", "Anti-rationalization pattern injection"),
            ("verification_gate.py", "VerificationGate", "Evidence-based completion verification"),
        ]

        collab_dir = root / "scripts" / "collaboration"
        for filename, class_name, description in known_components:
            if (collab_dir / filename).exists():
                components.append({
                    "name": class_name,
                    "file": f"scripts/collaboration/{filename}",
                    "description": description,
                })

        return components

    def _generate_role_section(self) -> str:
        """Generate agent role section"""
        content = f"# Agent Briefing: {self.agent_role}\n\n"
        content += f"**Role**: {self.agent_role}\n\n"
        
        if self.agent_context.capabilities:
            content += "**Capabilities**:\n"
            for cap in self.agent_context.capabilities:
                content += f"- {cap}\n"
            content += "\n"
        
        if self.agent_context.constraints:
            content += "**Constraints**:\n"
            for constraint in self.agent_context.constraints:
                content += f"- {constraint}\n"
            content += "\n"
        
        return content.strip()
    
    def _generate_project_section(self) -> str:
        """Generate project context section"""
        if not self.project_context:
            return ""
        
        content = "## Project Context\n\n"
        
        for key, value in self.project_context.items():
            if isinstance(value, (list, dict)):
                content += f"**{key.replace('_', ' ').title()}**:\n"
                content += f"```json\n{json.dumps(value, indent=2)}\n```\n\n"
            else:
                content += f"**{key.replace('_', ' ').title()}**: {value}\n\n"
        
        return content.strip()
    
    def _generate_task_section(self, task: str, context: Dict[str, Any]) -> str:
        """Generate current task section"""
        content = "## Current Task\n\n"
        content += f"{task}\n\n"
        
        if context:
            content += "**Task Context**:\n"
            for key, value in context.items():
                content += f"- **{key.replace('_', ' ').title()}**: {value}\n"
            content += "\n"
        
        return content.strip()
    
    def _generate_history_section(self, limit: int = 5) -> str:
        """Generate historical context section"""
        content = "## Recent History\n\n"
        
        recent_history = self.agent_context.history[-limit:]
        for i, entry in enumerate(reversed(recent_history), 1):
            task = entry.get("task", "Unknown task")
            timestamp = entry.get("timestamp", 0)
            dt = datetime.fromtimestamp(timestamp)
            
            content += f"{i}. **{task}** ({dt.strftime('%Y-%m-%d %H:%M')})\n"
            
            if "outcome" in entry:
                content += f"   - Outcome: {entry['outcome']}\n"
            
            if "key_decisions" in entry:
                content += f"   - Key decisions: {', '.join(entry['key_decisions'])}\n"
            
            content += "\n"
        
        return content.strip()
    
    def update_briefing(
        self,
        key: str,
        value: Any,
        section: Optional[str] = None,
        priority: int = 2
    ) -> None:
        if section:
            if section not in self.sections:
                self.sections[section] = BriefingSection(
                    title=section,
                    content="",
                    priority=priority
                )
            
            if isinstance(value, str):
                self.sections[section].content += f"\n- **{key}**: {value}"
            else:
                self.sections[section].content += f"\n- **{key}**: {json.dumps(value)}"
            
            self.sections[section].timestamp = datetime.now().timestamp()
        else:
            if key == "capabilities":
                if isinstance(value, list):
                    self.agent_context.capabilities.extend(value)
                else:
                    self.agent_context.capabilities.append(value)
            elif key == "constraints":
                if isinstance(value, list):
                    self.agent_context.constraints.extend(value)
                else:
                    self.agent_context.constraints.append(value)
            elif key == "preferences":
                if isinstance(value, dict):
                    self.agent_context.preferences.update(value)
                else:
                    self.agent_context.preferences[key] = value
        
        self._save_briefing()
    
    def add_section(
        self,
        title: str,
        content: str,
        priority: int = 2,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        self.sections[title] = BriefingSection(
            title=title,
            content=content,
            priority=priority,
            metadata=metadata or {}
        )
        
        self._save_briefing()
    
    def remove_section(self, title: str) -> bool:
        if title in self.sections:
            del self.sections[title]
            self._save_briefing()
            return True
        return False
    
    def get_section(self, title: str) -> Optional[BriefingSection]:
        return self.sections.get(title)
    
    def list_sections(self) -> List[str]:
        return list(self.sections.keys())
    
    def clear_history(self) -> None:
        self.agent_context.history.clear()
        self._save_briefing()
    
    def export_briefing(self, output_path: str) -> None:
        briefing_data = {
            "agent_role": self.agent_role,
            "project_context": self.project_context,
            "agent_context": self.agent_context.to_dict(),
            "sections": {
                title: section.to_dict()
                for title, section in self.sections.items()
            },
            "exported_at": datetime.now().isoformat()
        }
        
        Path(output_path).write_text(
            json.dumps(briefing_data, indent=2),
            encoding='utf-8'
        )
        
        logger.info(f"Briefing exported to {output_path}")
    
    def _add_to_history(
        self,
        task: str,
        context: Dict[str, Any],
        briefing: str
    ) -> None:
        history_entry = {
            "task": task,
            "context": context,
            "briefing_length": len(briefing),
            "timestamp": datetime.now().timestamp()
        }
        
        self.agent_context.history.append(history_entry)
        
        if len(self.agent_context.history) > 100:
            self.agent_context.history = self.agent_context.history[-100:]
        
        self._save_briefing()
    
    def _save_briefing(self) -> None:
        try:
            safe_role = _SAFE_FILENAME_RE.sub('_', self.agent_role.lower())
            briefing_file = self.storage_dir / f"{safe_role}_briefing.json"
            
            briefing_data = {
                "agent_role": self.agent_role,
                "project_context": self.project_context,
                "agent_context": self.agent_context.to_dict(),
                "sections": {
                    title: section.to_dict()
                    for title, section in self.sections.items()
                },
                "updated_at": datetime.now().isoformat()
            }
            
            briefing_file.write_text(
                json.dumps(briefing_data, indent=2),
                encoding='utf-8'
            )
        except Exception as e:
            logger.warning(f"Failed to save briefing: {e}")
    
    def _load_briefing(self) -> None:
        try:
            safe_role = _SAFE_FILENAME_RE.sub('_', self.agent_role.lower())
            briefing_file = self.storage_dir / f"{safe_role}_briefing.json"
            
            if not briefing_file.exists():
                return
            
            briefing_data = json.loads(briefing_file.read_text(encoding='utf-8'))
            
            self.project_context = briefing_data.get("project_context", {})
            
            agent_context_data = briefing_data.get("agent_context", {})
            self.agent_context = AgentContext(**agent_context_data)
            
            sections_data = briefing_data.get("sections", {})
            for title, section_data in sections_data.items():
                self.sections[title] = BriefingSection(**section_data)
            
            logger.info(f"Loaded briefing for {self.agent_role}")
        except Exception as e:
            logger.warning(f"Failed to load briefing: {e}")


_briefing_instances: Dict[str, AgentBriefing] = {}


def get_agent_briefing(
    agent_role: str,
    project_context: Optional[Dict[str, Any]] = None,
    storage_dir: Optional[str] = None
) -> AgentBriefing:
    if agent_role not in _briefing_instances:
        _briefing_instances[agent_role] = AgentBriefing(
            agent_role=agent_role,
            project_context=project_context,
            storage_dir=storage_dir
        )
    
    return _briefing_instances[agent_role]


def reset_briefings() -> None:
    """Reset all briefing instances (for testing)"""
    global _briefing_instances
    _briefing_instances.clear()


__version__ = "1.1.0"
__all__ = [
    "AgentBriefing",
    "BriefingSection",
    "AgentContext",
    "get_agent_briefing",
    "reset_briefings",
]
