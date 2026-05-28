FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

# Core runtime deps only. sentence-transformers + torch are huge (multi-GB
# on ARM64 once CUDA wheels resolve) and only needed for real embeddings;
# the offline demo path uses EMBEDDINGS_FAKE=1 (deterministic hash vectors).
# Opt in to the heavy install with `--build-arg INSTALL_EMBEDDINGS=1`.
ARG INSTALL_EMBEDDINGS=0
RUN pip install --upgrade pip && \
    pip install \
      "fastapi==0.115.0" "uvicorn[standard]==0.32.0" \
      "pydantic==2.9.2" "pydantic-settings==2.6.0" \
      "httpx==0.27.2" "elasticsearch==8.15.1" \
      "sse-starlette==2.1.3" \
      "tenacity==9.0.0" "python-multipart==0.0.12" \
      "beautifulsoup4==4.12.3" "lxml==5.3.0" \
      "arxiv==2.1.3" "crossrefapi==1.6.0" \
      "redis==5.1.1" "structlog==24.4.0" \
      "pytest==8.3.3" "pytest-asyncio==0.24.0" "pytest-mock==3.14.0" && \
    if [ "$INSTALL_EMBEDDINGS" = "1" ]; then \
      pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.4.1" && \
      pip install "sentence-transformers==3.2.0" ; \
    fi

COPY . .

# Default to deterministic fake embeddings; override to use real ones.
ENV EMBEDDINGS_FAKE=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
