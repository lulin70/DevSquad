#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentBriefing Unit Tests

Test the AgentBriefing system for context-aware briefing generation.
"""

import pytest
import tempfile
import shutil
import json
from pathlib import Path


@pytest.fixture
def temp_storage_dir():
    """Create temporary storage directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def agent_briefing(temp_storage_dir):
    """Create AgentBriefing instance"""
    from scripts.collaboration.agent_briefing import AgentBriefing, reset_briefings
    
    # Reset global instances
    reset_briefings()
    
    # Create new instance
    briefing = AgentBriefing(
        agent_role="Architect",
        project_context={"name": "DevSquad", "version": "3.4.0-Prod"},
        storage_dir=temp_storage_dir
    )
    yield briefing
    
    # Cleanup
    reset_briefings()


def test_import_agent_briefing():
    """Test AgentBriefing module import"""
    from scripts.collaboration.agent_briefing import (
        AgentBriefing,
        BriefingSection,
        AgentContext,
        get_agent_briefing,
        reset_briefings,
    )
    
    assert AgentBriefing is not None
    assert BriefingSection is not None
    assert AgentContext is not None
    assert get_agent_briefing is not None
    assert reset_briefings is not None


def test_agent_briefing_initialization(agent_briefing):
    """Test AgentBriefing initialization"""
    assert agent_briefing.agent_role == "Architect"
    assert agent_briefing.project_context["name"] == "DevSquad"
    assert agent_briefing.project_context["version"] == "3.4.0-Prod"
    assert len(agent_briefing.sections) == 0
    assert agent_briefing.agent_context.role == "Architect"


def test_generate_briefing_basic(agent_briefing):
    """Test basic briefing generation"""
    briefing = agent_briefing.generate_briefing(
        task="Design Protocol interface system",
        context={"priority": "high"}
    )
    
    # Verify briefing content
    assert "Architect" in briefing
    assert "Design Protocol interface system" in briefing
    assert "DevSquad" in briefing
    assert isinstance(briefing, str)
    assert len(briefing) > 0


def test_generate_briefing_with_capabilities(agent_briefing):
    """Test briefing generation with agent capabilities"""
    # Add capabilities
    agent_briefing.update_briefing("capabilities", "System design")
    agent_briefing.update_briefing("capabilities", "API design")
    
    briefing = agent_briefing.generate_briefing(
        task="Design REST API",
        context={}
    )
    
    # Verify capabilities are included
    assert "System design" in briefing
    assert "API design" in briefing


def test_generate_briefing_with_constraints(agent_briefing):
    """Test briefing generation with constraints"""
    # Add constraints
    agent_briefing.update_briefing("constraints", "Must use Python 3.8+")
    agent_briefing.update_briefing("constraints", "Follow PEP 8")
    
    briefing = agent_briefing.generate_briefing(
        task="Write code",
        context={}
    )
    
    # Verify constraints are included
    assert "Must use Python 3.8+" in briefing
    assert "Follow PEP 8" in briefing


def test_generate_briefing_with_history(agent_briefing):
    """Test briefing generation with history"""
    # Generate multiple briefings to build history
    agent_briefing.generate_briefing("Task 1", {})
    agent_briefing.generate_briefing("Task 2", {})
    agent_briefing.generate_briefing("Task 3", {})
    
    # Generate new briefing
    briefing = agent_briefing.generate_briefing("Task 4", {})
    
    # Verify history is included
    assert "Recent History" in briefing
    assert "Task 3" in briefing or "Task 2" in briefing


def test_generate_briefing_max_length(agent_briefing):
    """Test briefing generation with max length"""
    # Add lots of content
    for i in range(10):
        agent_briefing.add_section(
            title=f"Section {i}",
            content="A" * 1000,
            priority=2
        )
    
    # Generate briefing with max length
    briefing = agent_briefing.generate_briefing(
        task="Test task",
        context={},
        max_length=500
    )
    
    # Verify length is limited
    assert len(briefing) <= 550  # Allow some margin for truncation message
    assert "[Briefing truncated...]" in briefing


