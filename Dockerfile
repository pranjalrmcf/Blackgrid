# Phase 7: same Python, Debian security refresh; digest inspected 2026-10-23.
ARG PYTHON_IMAGE=python:3.11.17-slim-trixie@sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377
FROM ghcr.io/astral-sh/uv:0.11.32@sha256:df4cae8f3a96d175e2e5f992e597550000edbe78fdc2594d5cd8de1a217f504c AS uv
FROM ${PYTHON_IMAGE} AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
ARG DOWNLOAD_TIMEOUT=180
ARG DOWNLOAD_CONCURRENCY=2
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=${DOWNLOAD_TIMEOUT} UV_HTTP_RETRIES=2 UV_CONCURRENT_DOWNLOADS=${DOWNLOAD_CONCURRENCY}
WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
# Include the existing optional methods; do not silently lose Leiden support.
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --all-extras --no-install-project

FROM dependencies AS test-dependencies
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --all-extras --group quality --no-install-project

FROM dependencies AS benchmark-dependencies
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --group benchmark --all-extras --no-install-project

FROM ${PYTHON_IMAGE} AS runtime
ENV PATH=/opt/venv/bin:$PATH PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 PYTHONNOUSERSITE=1 BLACKGRID_ENV=production \
    BLACKGRID_CONFIG=/app/configs/collegemsg_sprint01.json \
    BLACKGRID_DATA_ROOT=/app BLACKGRID_RUNS_DIR=/app/runs \
    BLACKGRID_SHUTDOWN_GRACE_SECONDS=30 HOME=/tmp
WORKDIR /app
# Runtime is installed with uv in a separate stage; remove unused base packaging
# tools (including their vulnerable vendored copies), not application packages.
RUN /usr/local/bin/python -m pip uninstall -y pip setuptools wheel
RUN groupadd --gid 10001 blackgrid && useradd --uid 10001 --gid 10001 --no-create-home blackgrid \
    && mkdir /app/runs /app/data /app/results && chown 10001:10001 /app/runs \
    && printf '#!/bin/sh\nexec python -m blackgrid "$@"\n' > /usr/local/bin/blackgrid \
    && chmod 0555 /usr/local/bin/blackgrid
COPY --from=dependencies /opt/venv /opt/venv
COPY src/ ./src/
COPY configs/ ./configs/
COPY protocols/ ./protocols/
COPY docs/sprint04_review_rubric.md ./docs/sprint04_review_rubric.md
COPY pyproject.toml uv.lock README.md LICENSE ./
USER 10001:10001
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD ["python", "-m", "blackgrid.operations", "health", "--readiness"]
ENTRYPOINT ["python", "-m", "blackgrid.operations"]
CMD ["serve"]

# Tests and pytest exist only in this explicit verification target.
FROM runtime AS test
COPY --from=test-dependencies /opt/venv /opt/venv
COPY tests/ ./tests/
COPY scripts/ask_api.py ./scripts/ask_api.py
COPY scripts/generate_phase6.py ./scripts/generate_phase6.py
COPY scripts/verify_phase7.py ./scripts/verify_phase7.py
COPY scripts/benchmark_phase8.py ./scripts/benchmark_phase8.py
COPY scripts/release_gate.py ./scripts/release_gate.py
COPY scripts/verify_phase9.py ./scripts/verify_phase9.py
COPY scripts/ci/ ./scripts/ci/
COPY .github/ ./.github/
COPY benchmarks/production/ ./benchmarks/production/
COPY benchmarks/dev/registry.json ./benchmarks/dev/registry.json
ENTRYPOINT ["python", "-m", "pytest"]
CMD ["-o", "addopts=", "-q", "-p", "no:cacheprovider", "--basetemp=/tmp/pytest"]

FROM runtime AS benchmark
COPY --from=benchmark-dependencies /opt/venv /opt/venv
COPY benchmarks/production/ ./benchmarks/production/
COPY scripts/generate_phase6.py ./scripts/generate_phase6.py
ENTRYPOINT ["python", "-m", "benchmarks.production.run"]

FROM runtime AS production
