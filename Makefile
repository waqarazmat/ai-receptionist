# AI Receptionist — convenience commands
# Usage: make <target>
# Requires: Python 3.11+, Node 18+, PostgreSQL, Redis, ffmpeg

BACKEND_DIR  = backend
FRONTEND_DIR = frontend
VENV         = $(BACKEND_DIR)/.venv
PYTHON       = $(VENV)/bin/python
PIP          = $(VENV)/bin/pip
UVICORN      = $(VENV)/bin/uvicorn
ARQ          = $(VENV)/bin/arq
ALEMBIC      = $(VENV)/bin/alembic
PYTEST       = $(VENV)/bin/pytest

# ── Setup ─────────────────────────────────────────────────────────────────────

.PHONY: setup
setup: setup-backend setup-frontend
	@echo "✅ Setup complete. Copy .env.example → .env and fill in your values."

.PHONY: setup-backend
setup-backend:
	@echo "→ Creating Python venv and installing dependencies..."
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r $(BACKEND_DIR)/requirements.txt
	@if [ ! -f .env ]; then cp .env.example .env; echo "→ Copied .env.example → .env"; fi

.PHONY: setup-frontend
setup-frontend:
	@echo "→ Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && npm install
	@if [ ! -f $(FRONTEND_DIR)/.env ]; then cp $(FRONTEND_DIR)/.env.example $(FRONTEND_DIR)/.env; echo "→ Copied frontend/.env.example → frontend/.env"; fi

# ── Development servers ───────────────────────────────────────────────────────

.PHONY: backend
backend:
	cd $(BACKEND_DIR) && ../$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: worker
worker:
	cd $(BACKEND_DIR) && ../$(ARQ) app.tasks.worker.WorkerSettings

.PHONY: frontend
frontend:
	cd $(FRONTEND_DIR) && npm run dev

# ── Database ──────────────────────────────────────────────────────────────────

.PHONY: migrate
migrate:
	cd $(BACKEND_DIR) && ../$(ALEMBIC) upgrade head

.PHONY: migration
migration:
	@read -p "Migration description: " desc; \
	cd $(BACKEND_DIR) && ../$(ALEMBIC) revision --autogenerate -m "$$desc"

# ── Tests ─────────────────────────────────────────────────────────────────────

.PHONY: test
test:
	cd $(BACKEND_DIR) && ../$(PYTEST) tests/ -v

.PHONY: typecheck
typecheck:
	cd $(FRONTEND_DIR) && npx tsc --noEmit

# ── Keys (helpers for generating secrets) ─────────────────────────────────────

.PHONY: gen-jwt-key
gen-jwt-key:
	@$(PYTHON) -c "import secrets; print(secrets.token_hex(32))"

.PHONY: gen-fernet-key
gen-fernet-key:
	@$(PYTHON) -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
