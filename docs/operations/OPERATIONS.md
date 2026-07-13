# DevSquad Operations Manual

> **Version**: V4.0.10
> **Last Updated**: 2026-07-12
> **Audience**: DevOps engineers, system administrators

---

## 1. Deployment Modes

DevSquad consists of two services:

| Service | Entry Point | Default Port | Purpose |
|---------|-------------|--------------|---------|
| API Server | `scripts.api_server:app` (FastAPI) | 8000 | REST API, health checks, Prometheus metrics |
| Dashboard | `scripts.dashboard.app` (Streamlit) | 8501 | Web UI for task dispatch and monitoring |

### Local Development

```bash
# API Server (with auto-reload)
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

# Dashboard
streamlit run scripts/dashboard/app.py --server.port 8501

# CLI
python -m scripts.cli --version
```

### Production

```bash
# API Server (no reload, multiple workers)
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --workers 4

# Dashboard
streamlit run scripts/dashboard/app.py --server.port 8501 --server.headless true
```

---

## 2. Environment Variables

All environment variables are optional with sensible defaults.

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVSQUAD_ENV` | (empty) | Set to `production` to enable production mode (auth cannot be disabled) |
| `DEVSQUAD_LLM_BACKEND` | `mock` | LLM backend: `mock`, `openai`, `moka` |
| `DEVSQUAD_LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### API Server

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVSQUAD_API_AUTH_DISABLED` | (empty) | Set to `1` to disable API key auth (ignored in production mode) |
| `DEVSQUAD_CORS_ORIGINS` | (dev defaults) | Comma-separated allowed origins (e.g., `https://app.example.com,https://dashboard.example.com`) |
| `DEVSQUAD_RATE_LIMIT_DISABLED` | (empty) | Set to `1` to disable rate limiting |
| `DEVSQUAD_RATE_LIMIT_PER_MINUTE` | `60` | Requests per minute per IP |
| `DEVSQUAD_HTTPS_REDIRECT_ENABLED` | (empty) | Set to `1` to redirect HTTP→HTTPS (308) based on `X-Forwarded-Proto` |
| `DEVSQUAD_AUDIT_DIR` | (config default) | Directory for audit logs |

### LLM Backends

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (none) | OpenAI API key (when `DEVSQUAD_LLM_BACKEND=openai`) |
| `MOKA_API_KEY` | (none) | Moka AI API key (when `DEVSQUAD_LLM_BACKEND=moka`) |
| `MOKA_API_BASE` | `https://api.moka-ai.com/v1` | Moka AI API base URL |
| `MOKA_MODEL` | `moka/claude-sonnet-4-6` | Moka AI model name |

> **Security**: Never hardcode API keys in code or config files. Use environment variables or secret management.

---

## 3. Health Check Endpoints

DevSquad provides three health-related endpoints:

### `/api/v1/health` — Liveness Probe

**Purpose**: Reports whether the service process is alive and component status.

**Response** (200):
```json
{
  "status": "healthy",
  "version": "4.0.10",
  "uptime_seconds": 120.5,
  "components": {
    "lifecycle_protocol": "healthy",
    "history_database": "healthy"
  },
  "timestamp": "2026-07-12T10:30:00"
}
```

**Component statuses**: `healthy`, `degraded`, `unhealthy`, `not_configured`

**Implementation**: `scripts/api/routes/metrics_gates.py` → `health_check()`

### `/api/v1/ready` — Readiness Probe (v4.0.10+)

**Purpose**: Reports whether the service is ready to accept traffic. Returns 503 during startup and shutdown.

**Response when ready** (200):
```json
{
  "ready": true,
  "version": "4.0.10",
  "timestamp": "2026-07-12T10:30:00"
}
```

**Response when not ready** (503):
```json
{
  "error": "HTTP_ERROR",
  "message": "Service not ready",
  "status_code": 503
}
```

**Implementation**: `scripts/api_server.py` → `readiness_check()`

**K8s usage**:
```yaml
readinessProbe:
  httpGet:
    path: /api/v1/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
livenessProbe:
  httpGet:
    path: /api/v1/health
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 20
```

### `/metrics` — Prometheus Metrics

**Purpose**: Prometheus-format metrics for scraping.

**Auth**: Requires `AUDIT_READ` permission when auth is enabled.

**Implementation**: `scripts/api/routes/metrics.py`

---

## 4. Logging

DevSquad logs to stdout at INFO level by default.