def test_update_briefing_with_section(agent_briefing):
    """Test updating briefing with custom section"""
    agent_briefing.update_briefing(
        key="decision",
        value="Use Python Protocol",
        section="Technical Decisions",
        priority=1
    )
    
    # Verify section was created
    assert "Technical Decisions" in agent_briefing.sections
    assert "Use Python Protocol" in agent_briefing.sections["Technical Decisions"].content


def test_update_briefing_capabilities(agent_briefing):
    """Test updating agent capabilities"""
    agent_briefing.update_briefing("capabilities", "Database design")
    
    assert "Database design" in agent_briefing.agent_context.capabilities


def test_update_briefing_constraints(agent_briefing):
    """Test updating agent constraints"""
    agent_briefing.update_briefing("constraints", "No external dependencies")
    
    assert "No external dependencies" in agent_briefing.agent_context.constraints


def test_update_briefing_preferences(agent_briefing):
    """Test updating agent preferences"""
    agent_briefing.update_briefing("preferences", {"coding_style": "functional"})
    
    assert agent_briefing.agent_context.preferences["coding_style"] == "functional"


def test_add_section(agent_briefing):
    """Test adding a briefing section"""
    agent_briefing.add_section(
        title="Best Practices",
        content="Always use type hints",
        priority=1,
        metadata={"category": "coding"}
    )
    
    # Verify section was added
    assert "Best Practices" in agent_briefing.sections
    section = agent_briefing.sections["Best Practices"]
    assert section.content == "Always use type hints"
    assert section.priority == 1
    assert section.metadata["category"] == "coding"


def test_remove_section(agent_briefing):
    """Test removing a briefing section"""
    # Add section
    agent_briefing.add_section("Test Section", "Test content")
    assert "Test Section" in agent_briefing.sections
    
    # Remove section
    result = agent_briefing.remove_section("Test Section")
    assert result == True
    assert "Test Section" not in agent_briefing.sections
    
    # Try to remove non-existent section
    result = agent_briefing.remove_section("Non-existent")
    assert result == False


def test_get_section(agent_briefing):
    """Test getting a specific section"""
    agent_briefing.add_section("Test Section", "Test content", priority=2)
    
    section = agent_briefing.get_section("Test Section")
    assert section is not None
    assert section.title == "Test Section"
    assert section.content == "Test content"
    assert section.priority == 2
    
    # Get non-existent section
    section = agent_briefing.get_section("Non-existent")
    assert section is None


def test_list_sections(agent_briefing):
    """Test listing all sections"""
    agent_briefing.add_section("Section 1", "Content 1")
    agent_briefing.add_section("Section 2", "Content 2")
    agent_briefing.add_section("Section 3", "Content 3")
    
    sections = agent_briefing.list_sections()
    assert len(sections) == 3
    assert "Section 1" in sections
    assert "Section 2" in sections
    assert "Section 3" in sections


def test_clear_history(agent_briefing):
    """Test clearing agent history"""
    # Generate some briefings to build history
    agent_briefing.generate_briefing("Task 1", {})
    agent_briefing.generate_briefing("Task 2", {})
    
    assert len(agent_briefing.agent_context.history) == 2
    
    # Clear history
    agent_briefing.clear_history()
    assert len(agent_briefing.agent_context.history) == 0


def test_export_briefing(agent_briefing, temp_storage_dir):
    """Test exporting briefing to file"""
    # Add some content
    agent_briefing.add_section("Test Section", "Test content")
    agent_briefing.generate_briefing("Test task", {})
    
    # Export briefing
    output_path = Path(temp_storage_dir) / "exported_briefing.json"
    agent_briefing.export_briefing(str(output_path))
    
    # Verify file exists
    assert output_path.exists()
    
    # Verify content
    data = json.loads(output_path.read_text())
    assert data["agent_role"] == "Architect"
    assert "Test Section" in data["sections"]
    assert "exported_at" in data


