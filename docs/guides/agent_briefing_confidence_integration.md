# AgentBriefing + ConfidenceScore Integration Guide

## Overview

This guide demonstrates how to integrate **AgentBriefing** and **ConfidenceScore** systems into your DevSquad agents for context-aware, quality-assured AI collaboration.

## Table of Contents

1. [Quick Start](#quick-start)
2. [AgentBriefing Usage](#agentbriefing-usage)
3. [ConfidenceScore Usage](#confidencescore-usage)
4. [Integration Patterns](#integration-patterns)
5. [Best Practices](#best-practices)
6. [Advanced Examples](#advanced-examples)

---

## Quick Start

### Installation

```python
# Import the modules
from scripts.collaboration.agent_briefing import get_agent_briefing
from scripts.collaboration.confidence_score import get_confidence_scorer
```

### Basic Usage

```python
# 1. Create agent briefing
briefing = get_agent_briefing("Architect")

# 2. Generate briefing for task
briefing_content = briefing.generate_briefing(
    task="Design authentication system",
    context={"priority": "high"}
)

# 3. Get LLM response (with briefing as context)
response = llm.generate(prompt=f"{briefing_content}\n\n{user_request}")

# 4. Calculate confidence
scorer = get_confidence_scorer()
score = scorer.calculate_confidence(
    prompt=briefing_content,
    response=response,
    metadata={"model": "gpt-4", "temperature": 0.7}
)

# 5. Decision making
if score.is_confident(threshold=0.7):
    print(f"✅ High confidence ({score.overall_score:.2f}) - Proceed")
    proceed_with_implementation(response)
else:
    print(f"⚠️ Low confidence ({score.overall_score:.2f}) - Request review")
    request_human_review(response, score)
```

---

## AgentBriefing Usage

### 1. Creating Agent Briefings

```python
from scripts.collaboration.agent_briefing import AgentBriefing

# Create briefing for specific agent role
briefing = AgentBriefing(
    agent_role="Architect",
    project_context={
        "name": "DevSquad",
        "version": "3.5",
        "tech_stack": ["Python", "FastAPI", "PostgreSQL"],
        "architecture": "Microservices"
    }
)
```

### 2. Adding Capabilities

```python
# Add agent capabilities
briefing.update_briefing("capabilities", "System design")
briefing.update_briefing("capabilities", "API design")
briefing.update_briefing("capabilities", "Database schema design")
briefing.update_briefing("capabilities", "Performance optimization")
```

### 3. Adding Constraints

```python
# Add project constraints
briefing.update_briefing("constraints", "Must use Python 3.8+")
briefing.update_briefing("constraints", "Follow SOLID principles")
briefing.update_briefing("constraints", "Maximum response time: 200ms")
briefing.update_briefing("constraints", "Use Protocol for interfaces")
```

### 4. Adding Custom Sections

```python
# Add high-priority technical decisions
briefing.add_section(
    title="Technical Decisions",
    content="""
    - Use Python Protocol for interface definition
    - Implement dependency injection pattern
    - Use Redis for caching layer
    - PostgreSQL for persistent storage
    """,
    priority=1  # High priority
)

# Add medium-priority coding standards
briefing.add_section(
    title="Coding Standards",
    content="""
    - Follow PEP 8 style guide
    - Use type hints for all functions
    - Write docstrings for public APIs
    - Maintain test coverage > 80%
    """,
    priority=2  # Medium priority
)
```

### 5. Generating Briefings

```python
# Generate briefing for specific task
content = briefing.generate_briefing(
    task="Design Protocol interface system",
    context={
        "priority": "high",
        "deadline": "Week 4",
        "dependencies": ["Python 3.8+", "typing module"]
    }
)

print(content)
```

**Output:**
```markdown
# Agent Briefing: Architect

**Role**: Architect

**Capabilities**:
- System design
- API design
- Database schema design
- Performance optimization

**Constraints**:
- Must use Python 3.8+
- Follow SOLID principles
- Maximum response time: 200ms
- Use Protocol for interfaces

## Project Context

**Name**: DevSquad
**Version**: 3.5
**Tech Stack**: ["Python", "FastAPI", "PostgreSQL"]
**Architecture**: Microservices

## Current Task

Design Protocol interface system

**Task Context**:
- **Priority**: high
- **Deadline**: Week 4
- **Dependencies**: ["Python 3.8+", "typing module"]

## Technical Decisions

- Use Python Protocol for interface definition
- Implement dependency injection pattern
- Use Redis for caching layer
- PostgreSQL for persistent storage

## Coding Standards

- Follow PEP 8 style guide
- Use type hints for all functions
- Write docstrings for public APIs
- Maintain test coverage > 80%
```

### 6. Managing Sections

```python
# List all sections
sections = briefing.list_sections()
for section in sections:
    print(f"- {section.title} (Priority: {section.priority})")

# Get specific section
tech_decisions = briefing.get_section("Technical Decisions")
if tech_decisions:
    print(tech_decisions.content)

# Remove section
briefing.remove_section("Coding Standards")
```

### 7. Persistence

```python
# Save briefing to file
briefing.save("/path/to/briefings/architect_briefing.json")

# Load briefing from file
loaded_briefing = AgentBriefing.load("/path/to/briefings/architect_briefing.json")
```

---

## ConfidenceScore Usage

### 1. Basic Confidence Calculation

```python
from scripts.collaboration.confidence_score import ConfidenceScorer

# Create scorer
scorer = ConfidenceScorer()

# Calculate confidence
score = scorer.calculate_confidence(
    prompt="Design a REST API for user management",
    response="""
    Here's a comprehensive REST API design:
    
    1. User endpoints:
       - GET /api/v1/users - List users (pagination: limit=20)
       - POST /api/v1/users - Create user
       - GET /api/v1/users/{id} - Get user details
       - PUT /api/v1/users/{id} - Update user
       - DELETE /api/v1/users/{id} - Delete user
    
    2. Authentication:
       - Use JWT tokens with 15-minute expiry
       - Implement refresh tokens (7-day expiry)
       - Add rate limiting: 100 requests/minute
    
    Example implementation:
    ```python
    @app.route('/api/v1/users', methods=['GET'])
    @require_auth
    def list_users():
        page = request.args.get('page', 1)
        limit = request.args.get('limit', 20)
        users = User.query.paginate(page, limit)
        return jsonify(users)
    ```
    
    This design follows REST best practices.
    """,
    metadata={
        "model": "gpt-4",
        "temperature": 0.3,
        "token_count": 1200
    }
)

# Access score details
print(f"Overall Score: {score.overall_score:.2f}")
print(f"Confidence Level: {score.level.value}")
print(f"\nFactors:")
for factor, value in score.factors.items():
    print(f"  - {factor}: {value:.2f}")
print(f"\nReasoning:")
for reason in score.reasoning:
    print(f"  - {reason}")
```

**Output:**
```
Overall Score: 0.89
Confidence Level: high

Factors:
  - completeness: 0.90
  - certainty: 1.00
  - specificity: 1.00
  - consistency: 1.00
  - model_quality: 0.95

Reasoning:
  - Response length good
  - No uncertainty indicators found
  - High specificity (numbers, code, examples, lists)
  - No consistency issues detected
  - High-quality model (GPT-4/Claude-3)
  - Low temperature (0.3) increases confidence
  - Detailed response (high token count)
```

### 2. Confidence Levels

```python
from scripts.collaboration.confidence_score import ConfidenceLevel

# Check confidence level
if score.level == ConfidenceLevel.VERY_HIGH:
    print("Excellent quality - proceed with confidence")
elif score.level == ConfidenceLevel.HIGH:
    print("Good quality - proceed")
elif score.level == ConfidenceLevel.MEDIUM:
    print("Acceptable quality - review recommended")
elif score.level == ConfidenceLevel.LOW:
    print("Low quality - review required")
else:  # VERY_LOW
    print("Very low quality - regenerate response")
```

### 3. Threshold-Based Decisions

```python
# Simple threshold check
if score.is_confident(threshold=0.7):
    approve_response(response)
else:
    request_review(response)

# Multi-tier decision making
if score.overall_score >= 0.9:
    auto_approve(response)
elif score.overall_score >= 0.7:
    quick_review(response)
elif score.overall_score >= 0.5:
    detailed_review(response)
else:
    regenerate_response()
```

### 4. Confidence Trends

```python
# Generate multiple responses
for i in range(10):
    response = llm.generate(prompt=f"Task {i}")
    scorer.calculate_confidence(prompt, response, {})

# Analyze trend
trend = scorer.get_confidence_trend()
print(f"Confidence Trend: {trend}")

if trend == "improving":
    print("✅ Agent is learning and improving")
elif trend == "declining":
    print("⚠️ Agent quality is declining - investigate")
else:
    print("➡️ Agent quality is stable")
```

### 5. Statistics Export

```python
# Export comprehensive statistics
stats = scorer.export_stats()

print(f"Total Scores: {stats['total_scores']}")
print(f"Average Confidence: {stats['average_confidence']:.2f}")
print(f"Recent Average (last 10): {stats['recent_average']:.2f}")
print(f"Trend: {stats['trend']}")

print("\nLevel Distribution:")
for level, count in stats['level_distribution'].items():
    print(f"  - {level}: {count}")

print("\nFactor Averages:")
for factor, avg in stats['factor_averages'].items():
    print(f"  - {factor}: {avg:.2f}")
```

### 6. Custom Weights

```python
# Create scorer with custom weights
custom_scorer = ConfidenceScorer(
    weights={
        "completeness": 0.30,  # Emphasize completeness
        "certainty": 0.30,     # Emphasize certainty
        "specificity": 0.20,
        "consistency": 0.10,
        "model_quality": 0.10
    },
    min_response_length=100  # Require longer responses
)

score = custom_scorer.calculate_confidence(prompt, response, metadata)
```

---

## Integration Patterns

### Pattern 1: Basic Agent Workflow

```python
def agent_workflow(agent_role: str, task: str, user_request: str):
    """Basic agent workflow with briefing and confidence"""
    
    # 1. Get agent briefing
    briefing = get_agent_briefing(agent_role)
    briefing_content = briefing.generate_briefing(
        task=task,
        context={"user_request": user_request}
    )
    
    # 2. Generate response
    full_prompt = f"{briefing_content}\n\n---\n\n{user_request}"
    response = llm.generate(prompt=full_prompt)
    
    # 3. Calculate confidence
    scorer = get_confidence_scorer()
    score = scorer.calculate_confidence(
        prompt=full_prompt,
        response=response,
        metadata={"model": "gpt-4", "temperature": 0.7}
    )
    
    # 4. Decision making
    if score.is_confident(threshold=0.7):
        return {
            "status": "approved",
            "response": response,
            "confidence": score.overall_score
        }
    else:
        return {
            "status": "review_required",
            "response": response,
            "confidence": score.overall_score,
            "reasoning": score.reasoning
        }
```

### Pattern 2: Multi-Agent Collaboration

```python
def multi_agent_collaboration(task: str):
    """Multi-agent workflow with briefings and confidence tracking"""
    
    agents = ["Architect", "Developer", "Reviewer"]
    results = []
    
    for agent_role in agents:
        # Get agent briefing
        briefing = get_agent_briefing(agent_role)
        
        # Add previous results to context
        context = {
            "task": task,
            "previous_results": results
        }
        
        briefing_content = briefing.generate_briefing(
            task=f"{agent_role} phase",
            context=context
        )
        
        # Generate response
        response = llm.generate(prompt=briefing_content)
        
        # Calculate confidence
        scorer = get_confidence_scorer()
        score = scorer.calculate_confidence(
            prompt=briefing_content,
            response=response,
            metadata={"model": "gpt-4", "agent": agent_role}
        )
        
        # Store result
        results.append({
            "agent": agent_role,
            "response": response,
            "confidence": score.overall_score,
            "level": score.level.value
        })
        
        # Update briefing with outcome
        briefing.update_briefing(
            key="last_task",
            value=f"Completed with confidence {score.overall_score:.2f}",
            section="History"
        )
        
        # Stop if confidence too low
        if not score.is_confident(threshold=0.6):
            print(f"⚠️ {agent_role} confidence too low - stopping workflow")
            break
    
    return results
```

### Pattern 3: Iterative Refinement

```python
def iterative_refinement(task: str, max_iterations: int = 3):
    """Iteratively refine response until confidence threshold met"""
    
    briefing = get_agent_briefing("Developer")
    scorer = get_confidence_scorer()
    
    for iteration in range(max_iterations):
        # Generate briefing
        context = {
            "iteration": iteration + 1,
            "max_iterations": max_iterations
        }
        briefing_content = briefing.generate_briefing(task=task, context=context)
        
        # Generate response
        response = llm.generate(prompt=briefing_content)
        
        # Calculate confidence
        score = scorer.calculate_confidence(
            prompt=briefing_content,
            response=response,
            metadata={"model": "gpt-4", "iteration": iteration}
        )
        
        print(f"Iteration {iteration + 1}: Confidence = {score.overall_score:.2f}")
        
        # Check if confidence threshold met
        if score.is_confident(threshold=0.8):
            print(f"✅ High confidence achieved in {iteration + 1} iterations")
            return {
                "status": "success",
                "response": response,
                "iterations": iteration + 1,
                "confidence": score.overall_score
            }
        
        # Add feedback for next iteration
        briefing.add_section(
            title=f"Iteration {iteration + 1} Feedback",
            content=f"Previous confidence: {score.overall_score:.2f}\n" +
                   f"Issues: {', '.join(score.reasoning)}",
            priority=1
        )
    
    print(f"⚠️ Max iterations reached - confidence: {score.overall_score:.2f}")
    return {
        "status": "max_iterations",
        "response": response,
        "iterations": max_iterations,
        "confidence": score.overall_score
    }
```

### Pattern 4: Quality Gate

```python
def quality_gate_workflow(task: str):
    """Implement quality gates based on confidence scores"""
    
    briefing = get_agent_briefing("Developer")
    scorer = get_confidence_scorer()
    
    # Generate response
    briefing_content = briefing.generate_briefing(task=task)
    response = llm.generate(prompt=briefing_content)
    
    # Calculate confidence
    score = scorer.calculate_confidence(
        prompt=briefing_content,
        response=response,
        metadata={"model": "gpt-4"}
    )
    
    # Quality gates
    if score.overall_score >= 0.9:
        # Gate 1: Auto-approve
        return auto_approve(response)
    
    elif score.overall_score >= 0.7:
        # Gate 2: Peer review
        return peer_review(response, score)
    
    elif score.overall_score >= 0.5:
        # Gate 3: Senior review
        return senior_review(response, score)
    
    else:
        # Gate 4: Reject and regenerate
        return regenerate_with_feedback(task, score)
```

---

## Best Practices

### 1. Briefing Management

```python
# ✅ DO: Keep briefings focused and relevant
briefing.add_section(
    title="Current Sprint Goals",
    content="Focus on authentication and authorization",
    priority=1
)

# ❌ DON'T: Add too much irrelevant information
# briefing.add_section(
#     title="Company History",
#     content="Founded in 2020...",  # Not relevant to task
#     priority=1
# )

# ✅ DO: Update briefings regularly
briefing.update_briefing("constraints", "New security requirement: MFA")

# ✅ DO: Use priority levels effectively
briefing.add_section("Critical Bug", "Fix auth bypass", priority=1)  # High
briefing.add_section("Nice to Have", "Add dark mode", priority=3)   # Low
```

### 2. Confidence Thresholds

```python
# ✅ DO: Use appropriate thresholds for different tasks
THRESHOLDS = {
    "critical": 0.9,      # Security, data integrity
    "important": 0.7,     # Core features
    "standard": 0.5,      # Regular tasks
    "experimental": 0.3   # Prototypes, POCs
}

task_type = "critical"
threshold = THRESHOLDS[task_type]

if score.is_confident(threshold=threshold):
    proceed()
else:
    review()
```

### 3. Error Handling

```python
# ✅ DO: Handle low confidence gracefully
try:
    score = scorer.calculate_confidence(prompt, response, metadata)
    
    if not score.is_confident(threshold=0.7):
        # Log low confidence
        logger.warning(
            f"Low confidence: {score.overall_score:.2f}",
            extra={"reasoning": score.reasoning}
        )
        
        # Request human review
        request_review(response, score)
        
except Exception as e:
    logger.error(f"Confidence calculation failed: {e}")
    # Fallback to human review
    request_review(response, None)
```

### 4. Monitoring and Logging

```python
# ✅ DO: Track confidence metrics over time
def log_confidence_metrics(agent_role: str, score: ConfidenceScore):
    """Log confidence metrics for monitoring"""
    
    metrics = {
        "timestamp": score.timestamp,
        "agent": agent_role,
        "overall_score": score.overall_score,
        "level": score.level.value,
        "factors": score.factors,
        "metadata": score.metadata
    }
    
    # Log to monitoring system
    logger.info("confidence_score", extra=metrics)
    
    # Alert if confidence declining
    scorer = get_confidence_scorer()
    trend = scorer.get_confidence_trend()
    if trend == "declining":
        alert_team(f"Agent {agent_role} confidence declining")
```

---

## Advanced Examples

### Example 1: Context-Aware Agent

```python
class ContextAwareAgent:
    """Agent with briefing and confidence tracking"""
    
    def __init__(self, role: str):
        self.role = role
        self.briefing = get_agent_briefing(role)
        self.scorer = get_confidence_scorer()
    
    def execute_task(self, task: str, context: dict) -> dict:
        """Execute task with confidence tracking"""
        
        # Generate briefing
        briefing_content = self.briefing.generate_briefing(
            task=task,
            context=context
        )
        
        # Generate response
        response = self._generate_response(briefing_content)
        
        # Calculate confidence
        score = self.scorer.calculate_confidence(
            prompt=briefing_content,
            response=response,
            metadata={"model": "gpt-4", "agent": self.role}
        )
        
        # Update briefing with result
        self._update_history(task, score)
        
        return {
            "response": response,
            "confidence": score.overall_score,
            "level": score.level.value,
            "factors": score.factors,
            "reasoning": score.reasoning
        }
    
    def _generate_response(self, prompt: str) -> str:
        """Generate LLM response"""
        # Implementation depends on LLM provider
        return llm.generate(prompt=prompt)
    
    def _update_history(self, task: str, score: ConfidenceScore):
        """Update briefing history"""
        self.briefing.update_briefing(
            key=f"task_{int(score.timestamp)}",
            value={
                "task": task,
                "confidence": score.overall_score,
                "level": score.level.value,
                "timestamp": score.timestamp
            },
            section="History"
        )
```

### Example 2: Confidence-Based Routing

```python
def confidence_based_routing(task: str, response: str, score: ConfidenceScore):
    """Route tasks based on confidence levels"""
    
    if score.level == ConfidenceLevel.VERY_HIGH:
        # Auto-approve and deploy
        return auto_deploy(response)
    
    elif score.level == ConfidenceLevel.HIGH:
        # Quick peer review
        return peer_review_queue.add(response, priority="low")
    
    elif score.level == ConfidenceLevel.MEDIUM:
        # Standard review process
        return review_queue.add(response, priority="medium")
    
    elif score.level == ConfidenceLevel.LOW:
        # Senior review required
        return senior_review_queue.add(response, priority="high")
    
    else:  # VERY_LOW
        # Regenerate with different approach
        return regenerate_task(task, feedback=score.reasoning)
```

### Example 3: Adaptive Temperature

```python
def adaptive_temperature_generation(task: str, max_attempts: int = 3):
    """Adjust temperature based on confidence scores"""
    
    briefing = get_agent_briefing("Developer")
    scorer = get_confidence_scorer()
    
    temperatures = [0.3, 0.5, 0.7]  # Start conservative, increase if needed
    
    for attempt, temperature in enumerate(temperatures):
        # Generate response
        briefing_content = briefing.generate_briefing(task=task)
        response = llm.generate(
            prompt=briefing_content,
            temperature=temperature
        )
        
        # Calculate confidence
        score = scorer.calculate_confidence(
            prompt=briefing_content,
            response=response,
            metadata={"model": "gpt-4", "temperature": temperature}
        )
        
        print(f"Attempt {attempt + 1} (temp={temperature}): " +
              f"Confidence = {score.overall_score:.2f}")
        
        # Check if acceptable
        if score.is_confident(threshold=0.7):
            return {
                "status": "success",
                "response": response,
                "temperature": temperature,
                "confidence": score.overall_score
            }
    
    # All attempts failed
    return {
        "status": "failed",
        "response": response,
        "confidence": score.overall_score,
        "message": "Could not achieve acceptable confidence"
    }
```

---

## Summary

The **AgentBriefing** and **ConfidenceScore** systems provide:

1. **Context Awareness**: Agents understand project context and history
2. **Quality Assurance**: Automatic response quality assessment
3. **Risk Management**: Low-confidence responses flagged for review
4. **Transparency**: Detailed reasoning for confidence scores
5. **Continuous Improvement**: Track trends and optimize over time

Use these systems together to build robust, reliable AI agent workflows with built-in quality gates and context management.

---

## Next Steps

1. **Integration**: Integrate into existing agent workflows
2. **Customization**: Adjust weights and thresholds for your use case
3. **Monitoring**: Set up dashboards to track confidence metrics
4. **Optimization**: Analyze trends and improve agent performance

For more information, see:
- [AgentBriefing API Documentation](../api/agent_briefing.md)
- [ConfidenceScore API Documentation](../api/confidence_score.md)
- [Protocol Interface System](../architecture/protocol_interfaces_spec.md)
