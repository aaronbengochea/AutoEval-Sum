.PHONY: help install install-backend install-frontend \
        dev dev-backend dev-frontend \
        build up down \
        lint lint-backend lint-frontend \
        test test-backend test-unit test-integration \
        setup-dynamo setup-pinecone \
        clean

# ──────────────────────────────────────────────
# Help
# ──────────────────────────────────────────────
help:
	@echo ""
	@echo "AutoEval-Sum — available commands"
	@echo "──────────────────────────────────"
	@echo "  make install            Install all dependencies (backend + frontend)"
	@echo "  make install-backend    Install backend via uv"
	@echo "  make install-frontend   Install frontend via pnpm"
	@echo ""
	@echo "  make dev                Start full stack locally (compose)"
	@echo "  make dev-backend        Start backend + DynamoDB only"
	@echo "  make dev-frontend       Start frontend only"
	@echo ""
	@echo "  make build              Build Docker images"
	@echo "  make up                 Docker Compose up (detached)"
	@echo "  make down               Docker Compose down"
	@echo ""
	@echo "  make lint               Lint backend + frontend"
	@echo "  make test               Run all backend tests"
	@echo "  make test-unit          Run unit tests only"
	@echo "  make test-integration   Run integration tests only"
	@echo ""
	@echo "  make setup-dynamo       Create DynamoDB tables (idempotent)"
	@echo "  make setup-pinecone     Create Pinecone index + namespaces (idempotent)"
	@echo ""
	@echo "  make clean              Remove caches and build artifacts"

# ──────────────────────────────────────────────
# Install
# ──────────────────────────────────────────────
install: install-backend install-frontend

install-backend:
	cd apps/backend && uv sync --extra dev

install-frontend:
	cd apps/frontend && pnpm install

# ──────────────────────────────────────────────
# Development
# ──────────────────────────────────────────────
dev:
	docker compose up

dev-backend:
	docker compose up dynamodb-local backend

dev-frontend:
	cd apps/frontend && pnpm dev

# ──────────────────────────────────────────────
# Docker
# ──────────────────────────────────────────────
build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

# ──────────────────────────────────────────────
# Lint
# ──────────────────────────────────────────────
lint: lint-backend lint-frontend

lint-backend:
	cd apps/backend && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/

lint-frontend:
	cd apps/frontend && pnpm lint && pnpm type-check

# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────
test: test-backend

test-backend:
	cd apps/backend && uv run pytest tests/ -v --cov=src/autoeval_sum --cov-report=term-missing

test-unit:
	cd apps/backend && uv run pytest tests/unit/ -v

test-integration:
	cd apps/backend && uv run pytest tests/integration/ -v

# ──────────────────────────────────────────────
# Infra setup
# ──────────────────────────────────────────────
setup-dynamo:
	cd apps/backend && uv run python scripts/setup_dynamodb.py

setup-pinecone:
	cd apps/backend && uv run python scripts/setup_pinecone.py

# ──────────────────────────────────────────────
# Clean
# ──────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .next -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete."
