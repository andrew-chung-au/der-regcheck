# --------------------------------------------------------------
# Stage 1: build with uv
# --------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS builder

WORKDIR /build

COPY pyproject.toml uv.lock ./

# Install the project system-wide into the builder image
RUN uv pip install --system -e .

COPY . .

# --------------------------------------------------------------
# Stage 2: runtime image
# --------------------------------------------------------------
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install the same dependencies system-wide in the runtime image
COPY --from=builder /usr/local/lib/python3.13/site-packages \
     /usr/local/lib/python3.13/site-packages

COPY --from=builder /usr/local/bin/streamlit \
     /usr/local/bin/streamlit

COPY --from=builder /build/src /app/src
COPY --from=builder /build/config /app/config
COPY --from=builder /build/data/processed /app/data/processed
COPY --from=builder /build/data/evaluation /app/data/evaluation
COPY --from=builder /build/data/feedback /app/data/feedback
COPY --from=builder /build/.streamlit /app/.streamlit

WORKDIR /app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "src/ui/streamlit_app.py"]