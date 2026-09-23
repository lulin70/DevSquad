# DevSquad Configuration Guide

> **Version**: V4.4.1 | **Updated**: 2026-07-30
>
> Complete configuration reference for all DevSquad components including LLM backends (mock/openai/anthropic/moka/auto/trae/fallback), Authentication, REST API, Alerts, Historical Data Storage.
>
> **Note**: This file remains under `docs/guides/CONFIGURATION.md` for now.
> V4.4.1 阶段 1 计划曾提议上移到根目录，但为减少链接断裂风险暂缓；上移将随 V4.5.0 文档体系大调整时一并执行。

## Configuration Methods

DevSquad supports 3 configuration methods with clear priority:

**Priority: Environment Variables > Config File > Defaults**

## Method 1: Environment Variables (Highest Priority)

```bash
# LLM Backend — DevSquad reads DEVSQUAD_-prefixed vars first, falls back to bare names
export DEVSQUAD_OPENAI_API_KEY="sk-..."     # Required for OpenAI backend (or OPENAI_API_KEY)
export DEVSQUAD_OPENAI_BASE_URL="https://api.openai.com/v1"  # Optional: custom endpoint
export OPENAI_MODEL="gpt-4"                 # Optional: model name

export DEVSQUAD_ANTHROPIC_API_KEY="sk-ant-..."  # Required for Anthropic backend (or ANTHROPIC_API_KEY)
export ANTHROPIC_MODEL="claude-sonnet-4-20250514"  # Optional: model name

# Moka AI backend (V4.0.7+)
export MOKA_API_KEY="your-moka-key"         # Required for Moka backend
export MOKA_API_BASE="https://api.moka-ai.com/v1"
export MOKA_MODEL="moka/claude-sonnet-4-6"

# DevSquad Settings
export DEVSQUAD_LLM_BACKEND=auto            # Backend: auto/mock/openai/anthropic/moka/trae/fallback
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
  # LLM Backend — auto tries real LLM first, falls back to mock
  backend: auto                    # auto/mock/openai/anthropic/moka/trae/fallback
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
| `backend` | `auto` | Auto tries real LLM first, falls back to mock |
| `model` | `gpt-4` (OpenAI) / `claude-sonnet-4-20250514` (Anthropic) / `moka/claude-sonnet-4-6` (Moka) | Default model per backend |
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

## Python API Configuration

ConfigManager was removed in V3.7.2 (dead code). Configuration is managed via environment variables and `~/.devsquad.yaml` only. No Python API for runtime config modification is provided.

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

## Real Provider Verification (OpenAI-compatible / DeepSeek)

DevSquad drives any OpenAI-compatible endpoint through two code paths, and they do
**not** read the same environment variables:

| Path | Entry point | Variables read |
|------|-------------|----------------|
| CLI | `devsquad dispatch --backend openai` | `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`, falling back to the `DEVSQUAD_OPENAI_*` names |
| Library | `create_backend()`, `devsquad doctor` | `DEVSQUAD_OPENAI_API_KEY` / `DEVSQUAD_OPENAI_BASE_URL` / `DEVSQUAD_OPENAI_MODEL` |

Setting only one pair is a real trap: configure **both** when you point DevSquad at a
non-OpenAI host (for example DeepSeek), or the CLI and the library will disagree about
which endpoint and model are in play.

### Reasoning models: reasoning tokens count against `max_tokens`

`deepseek-flash` is a reasoning model. It returns its chain of thought in a separate
`reasoning_content` field, but those tokens are still billed into `max_tokens`. A
long-reasoning prompt (code review / diff analysis — DevSquad's main workload) can
therefore consume the entire budget and come back with `finish_reason='length'` and an
**empty** `content`, even though the request "succeeded". Raise `max_tokens` for these
models, and prefer a non-reasoning model when a small, hard budget is required.

The effective budget is resolved as: explicit `max_tokens` argument →
`DEVSQUAD_REASONING_MAX_TOKENS` (env override, applied to any model) →
`DEFAULT_LLM_MAX_TOKENS_REASONING` (`16384`, applied when the model name matches the
reasoning-model markers in `scripts/collaboration/reasoning_budget.py`) →
`DEFAULT_LLM_MAX_TOKENS` (`4096`).

An empty `content` with `finish_reason='length'` is **not** treated as success:
`OpenAIBackend.generate()` logs a WARNING naming the model and the effective `max_tokens`,
then raises, so the fallback chain degrades to the next backend instead of returning an
empty answer. A truncated-but-non-empty answer is still returned unchanged.

### List the provider's available models

Ask the provider directly instead of guessing the model id:

```bash
# The key is read from the environment/.env — never passed on the command line.
set -a; source .env; set +a
curl -sS -H "Authorization: Bearer $DEVSQUAD_OPENAI_API_KEY" \
  "$DEVSQUAD_OPENAI_BASE_URL/models" \
  | python3 -c 'import json, sys; print([m["id"] for m in json.load(sys.stdin)["data"]])'
```

The current provider (DeepSeek, `https://api.deepseek.com/v1`) offers
`deepseek-flash` and `deepseek-v4-pro`.

### Re-runnable smoke check

The same contract is asserted by the `external` test lane. It skips cleanly when no key
is configured and makes no network call in that case:

```bash
# Library path (reads DEVSQUAD_OPENAI_*; conftest.py auto-loads .env).
python3 -m pytest tests/external -q -p no:randomly

# CLI path (reads OPENAI_*): source the env first, then run a real dispatch.
set -a; source .env; set +a
python3 scripts/cli.py dispatch -t "reply with the single word: pong" --backend openai
```

## Troubleshooting

### Config file not loaded

```bash
# Check if config file exists
ls -la ~/.devsquad.yaml

# Verify config is being read
# ConfigManager removed in V3.7.2 (dead code)
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
