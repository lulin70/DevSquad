# DevSquad Quick Start Guide

> **Version**: V3.6.0 | **5-Minute Getting Started**
>
> Get DevSquad up and running in 5 minutes. For complete documentation, see [REFERENCE_GUIDE_EN.md](REFERENCE_GUIDE_EN.md).

---

## What is DevSquad?

DevSquad transforms a **single AI task into a multi-role AI collaboration**. It automatically dispatches your task to the right combination of expert roles — architect, product manager, coder, tester, security reviewer, DevOps — orchestrates their parallel collaboration through a shared workspace, resolves conflicts via weighted consensus voting, and delivers a unified structured report.

**One task → Multi-role AI collaboration → One conclusion**

---

## Installation

### Prerequisites

- **Python 3.10+** (3.10, 3.11 supported)
- **pip** or **pipenv** for package management

### Option A: Quick Start (No Installation)

```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# Run directly (no dependencies needed)
python3 scripts/cli.py dispatch -t "Design user authentication system"
```

### Option B: Full Installation (Recommended)

```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# Install with all features
pip install -e .

# Use the CLI command
devsquad dispatch -t "Design user authentication system"
```

### Verify Installation

```bash
devsquad --version
# Expected: devsquad 3.6.0
```

---

## First Dispatch (3 Lines of Code)

### Python API

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("Design user authentication system")
print(result.to_markdown())
disp.shutdown()
```

### CLI Command

```bash
# Mock mode (no API Key needed)
python3 scripts/cli.py dispatch -t "Design user authentication system"

# Specify roles
python3 scripts/cli.py dispatch -t "Optimize database performance" -r arch coder

# Use LLM backend
python3 scripts/cli.py dispatch -t "Design REST API" --backend openai --stream
```

---

## CLI Quick Reference

| Command | Description | Example |
|---------|-------------|---------|
| `dispatch` | Execute multi-agent task | `dispatch -t "Task" -r arch coder` |
| `spec` | Define requirements | `spec -t "User auth system"` |
| `plan` | Break down tasks | `plan -t "Implement OAuth2"` |
| `build` | Implement with TDD | `build -t "Add password reset"` |
| `test` | Run tests | `test -t "Run all unit tests"` |
| `review` | Code review | `review -t "Review PR #123"` |
| `ship` | Deploy to production | `ship -t "Deploy v2.0"` |
| `status` | System status | `status` |
| `roles` | List available roles | `roles` |

**Role Short IDs**: `arch` (Architect), `pm` (Product Manager), `sec` (Security), `test` (Tester), `coder` (Coder), `infra` (DevOps), `ui` (UI Designer)

---

## Quick Demo

Run the interactive demo to see DevSquad in action:

```bash
python examples/quick_demo.py
```

This demonstrates:
- ✅ Bug fix scenario (Chinese intent detection)
- ✅ Code review (consensus mode + five-axis review)
- ✅ New feature design (multi-role collaboration)

---

## Configuration (Optional)

Create `.devsquad.yaml` in your project root:

```yaml
quality_control:
  enabled: true
  strict_mode: true
  min_quality_score: 85

llm:
  backend: mock  # mock, openai, or anthropic
  timeout: 120
```

Or use environment variables:

```bash
export OPENAI_API_KEY="sk-..."
export DEVSQUAD_LLM_BACKEND=openai
```

---

## Sub-Skills (V3.6.0)

DevSquad also provides **6 atomic sub-skills** (`skills/` package) that can be used independently:
`dispatch`, `intent`, `review`, `security`, `test`, `retrospective`. Each is a ~50-line wrapper around core modules, working in Mock mode without API keys.

```python
from skills import get_skill, list_skills
from skills.security.handler import SecuritySkill
risk = SecuritySkill().scan_input("suspicious input")
```

See [SKILL.md](../SKILL.md) § "Layered Sub-Skill Architecture" for details.

---

## Next Steps

📚 **Complete Documentation**
- [REFERENCE_GUIDE_EN.md](REFERENCE_GUIDE_EN.md) - Full user guide (all features, advanced usage)

🚀 **Examples**
- [examples/quick_demo.py](../examples/quick_demo.py) - Interactive demo (3 scenarios)
- [examples/quick_start.py](../examples/quick_start.py) - Lifecycle examples
- [examples/full_project_workflow.py](../examples/full_project_workflow.py) - Complete project workflow

🌐 **Web Dashboard**
```bash
streamlit run scripts/dashboard.py
# Open http://localhost:8501
```

🔌 **REST API Server**
```bash
pip install fastapi uvicorn
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload
# Access Swagger UI: http://localhost:8000/docs
```

☸️ **Kubernetes Deployment**
```bash
helm install devsquad ./helm/devsquad
kubectl port-forward svc/devsquad-api 8000:8000
```

---

## Need Help?

- **FAQ**: See [REFERENCE_GUIDE_EN.md §16](REFERENCE_GUIDE_EN.md#16-faq)
- **Issues**: [GitHub Issues](https://github.com/lulin70/DevSquad/issues)
- **Version History**: [CHANGELOG.md](../CHANGELOG.md)

---

*DevSquad V3.6.0 — Get started in 5 minutes ⏱️*
