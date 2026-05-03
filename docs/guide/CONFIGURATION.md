# DevSquad Configuration Guide (V3.6.0-Prod)

> **Version**: V3.6.0-Prod | **Updated**: 2026-05-03
>
> Complete configuration reference for all DevSquad components including new production features (Authentication, REST API, Alerts, Historical Data Storage).

## Configuration Methods

DevSquad supports 3 configuration methods with clear priority:

**Priority: Environment Variables > Config File > Defaults**

## Method 1: Environment Variables (Highest Priority)

```bash
# LLM Backend
export OPENAI_API_KEY="sk-..."              # Required for OpenAI backend
export OPENAI_BASE_URL="https://api.openai.com/v1"  # Optional: custom endpoint
export OPENAI_MODEL="gpt-4"                 # Optional: model name

export ANTHROPIC_API_KEY="sk-ant-..."       # Required for Anthropic backend
export ANTHROPIC_MODEL="claude-sonnet-4-20250514"  # Optional: model name

# DevSquad Settings
export DEVSQUAD_LLM_BACKEND=openai          # Default backend: mock/openai/anthropic
export DEVSQUAD_LOG_LEVEL=WARNING           # Logging level
```

> **Security**: API keys are read from environment variables only. There is no `--api-key` CLI flag.
> This prevents keys from appearing in shell history or process listings.

### Persistent Environment Variables

Add to `~/.zshrc` or `~/.bashrc`:

```bash
# Add these lines to your shell config
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4"
export DEVSQUAD_LLM_BACKEND=openai
```

Then reload: `source ~/.zshrc`

## Method 2: Configuration File (~/.devsquad.yaml)

Create `~/.devsquad.yaml`:

```yaml
devsquad:
  # LLM Backend
  backend: openai                    # mock/openai/anthropic
  base_url: https://api.openai.com/v1
  model: gpt-4
  timeout: 120                       # Request timeout in seconds

  # Output
  output_format: structured          # markdown/json/compact/structured/detailed

  # Validation
  strict_validation: false           # True = block on prompt injection

  # Infrastructure
  checkpoint_enabled: true           # Enable CheckpointManager
  cache_enabled: true                # Enable LLM cache
  log_level: WARNING                 # DEBUG/INFO/WARNING/ERROR

  # Advanced
  max_retries: 3                     # LLM retry count
  cache_ttl: 86400                   # Cache TTL in seconds (default: 24h)
  max_cache_entries: 1000            # Max LRU cache entries
```

### Config File Location

Default: `~/.devsquad.yaml`

Override via environment variable:
```bash
export DEVSQUAD_CONFIG_PATH=/custom/path/to/config.yaml
```

## Method 3: Defaults (Lowest Priority)

When no environment variables or config file values are set, DevSquad uses these defaults:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `backend` | `mock` | Mock backend returns assembled prompts |
| `model` | `gpt-4` (OpenAI) / `claude-sonnet-4-20250514` (Anthropic) | Default model per backend |
| `timeout` | `120` | Request timeout in seconds |
| `output_format` | `markdown` | Default output format |
| `strict_validation` | `false` | Warn on prompt injection (don't block) |
| `checkpoint_enabled` | `true` | CheckpointManager enabled |
| `cache_enabled` | `true` | LLM cache enabled |
| `log_level` | `WARNING` | Logging level |

## CLI Flags (Override Everything)

CLI flags override both environment variables and config file:

```bash
# Override backend
python3 scripts/cli.py dispatch -t "task" --backend openai

# Override model
python3 scripts/cli.py dispatch -t "task" --model gpt-4-turbo

# Override base URL
python3 scripts/cli.py dispatch -t "task" --base-url https://custom.api.com/v1

# Enable streaming
python3 scripts/cli.py dispatch -t "task" --stream
```

## Using ConfigManager (Python API)

```python
from scripts.collaboration.config_loader import ConfigManager

# Create manager (auto-loads: env > file > defaults)
config_mgr = ConfigManager()

# Access config values
print(f"Backend: {config_mgr.get('backend')}")
print(f"Model: {config_mgr.get('model')}")
print(f"Timeout: {config_mgr.get('timeout')}")
print(f"Strict validation: {config_mgr.get('strict_validation')}")

# Set config values
config_mgr.set('backend', 'openai')
config_mgr.set('log_level', 'DEBUG')

# Save current config to file (~/.devsquad.yaml)
config_mgr.save()
```

## Docker Configuration

Pass environment variables to Docker container:

```bash
# Single env var
docker run -e OPENAI_API_KEY="sk-..." devsquad dispatch -t "task" --backend openai

# Multiple env vars via env-file
cat > .env << EOF
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4
DEVSQUAD_LLM_BACKEND=openai
EOF

docker run --env-file .env devsquad dispatch -t "task"
```

## Environment Variable Reference

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENAI_API_KEY` | OpenAI API key | None (required for OpenAI) |
| `OPENAI_BASE_URL` | OpenAI-compatible base URL | None |
| `OPENAI_MODEL` | Model name for OpenAI | `gpt-4` |
| `ANTHROPIC_API_KEY` | Anthropic API key | None (required for Anthropic) |
| `ANTHROPIC_MODEL` | Model name for Anthropic | `claude-sonnet-4-20250514` |
| `DEVSQUAD_LLM_BACKEND` | Default backend type | `mock` |
| `DEVSQUAD_BASE_URL` | Default base URL | None |
| `DEVSQUAD_MODEL` | Default model name | None |
| `DEVSQUAD_TIMEOUT` | Request timeout | `120` |
| `DEVSQUAD_LOG_LEVEL` | Logging level | `WARNING` |
| `DEVSQUAD_CONFIG_PATH` | Custom config file path | `~/.devsquad.yaml` |
| `DEVSQUAD_STRICT_VALIDATION` | Block on prompt injection | `false` |
| `DEVSQUAD_CHECKPOINT_ENABLED` | Enable checkpoints | `true` |
| `DEVSQUAD_CACHE_ENABLED` | Enable LLM cache | `true` |

## Troubleshooting

### Config file not loaded

```bash
# Check if config file exists
ls -la ~/.devsquad.yaml

# Verify config is being read
python3 -c "from scripts.collaboration.config_loader import ConfigManager; c=ConfigManager(); print(c.to_dict())"
```

### Environment variable not taking effect

```bash
# Verify env var is set
echo $OPENAI_API_KEY
echo $DEVSQUAD_LLM_BACKEND

# Check if it's exported (not just set)
export OPENAI_API_KEY="sk-..."  # Must use 'export'
```

### API key security

DevSquad never logs or exposes API keys:
- No `--api-key` CLI flag
- Keys are masked in any debug output
- Environment variables only
