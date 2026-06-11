FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./

# Core runtime deps only. Cloud Run uses Vertex embeddings and the offline
# demo uses deterministic hash vectors. sentence-transformers + torch are
# optional because their image footprint is large.
ARG INSTALL_EMBEDDINGS=0
RUN pip install --upgrade pip && \
    pip install \
      "fastapi==0.136.3" "uvicorn[standard]==0.48.0" \
      "pydantic==2.13.4" "pydantic-settings==2.6.0" \
      "httpx==0.28.1" "elasticsearch==8.15.1" \
      "sse-starlette==2.1.3" \
      "tenacity==9.0.0" "python-multipart==0.0.12" \
      "beautifulsoup4==4.12.3" "lxml==5.3.0" \
      "arxiv==2.1.3" "crossrefapi==1.6.0" \
      "redis==5.1.1" "structlog==24.4.0" \
      "aiohttp==3.10.10" \
      "reportlab==4.2.5" \
      "google-cloud-firestore==2.19.0" \
      "google-adk[mcp]==2.2.0" "google-genai==2.8.0" \
      "pytest==8.3.3" "pytest-asyncio==0.24.0" "pytest-mock==3.14.0" && \
    if [ "$INSTALL_EMBEDDINGS" = "1" ]; then \
      pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.4.1" && \
      pip install "sentence-transformers==3.2.0" ; \
    fi

COPY backend/ .
COPY infra/ /app/infra/

# Default to deterministic fake embeddings; override to use real ones.
ENV EMBEDDINGS_FAKE=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
