#!/usr/bin/env python3
"""
Prometheus Metrics API Routes for DevSquad

Exposes /metrics endpoint for Prometheus scraping.
Integrates with FastAPI application.

Usage:
    from scripts.api.routes.metrics import router as prometheus_router
    app.include_router(prometheus_router)

Endpoint:
    GET /metrics - Prometheus exposition format metrics
"""

import logging

from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from scripts.collaboration.prometheus_metrics import get_metrics

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="",
    tags=["Prometheus"],
)


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    summary="Prometheus Metrics Endpoint",
    description="""
Expose Prometheus metrics in standard exposition format.

Scrape this endpoint with Prometheus:
```yaml
scrape_configs:
  - job_name: 'devsquad'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

**Available Metrics:**
- `devsquad_dispatch_total` - Task dispatch counter (labels: mode, role_count)
- `devsquad_dispatch_duration_seconds` - Dispatch latency histogram
- `devsquad_llm_calls_total` - LLM API call counter (labels: backend, success)
- `devsquad_llm_duration_seconds` - LLM latency histogram
- `devsquad_cache_hits_total` - Cache hit counter (labels: cache_level, operation)
- `devsquad_cache_misses_total` - Cache miss counter
- `devsquad_workers_active` - Active worker gauge (labels: worker_type)
- `devsquad_errors_total` - Error counter (labels: error_type, component)
- `devsquad_tasks_in_progress` - Tasks in progress gauge (labels: phase)
- `devsquad_consensus_rounds_total` - Consensus round counter
- `devsquad_gate_checks_total` - Gate check counter (labels: gate_name, result)
- `devsquad_build` - Build info metadata
""",
)
async def prometheus_metrics() -> Response:
    """
    Expose Prometheus metrics endpoint.

    Returns Prometheus exposition format text for scraping.
    Returns 503 if prometheus-client is not installed.
    """
    metrics = get_metrics()

    if not metrics.is_available():
        return Response(
            content="# prometheus-client not installed. pip install prometheus-client\n",
            status_code=503,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    metrics_data = metrics.generate_metrics()
    if metrics_data is None:
        return Response(
            content="# No metrics available\n",
            status_code=503,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return Response(
        content=metrics_data,
        status_code=200,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
