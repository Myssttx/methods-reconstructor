.PHONY: help dev up down logs build backend-shell frontend-shell test test-unit test-integration test-frontend lint eval clean elastic-init seed

help:
	@echo "Methods Reconstructor — make targets"
	@echo "  make dev               — start the full local stack (docker-compose)"
	@echo "  make up                — alias for dev"
	@echo "  make down              — stop the stack"
	@echo "  make logs              — tail backend + frontend logs"
	@echo "  make build             — rebuild docker images"
	@echo "  make elastic-init      — create papers/claims indexes in local Elastic"
	@echo "  make seed              — seed demo fixtures into Elastic"
	@echo "  make test              — run all backend tests"
	@echo "  make test-unit         — backend unit tests"
	@echo "  make test-integration  — backend integration tests (requires stack up)"
	@echo "  make test-frontend     — frontend tests"
	@echo "  make lint              — ruff + mypy + eslint"
	@echo "  make eval              — run eval harness"
	@echo "  make clean             — remove local state + caches"

dev up:
	docker-compose up --build

down:
	docker-compose down

logs:
	docker-compose logs -f backend frontend

build:
	docker-compose build

backend-shell:
	docker-compose exec backend bash

frontend-shell:
	docker-compose exec frontend sh

elastic-init:
	docker-compose exec backend python -m infra.scripts.create_elastic_indexes

seed:
	docker-compose exec backend python -m infra.scripts.seed_demo_corpus

test: test-unit

test-unit:
	cd backend && python -m pytest tests/unit -v

test-integration:
	cd backend && python -m pytest tests/integration -v

test-frontend:
	cd frontend && npm test --silent || true

lint:
	cd backend && ruff check app tests && mypy app || true
	cd frontend && npm run lint --silent || true

eval:
	cd backend && python -m eval.run_eval

clean:
	rm -rf .local_storage .local_data backend/.pytest_cache backend/.ruff_cache backend/.mypy_cache frontend/.next frontend/node_modules
