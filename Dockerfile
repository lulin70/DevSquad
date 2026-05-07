FROM python:3.11-slim

LABEL maintainer="DevSquad Team"
LABEL description="Multi-Role AI Task Orchestrator"
LABEL version="3.5.0"

WORKDIR /app

COPY pyproject.toml ./
COPY scripts/ ./scripts/

RUN pip install --no-cache-dir -e ".[dev]"

ENV DEVSQUAD_LLM_BACKEND=mock
ENV DEVSQUAD_LOG_LEVEL=WARNING

ENTRYPOINT ["python", "scripts/cli.py"]
CMD ["--help"]
