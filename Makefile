.PHONY: help dev up down logs build backend-shell frontend-shell test test-unit test-integration test-frontend lint eval variability cancer-stress training-export secret-scan adk-web clean elastic-init seed native-backend native-frontend native-elastic native-setup

# Use modern `docker compose` v2 (built into Docker Desktop) by default.
# Override with `make DC=docker-compose ...` if you only have the deprecated v1 binary.
DC ?= docker compose

help:
	@echo "Methods Reconstructor — make targets"
	@echo ""
	@echo "Docker stack (needs Docker Desktop or Colima):"
	@echo "  make dev               — start the full local stack"
	@echo "  make up                — alias for dev"
	@echo "  make down              — stop the stack"
	@echo "  make logs              — tail backend + frontend logs"
	@echo "  make build             — rebuild docker images"
	@echo "  make elastic-init      — create papers/claims indexes"
	@echo "  make seed              — seed demo fixtures into Elastic"
	@echo ""
	@echo "Native (no Docker):"
	@echo "  make native-setup      — one-time: install backend venv + frontend deps"
	@echo "  make native-elastic    — start Elasticsearch via Homebrew services"
	@echo "  make native-backend    — run FastAPI from backend/.venv"
	@echo "  make native-frontend   — run Next.js from frontend/node_modules"
	@echo "  make adk-web           — run the Google ADK research-agent UI"
	@echo ""
	@echo "Tests + tooling:"
	@echo "  make test              — run all backend tests"
	@echo "  make test-unit         — backend unit tests"
	@echo "  make test-integration  — backend integration tests (requires stack)"
	@echo "  make test-frontend     — frontend tests"
	@echo "  make lint              — ruff + mypy + eslint"
	@echo "  make eval              — run eval harness"
	@echo "  make variability ID=…  — repeat a full run and report consistency"
	@echo "  make cancer-stress     — run complex public cancer papers"
	@echo "  make training-export   — export source-backed JSONL examples"
	@echo "  make secret-scan       — scan tracked files for committed secrets"
	@echo "  make clean             — remove local state + caches"

dev up:
	$(DC) up --build

down:
	$(DC) down

logs:
	$(DC) logs -f backend frontend

build:
	$(DC) build

backend-shell:
	$(DC) exec backend bash

frontend-shell:
	$(DC) exec frontend sh

elastic-init:
	$(DC) exec backend python -m infra.scripts.create_elastic_indexes

seed:
	$(DC) exec backend python -m infra.scripts.seed_demo_corpus

# ---- Native (no-Docker) targets ----

native-setup:
	cd backend && python3 -m venv .venv && \
		.venv/bin/pip install --upgrade pip && \
		.venv/bin/pip install \
			"fastapi==0.136.3" "uvicorn[standard]==0.48.0" \
			"pydantic==2.13.4" "pydantic-settings==2.6.0" \
			"httpx==0.28.1" "elasticsearch==8.15.1" \
			"sentence-transformers==3.2.0" "sse-starlette==2.1.3" \
			"tenacity==9.0.0" "python-multipart==0.0.12" \
			"beautifulsoup4==4.12.3" "lxml==5.3.0" \
			"arxiv==2.1.3" "crossrefapi==1.6.0" \
			"redis==5.1.1" "structlog==24.4.0" "aiohttp==3.10.10" \
			"reportlab==4.2.5" "google-cloud-firestore==2.19.0" \
			"google-adk[mcp]==2.2.0" "google-genai==2.8.0" \
			"pytest==8.3.3" "pytest-asyncio==0.24.0"
	cd frontend && npm install --no-audit --no-fund

native-elastic:
	brew services start elastic/tap/elasticsearch-full 2>/dev/null || brew services start elasticsearch

native-backend:
	cd backend && ELASTIC_URL=http://localhost:9200 \
		.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

native-frontend:
	cd frontend && npm run dev

adk-web:
	cd backend && .venv/bin/adk web

native-elastic-init:
	cd backend && ELASTIC_URL=http://localhost:9200 \
		.venv/bin/python ../infra/scripts/create_elastic_indexes.py

native-seed:
	cd backend && ELASTIC_URL=http://localhost:9200 EMBEDDINGS_FAKE=1 \
		.venv/bin/python ../infra/scripts/seed_demo_corpus.py

test: test-unit

test-unit:
	cd backend && .venv/bin/python -m pytest tests/unit -v

test-integration:
	cd backend && .venv/bin/python -m pytest tests/integration -v

test-frontend:
	cd frontend && npm test --silent || true

lint:
	cd backend && .venv/bin/ruff check app tests && .venv/bin/mypy app || true
	cd frontend && npm run lint --silent || true

eval:
	backend/.venv/bin/python eval/run_eval.py

variability:
	test -n "$(ID)" || { echo "Usage: make variability ID=fixture:paper_a"; exit 1; }
	ELASTIC_URL=http://localhost:9200 \
		backend/.venv/bin/python eval/run_variability.py "$(ID)" --runs "$(or $(RUNS),3)"

cancer-stress:
	ELASTIC_URL=http://localhost:9200 \
		backend/.venv/bin/python eval/run_cancer_stress.py

training-export:
	backend/.venv/bin/python eval/export_training_jsonl.py

secret-scan:
	./scripts/check-secrets.sh

clean:
	rm -rf .local_storage .local_data backend/.pytest_cache backend/.ruff_cache backend/.mypy_cache frontend/.next frontend/node_modules
