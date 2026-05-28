FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install \
      "fastapi==0.115.0" "uvicorn[standard]==0.32.0" \
      "pydantic==2.9.2" "pydantic-settings==2.6.0" \
      "httpx==0.27.2" "elasticsearch==8.15.1" \
      "sentence-transformers==3.2.0" "sse-starlette==2.1.3" \
      "tenacity==9.0.0" "python-multipart==0.0.12" \
      "beautifulsoup4==4.12.3" "lxml==5.3.0" \
      "arxiv==2.1.3" "crossrefapi==1.6.0" \
      "redis==5.1.1" "structlog==24.4.0" \
      "pytest==8.3.3" "pytest-asyncio==0.24.0" "pytest-mock==3.14.0"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
