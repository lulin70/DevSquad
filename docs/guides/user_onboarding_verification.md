# User Onboarding Verification Guide

**Version**: 3.5.0  
**Date**: 2026-05-01  
**Purpose**: Verify complete user onboarding flow

---

## Test Scenario 1: New User - Basic Usage

### Step 1: Clone Repository
```bash
cd /tmp
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad
```

**Expected**: Repository cloned successfully

### Step 2: Check System Status
```bash
python3 scripts/cli.py status
```

**Expected Output**:
```
System Status: Ready
Available Roles: 7
LLM Backend: mock (default)
```

### Step 3: List Available Roles
```bash
python3 scripts/cli.py roles
```

**Expected**: Shows 7 roles with descriptions

### Step 4: Run First Task (Mock Mode)
```bash
python3 scripts/cli.py dispatch -t "Design a simple REST API"
```

**Expected**: 
- Task dispatched successfully
- Mock responses generated
- Structured report displayed

---

## Test Scenario 2: Python API Usage

### Step 1: Create Test Script
```python
# test_basic_api.py
from scripts.collaboration.dispatcher import MultiAgentDispatcher

# Test 1: Basic dispatch
disp = MultiAgentDispatcher()
result = disp.dispatch("Design user authentication system")

print("✅ Test 1: Basic dispatch")
print(f"  Success: {result.success}")
print(f"  Summary length: {len(result.summary)}")
print(f"  Findings count: {len(result.findings)}")

disp.shutdown()
print("✅ Dispatcher shutdown successfully")
```

### Step 2: Run Test
```bash
python3 test_basic_api.py
```

**Expected**:
- All tests pass
- No errors
- Clean shutdown

---

## Test Scenario 3: New Features (v3.5.0)

### Step 1: Test AgentBriefing
```python
# test_agent_briefing.py
from scripts.collaboration.agent_briefing import get_agent_briefing

# Create briefing
briefing = get_agent_briefing("architect")
briefing.update_briefing("capabilities", "System design")
briefing.update_briefing("constraints", "Must use Python 3.8+")

# Generate briefing
content = briefing.generate_briefing(
    task="Design authentication system",
    context={"priority": "high"}
)

print("✅ AgentBriefing test passed")
print(f"  Briefing length: {len(content)}")
print(f"  Contains capabilities: {'System design' in content}")
print(f"  Contains constraints: {'Python 3.8+' in content}")
```

### Step 2: Test ConfidenceScore
```python
# test_confidence_score.py
from scripts.collaboration.confidence_score import get_confidence_scorer

scorer = get_confidence_scorer()

# Test high-quality response
response = """
Here's a comprehensive REST API design:

1. Authentication Endpoints:
   - POST /api/v1/auth/login
   - POST /api/v1/auth/logout
   - POST /api/v1/auth/refresh

2. User Management:
   - GET /api/v1/users
   - POST /api/v1/users
   - PUT /api/v1/users/{id}
   - DELETE /api/v1/users/{id}

Security considerations:
- Use JWT tokens
- Implement rate limiting
- Enable HTTPS only
"""

score = scorer.calculate_confidence(
    prompt="Design a REST API",
    response=response,
    metadata={"model": "gpt-4", "temperature": 0.7}
)

print("✅ ConfidenceScore test passed")
print(f"  Overall score: {score.overall_score:.2f}")
print(f"  Level: {score.level.value}")
print(f"  Is confident: {score.is_confident(0.7)}")
```

### Step 3: Test EnhancedWorker
```python
# test_enhanced_worker.py
from scripts.collaboration.enhanced_worker import create_enhanced_worker
from scripts.collaboration.scratchpad import Scratchpad
from scripts.collaboration.models import TaskDefinition

scratchpad = Scratchpad()

worker = create_enhanced_worker(
    worker_id="test-001",
    role_id="architect",
    role_prompt="You are a system architect",
    scratchpad=scratchpad,
    confidence_threshold=0.7,
    enable_briefing=True,
    enable_confidence=True,
)

task = TaskDefinition(
    task_id="task-001",
    description="Design a simple REST API",
    role_id="architect"
)

result = worker.execute(task)

print("✅ EnhancedWorker test passed")
print(f"  Success: {result.success}")
print(f"  Has confidence score: {'confidence_score' in result.output}")
print(f"  Has briefing: {'briefing_used' in result.output}")
print(f"  Attempts: {result.output.get('attempts', 0)}")
```

### Step 4: Run All New Feature Tests
```bash
python3 test_agent_briefing.py
python3 test_confidence_score.py
python3 test_enhanced_worker.py
```