def test_persistence_save_and_load(temp_storage_dir):
    """Test briefing persistence (save and load)"""
    from scripts.collaboration.agent_briefing import AgentBriefing
    
    # Create briefing and add content
    briefing1 = AgentBriefing(
        agent_role="Developer",
        project_context={"name": "Test"}, storage_dir=temp_storage_dir
    )
    briefing1.add_section("Section 1", "Content 1")
    briefing1.update_briefing("capabilities", "Coding")
    
    # Create new instance (should load from disk)
    briefing2 = AgentBriefing(
        agent_role="Developer",
        storage_dir=temp_storage_dir
    )
    
    # Verify content was loaded
    assert "Section 1" in briefing2.sections
    assert "Coding" in briefing2.agent_context.capabilities


def test_section_priority_ordering(agent_briefing):
    """Test sections are ordered by priority"""
    # Add sections with different priorities
    agent_briefing.add_section("Low Priority", "Content", priority=3)
    agent_briefing.add_section("High Priority", "Content", priority=1)
    agent_briefing.add_section("Medium Priority", "Content", priority=2)
    
    # Generate briefing
    briefing = agent_briefing.generate_briefing("Test", {})
    
    # Verify high priority appears before low priority
    high_pos = briefing.find("High Priority")
    medium_pos = briefing.find("Medium Priority")
    low_pos = briefing.find("Low Priority")
    
    assert high_pos < medium_pos < low_pos


def test_history_limit(agent_briefing):
    """Test history is limited to 100 entries"""
    # Generate 150 briefings
    for i in range(150):
        agent_briefing.generate_briefing(f"Task {i}", {})
    
    # Verify history is limited to 100
    assert len(agent_briefing.agent_context.history) == 100
    
    # Verify oldest entries were removed
    tasks = [entry["task"] for entry in agent_briefing.agent_context.history]
    assert "Task 0" not in tasks
    assert "Task 149" in tasks


def test_briefing_section_dataclass(agent_briefing):
    """Test BriefingSection dataclass"""
    from scripts.collaboration.agent_briefing import BriefingSection
    
    section = BriefingSection(
        title="Test",
        content="Content",
        priority=1,
        metadata={"key": "value"}
    )
    
    # Test to_dict
    data = section.to_dict()
    assert data["title"] == "Test"
    assert data["content"] == "Content"
    assert data["priority"] == 1
    assert data["metadata"]["key"] == "value"
    assert "timestamp" in data


def test_agent_context_dataclass(agent_briefing):
    """Test AgentContext dataclass"""
    from scripts.collaboration.agent_briefing import AgentContext
    
    context = AgentContext(
        role="Tester",
        capabilities=["Unit testing", "Integration testing"],
        constraints=["No manual testing"],
        preferences={"framework": "pytest"}
    )
    
    # Test to_dict
    data = context.to_dict()
    assert data["role"] == "Tester"
    assert "Unit testing" in data["capabilities"]
    assert "No manual testing" in data["constraints"]
    assert data["preferences"]["framework"] == "pytest"


def test_get_agent_briefing_factory():
    """Test get_agent_briefing factory function"""
    from scripts.collaboration.agent_briefing import get_agent_briefing, reset_briefings
    
    # Reset first
    reset_briefings()
    
    # Get briefing (should create new instance)
    briefing1 = get_agent_briefing("Architect")
    assert briefing1.agent_role == "Architect"
    
    # Get same briefing again (should return same instance)
    briefing2 = get_agent_briefing("Architect")
    assert briefing1 is briefing2
    
    # Get different briefing (should create new instance)
    briefing3 = get_agent_briefing("Developer")
    assert briefing3.agent_role == "Developer"
    assert briefing1 is not briefing3
    
    # Cleanup
    reset_briefings()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
