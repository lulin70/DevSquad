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
        project_context={"name": "DevSquad", "version": "3.4.0-Prod"}
    )
    
    # Generate briefing
    content = briefing.generate_briefing(
        task="Design Protocol interface system",
        context={"priority": "high"}
    )
    
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
    """
    
    def __init__(
        self,
        agent_role: str,
        project_context: Optional[Dict[str, Any]] = None,
        storage_dir: Optional[str] = None
    ):
        """
        Initialize agent briefing
        
        Args:
            agent_role: Agent role (e.g., "Architect", "Developer")
            project_context: Project-level context information
            storage_dir: Directory for persisting briefings
        """
        self.agent_role = agent_role
        self.project_context = project_context or {}
        self.storage_dir = Path(storage_dir or "data/briefings")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Briefing sections
        self.sections: Dict[str, BriefingSection] = {}
        
        # Agent context
        self.agent_context = AgentContext(role=agent_role)
        
        # Load existing briefing if available
        self._load_briefing()
    
    def generate_briefing(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        max_length: Optional[int] = None
    ) -> str:
        """
        Generate briefing for a specific task
        
        Args:
            task: Task description
            context: Additional context for this task
            max_length: Maximum briefing length (characters)
        
        Returns:
            Generated briefing content
        """
        context = context or {}
        
        # Build briefing sections
        briefing_parts = []
        
        # 1. Agent role and capabilities
        briefing_parts.append(self._generate_role_section())
        
        # 2. Project context
        briefing_parts.append(self._generate_project_section())
        
        # 3. Current task
        briefing_parts.append(self._generate_task_section(task, context))
        
        # 4. Historical context
        if self.agent_context.history:
            briefing_parts.append(self._generate_history_section())
        
        # 5. Custom sections (sorted by priority)
        sorted_sections = sorted(
            self.sections.values(),
            key=lambda s: (s.priority, -s.timestamp)
        )
        for section in sorted_sections:
            briefing_parts.append(f"## {section.title}\n\n{section.content}")
        
        # Combine all parts
        full_briefing = "\n\n".join(briefing_parts)
        
        # Truncate if needed
        if max_length and len(full_briefing) > max_length:
            full_briefing = full_briefing[:max_length] + "\n\n[Briefing truncated...]"
        
        # Save to history
        self._add_to_history(task, context, full_briefing)
        
        return full_briefing
    
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
        """
        Update briefing with new information
        
        Args:
            key: Information key
            value: Information value
            section: Section name (creates new section if not exists)
            priority: Section priority (1=high, 2=medium, 3=low)
        """
        if section:
            # Update or create section
            if section not in self.sections:
                self.sections[section] = BriefingSection(
                    title=section,
                    content="",
                    priority=priority
                )
            
            # Append to section content
            if isinstance(value, str):
                self.sections[section].content += f"\n- **{key}**: {value}"
            else:
                self.sections[section].content += f"\n- **{key}**: {json.dumps(value)}"
            
            self.sections[section].timestamp = datetime.now().timestamp()
        else:
            # Update agent context
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
        
        # Persist changes
        self._save_briefing()
    
    def add_section(
        self,
        title: str,
        content: str,
        priority: int = 2,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a new briefing section
        
        Args:
            title: Section title
            content: Section content
            priority: Section priority (1=high, 2=medium, 3=low)
            metadata: Additional metadata
        """
        self.sections[title] = BriefingSection(
            title=title,
            content=content,
            priority=priority,
            metadata=metadata or {}
        )
        
        self._save_briefing()
    
    def remove_section(self, title: str) -> bool:
        """
        Remove a briefing section
        
        Args:
            title: Section title
        
        Returns:
            True if section was removed, False if not found
        """
        if title in self.sections:
            del self.sections[title]
            self._save_briefing()
            return True
        return False
    
    def get_section(self, title: str) -> Optional[BriefingSection]:
        """Get a specific briefing section"""
        return self.sections.get(title)
    
    def list_sections(self) -> List[str]:
        """List all section titles"""
        return list(self.sections.keys())
    
    def clear_history(self) -> None:
        """Clear agent history"""
        self.agent_context.history.clear()
        self._save_briefing()
    
    def export_briefing(self, output_path: str) -> None:
        """
        Export briefing to file
        
        Args:
            output_path: Output file path
        """
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
        """Add task to history"""
        history_entry = {
            "task": task,
            "context": context,
            "briefing_length": len(briefing),
            "timestamp": datetime.now().timestamp()
        }
        
        self.agent_context.history.append(history_entry)
        
        # Keep only recent history (last 100 entries)
        if len(self.agent_context.history) > 100:
            self.agent_context.history = self.agent_context.history[-100:]
        
        self._save_briefing()
    
    def _save_briefing(self) -> None:
        """Save briefing to disk"""
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
        """Load briefing from disk"""
        try:
            safe_role = _SAFE_FILENAME_RE.sub('_', self.agent_role.lower())
            briefing_file = self.storage_dir / f"{safe_role}_briefing.json"
            
            if not briefing_file.exists():
                return
            
            briefing_data = json.loads(briefing_file.read_text(encoding='utf-8'))
            
            # Restore project context
            self.project_context = briefing_data.get("project_context", {})
            
            # Restore agent context
            agent_context_data = briefing_data.get("agent_context", {})
            self.agent_context = AgentContext(**agent_context_data)
            
            # Restore sections
            sections_data = briefing_data.get("sections", {})
            for title, section_data in sections_data.items():
                self.sections[title] = BriefingSection(**section_data)
            
            logger.info(f"Loaded briefing for {self.agent_role}")
        except Exception as e:
            logger.warning(f"Failed to load briefing: {e}")


# Global briefing instances
_briefing_instances: Dict[str, AgentBriefing] = {}


def get_agent_briefing(
    agent_role: str,
    project_context: Optional[Dict[str, Any]] = None,
    storage_dir: Optional[str] = None
) -> AgentBriefing:
    """
    Get or create agent briefing instance
    
    Args:
        agent_role: Agent role
        project_context: Project context
        storage_dir: Storage directory
    
    Returns:
        AgentBriefing instance
    """
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


__version__ = "1.0.0"
__all__ = [
    "AgentBriefing",
    "BriefingSection",
    "AgentContext",
    "get_agent_briefing",
    "reset_briefings",
]
