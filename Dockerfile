# ============ Stage 1: Builder ============
FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml ./

RUN pip install --no-cache-dir --prefix=/install .[all]

# ============ Stage 2: Production Runtime ============
FROM python:3.12-slim AS runtime

ARG VERSION=4.0.0

LABEL maintainer="DevSquad Team"
LABEL description="DevSquad V${VERSION} - Multi-Role AI Task Orchestrator"
LABEL version="${VERSION}"
LABEL org.opencontainers.image.source="https://github.com/lulin70/DevSquad"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /install/bin /usr/local/bin

COPY scripts/ ./scripts/
COPY skills/ ./skills/
COPY skill-manifest.yaml SKILL.md CLAUDE.md ./

RUN useradd --create-home --shell /bin/bash devsquad \
    && chown -R devsquad:devsquad /app

USER devsquad

ENV DEVSQUAD_LLM_BACKEND=mock
ENV DEVSQUAD_LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "from scripts.collaboration._version import __version__; print(__version__)" || exit 1

EXPOSE 8000 8501

CMD ["python3", "-m", "scripts.cli", "--version"]

# ============ Stage 3: Dev (可选，用于开发调试) ============
FROM builder AS dev

WORKDIR /app

COPY . .

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends git vim \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash devsquad \
    && chown -R devsquad:devsquad /app

USER devsquad

ENV DEVSQUAD_LLM_BACKEND=mock
ENV DEVSQUAD_LOG_LEVEL=DEBUG

CMD ["/bin/bash"]
