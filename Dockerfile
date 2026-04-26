FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv for faster builds
RUN pip install --no-cache-dir uv

# Copy source
COPY . /app/

# Install package and dependencies
RUN uv pip install --system --no-cache .

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV ENABLE_WEB_INTERFACE=true

# HuggingFace Spaces expects port 7860
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

CMD ["uvicorn", "undercover_agent_city.server.app:app", "--host", "0.0.0.0", "--port", "7860"]