**Configuration** (`scripts/api_server.py`):
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
```

**Key log events**:
- Startup: component initialization, security status, endpoint list
- Request: `Request: GET /api/v1/health`
- Response: `Response: 200 (took 0.003s)`
- Shutdown: `Draining traffic (ready=False)...`

**Log levels**:
- `INFO` — normal operations (default)
- `DEBUG` — detailed request/response, LLM calls (set `DEVSQUAD_LOG_LEVEL=DEBUG`)
- `WARNING` — degraded mode, rate limit disabled, auth disabled
- `ERROR` — unhandled exceptions, failed health checks

---

## 5. Startup/Shutdown Flow

### Startup Sequence

1. FastAPI app created with CORS, timing, HTTPS redirect, and rate limit middleware
2. `startup_event()` fires:
   - Security status loaded (auth, RBAC, audit logger)
   - Rate limit and HTTPS redirect status checked
   - Available endpoints logged
   - `_app_ready = True` — /ready starts returning 200
3. Server accepts requests

### Shutdown Sequence

1. SIGTERM received (uvicorn handles signal)
2. `shutdown_event()` fires:
   - `_app_ready = False` — /ready starts returning 503 (traffic drains)
   - Cleanup logged
3. Server stops accepting new connections
4. In-flight requests complete (graceful)

### Traffic Draining

During shutdown, load balancers should route traffic to other instances based on `/ready` returning 503. The `/health` endpoint continues returning 200 until the process exits, allowing liveness checks to pass during graceful shutdown.

---

## 6. Docker Deployment

### Building

```bash
# Production image
docker build --build-arg VERSION=4.0.10 -t devsquad:4.0.10 .

# Dev image (includes git, vim, source code)
docker build --target dev -t devsquad:dev .
```

### Dockerfile Structure

- **Stage 1 (builder)**: Installs dependencies via `pip install .[all]`
- **Stage 2 (runtime)**: Slim runtime with non-root `devsquad` user
- **Stage 3 (dev)**: Optional development image with git/vim

### Running

```bash
# API Server
docker run -p 8000:8000 \
  -e DEVSQUAD_LLM_BACKEND=mock \
  -e DEVSQUAD_API_AUTH_DISABLED=1 \
  devsquad:4.0.10 \
  uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000

# With production auth
docker run -p 8000:8000 \
  -e DEVSQUAD_ENV=production \
  -e DEVSQUAD_CORS_ORIGINS=https://dashboard.example.com \
  devsquad:4.0.10 \
  uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --workers 4
```

### Health Check

The Dockerfile includes a built-in health check:
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "from scripts.collaboration._version import __version__; print(__version__)" || exit 1
```

For production, override with HTTP-based health check:
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/ready || exit 1
```

### Ports

| Port | Service |
|------|---------|
| 8000 | API Server (FastAPI) |
| 8501 | Dashboard (Streamlit) |

---

## 7. Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or use different port
uvicorn scripts.api_server:app --port 8001
```

### CORS Errors

**Symptom**: Browser console shows `Access-Control-Allow-Origin` errors.

**Fix**: Set `DEVSQUAD_CORS_ORIGINS` to include the frontend origin:
```bash
export DEVSQUAD_CORS_ORIGINS="http://localhost:8501,http://localhost:3000"
```

### Rate Limit (429 Too Many Requests)

**Symptom**: API returns 429 during testing.

**Fix**:
- Increase limit: `export DEVSQUAD_RATE_LIMIT_PER_MINUTE=200`
- Disable for dev: `export DEVSQUAD_RATE_LIMIT_DISABLED=1`

### Auth (401 Unauthorized)

**Symptom**: API returns 401 with `Missing X-API-Key header`.

**Fix**:
- Dev mode: `export DEVSQUAD_API_AUTH_DISABLED=1`
- Production: Configure API keys in `config/deployment.yaml`

### /ready Returns 503

**Symptom**: `/api/v1/ready` returns 503 after startup.

**Diagnosis**:
1. Check startup logs for errors
2. Verify `startup_event()` completed successfully
3. Check if `_app_ready` flag was set (look for "Ready to accept requests!" in logs)

### HTTPS Redirect Loop

**Symptom**: Requests redirect infinitely between HTTP and HTTPS.

**Fix**: Ensure your load balancer sets `X-Forwarded-Proto: https` correctly, or disable HTTPS redirect:
```bash
unset DEVSQUAD_HTTPS_REDIRECT_ENABLED
```

---

## 8. Monitoring Checklist

| Check | Command | Expected |
|-------|---------|----------|
| Liveness | `curl http://localhost:8000/api/v1/health` | 200 with `status: healthy` |
| Readiness | `curl http://localhost:8000/api/v1/ready` | 200 with `ready: true` |
| Version | `curl http://localhost:8000/ | python -m json.tool` | `version: 4.0.10` |
| Prometheus | `curl http://localhost:8000/metrics` | Metrics in Prometheus format |
| Swagger UI | Open `http://localhost:8000/docs` | Interactive API docs |
