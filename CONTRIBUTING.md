# Contributing to DevSquad

Thank you for your interest in contributing to DevSquad! This guide will help you get started.

## Quick Start

### 1. Fork and Clone

```bash
# 1. Fork on GitHub: https://github.com/lulin70/DevSquad
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/DevSquad.git
cd DevSquad

# 3. Add upstream
git remote add upstream https://github.com/lulin70/DevSquad.git
```

### 2. Set Up Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Tests

```bash
# Core collaboration tests
python3 -m pytest scripts/collaboration/ -v

# Role mapping tests
python3 scripts/collaboration/role_mapping_test.py

# Specific module tests
python3 scripts/collaboration/dispatcher_test.py
python3 scripts/collaboration/memory_bridge_test.py
```

## Project Structure

```
DevSquad/
├── scripts/
│   ├── collaboration/          # Core modules (27)
│   │   ├── _version.py         # Version SSOT (3.4.0)
│   │   ├── models.py           # Data models (zero dependencies)
│   │   ├── dispatcher.py       # Unified entry point
│   │   ├── coordinator.py      # Global orchestrator
│   │   ├── scratchpad.py       # Shared blackboard
│   │   ├── worker.py           # Role executor (with streaming)
│   │   ├── consensus.py        # Consensus engine
│   │   ├── llm_backend.py      # Mock/OpenAI/Anthropic + streaming
│   │   ├── role_matcher.py     # Keyword-based role matching
│   │   ├── report_formatter.py # Structured/compact/detailed reports
│   │   ├── input_validator.py  # Security + prompt injection detection
│   │   ├── ai_semantic_matcher.py # LLM-powered semantic matching
│   │   ├── checkpoint_manager.py  # State persistence + handoff
│   │   ├── workflow_engine.py     # Task-to-workflow auto-split
│   │   ├── task_completion_checker.py # Completion tracking
│   │   ├── code_map_generator.py  # AST-based code analysis
│   │   ├── dual_layer_context.py  # Project + task context with TTL
│   │   ├── skill_registry.py     # Skill registration + discovery
│   │   ├── config_loader.py      # YAML config + env var overrides
│   │   ├── context_compressor.py
│   │   ├── permission_guard.py
│   │   ├── skillifier.py
│   │   ├── warmup_manager.py
│   │   ├── memory_bridge.py
│   │   ├── mce_adapter.py
│   │   ├── batch_scheduler.py
│   │   ├── prompt_assembler.py
│   │   ├── prompt_variant_generator.py
│   │   └── test_quality_guard.py
│   ├── services/               # Task/translation services
│   ├── tests/                  # Integration tests
│   ├── vibe_coding/            # Vibe coding module
│   ├── cli.py                  # CLI entry point
│   └── mcp_server.py           # MCP Server for OpenClaw
├── .github/workflows/          # CI (Python 3.9-3.12 matrix)
├── data/                       # Runtime data (gitignored)
├── docs/                       # Documentation
├── Dockerfile                  # Docker support
├── pyproject.toml              # pip-installable package
├── skill-manifest.yaml         # Trae IDE skill manifest
├── CLAUDE.md                   # Claude Code integration
├── SKILL.md                    # Operational manual (EN)
├── docs/i18n/SKILL_CN.md         # Operational manual (CN)
├── docs/i18n/SKILL_JP.md         # Operational manual (JP)
└── README.md                   # Project readme
```

## Role System

DevSquad has **7 core roles** with full prompt templates:

| Core Role | ID | Aliases |
|-----------|-----|---------|
| Architect | `architect` | `arch` |
| Product Manager | `product-manager` | `pm` |
| Security Expert | `security` | `sec` |
| Tester | `tester` | `test`, `qa` |
| Coder | `solo-coder` | `coder`, `dev` |
| DevOps | `devops` | `infra` |
| UI Designer | `ui-designer` | `ui` |

When adding a new role, update:
1. `ROLE_REGISTRY` in `scripts/collaboration/models.py`
2. `ROLE_WEIGHTS` in `scripts/collaboration/models.py`
3. Role table in `README.md`, `SKILL.md`, `docs/i18n/SKILL_CN.md`, `docs/i18n/SKILL_JP.md`

## Code Style

- **Python**: PEP 8, dataclasses for models, type hints throughout
- **Imports**: Use relative imports within `scripts/collaboration/`
- **Docstrings**: English, Google style
- **Comments**: English
- **No comments in code** unless explicitly asked

## Commit Guidelines

```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Make changes, then commit
git add -A
git commit -m "feat: add your feature description"

# Push to your fork
git push origin feature/your-feature-name

# Open a Pull Request on GitHub
```

Commit message prefixes:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation change
- `refactor:` Code refactoring
- `test:` Test addition/fix
- `chore:` Build/maintenance

## Testing Standards

- Every new module must have a corresponding `*_test.py` file
- Use `unittest` framework for consistency
- Test file location: same directory as the module (e.g., `scripts/collaboration/`)
- Run from project root: `python3 scripts/collaboration/your_test.py`
- Minimum: test happy path + error path + edge cases

## Questions?

Open an issue at https://github.com/lulin70/DevSquad/issues