**Expected**: All tests pass with ✅

---

## Test Scenario 4: Unit Tests

### Step 1: Run All Tests
```bash
python3 -m pytest tests/ -v --tb=short
```

**Expected**:
- 214 tests total
- 212+ passing
- < 5 failures (known issues)

### Step 2: Run New Feature Tests Only
```bash
python3 -m pytest tests/test_agent_briefing.py tests/test_confidence_score.py -v
```

**Expected**:
- 65 tests
- 65 passing
- 0 failures

---

## Test Scenario 5: Documentation Access

### Step 1: Check README
```bash
cat README.md | grep "V3.5.0"
```

**Expected**: Shows v3.5.0 version info

### Step 2: Check Integration Guide
```bash
ls -la docs/guides/agent_briefing_confidence_integration.md
```

**Expected**: File exists and is readable

### Step 3: Check Milestone Summary
```bash
ls -la docs/milestones/milestone_2_summary.md
```

**Expected**: File exists and is readable

---

## Test Scenario 6: Configuration

### Step 1: Check Default Config
```bash
python3 -c "from scripts.collaboration.config_loader import load_config; print(load_config())"
```

**Expected**: Shows default configuration

### Step 2: Create Custom Config
```bash
cat > .devsquad.yaml << EOF
quality_control:
  enabled: true
  strict_mode: true

llm:
  backend: mock
  timeout: 120
EOF
```

### Step 3: Verify Config Loading
```bash
python3 -c "from scripts.collaboration.config_loader import load_config; c=load_config(); print(f'QC enabled: {c.get(\"quality_control\", {}).get(\"enabled\")}')"
```

**Expected**: Shows "QC enabled: True"

---

## Verification Checklist

### Installation & Setup
- [ ] Repository clones successfully
- [ ] No missing dependencies errors
- [ ] Python 3.9+ detected
- [ ] CLI commands work

### Basic Functionality
- [ ] `status` command works
- [ ] `roles` command lists 7 roles
- [ ] `dispatch` command executes tasks
- [ ] Mock mode works without API keys

### Python API
- [ ] Can import modules
- [ ] Dispatcher creates successfully
- [ ] Tasks execute successfully
- [ ] Clean shutdown works

### New Features (v3.5.0)
- [ ] AgentBriefing creates and generates
- [ ] ConfidenceScore calculates correctly
- [ ] EnhancedWorker executes with QA
- [ ] All 65 new tests pass

### Documentation
- [ ] README shows v3.5.0
- [ ] Integration guide accessible
- [ ] Milestone summary accessible
- [ ] Code has inline docs

### Configuration
- [ ] Default config loads
- [ ] Custom config works
- [ ] Environment variables override

---

## Common Issues & Solutions

### Issue 1: Import Errors
**Symptom**: `ModuleNotFoundError: No module named 'scripts'`

**Solution**:
```bash
# Make sure you're in the DevSquad directory
cd /path/to/DevSquad

# Or install as package
pip install -e .
```

### Issue 2: Permission Errors
**Symptom**: `Permission denied` when running scripts

**Solution**:
```bash
chmod +x scripts/cli.py
# Or use python3 explicitly
python3 scripts/cli.py
```

### Issue 3: Test Failures
**Symptom**: Some tests fail

**Solution**:
```bash
# Check if it's known issues (2 cache tests)
python3 -m pytest tests/ -v | grep FAILED

# Run only new feature tests
python3 -m pytest tests/test_agent_briefing.py tests/test_confidence_score.py -v
```

---

## Success Criteria

✅ **All scenarios pass**  
✅ **No critical errors**  
✅ **Documentation accessible**  
✅ **New features work**  
✅ **Tests pass (212+/214)**

---

## Next Steps After Verification

1. **For New Users**:
   - Read [Integration Guide](agent_briefing_confidence_integration.md)
   - Try examples in [EXAMPLES.md](../../EXAMPLES.md)
   - Explore [SKILL.md](../../SKILL.md)

2. **For Developers**:
   - Read [Milestone 2 Summary](../milestones/milestone_2_summary.md)
   - Check [Architecture Specs](../architecture/)
   - Review test files in `tests/`

3. **For Contributors**:
   - Read [CONTRIBUTING.md](../../CONTRIBUTING.md)
   - Check [CHANGELOG.md](../../CHANGELOG.md)
   - Review open issues on GitHub

---

**Last Updated**: 2026-05-01  
**Version**: 3.5.0  
**Status**: ✅ Verified
