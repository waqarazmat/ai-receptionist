#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# AI Receptionist — Mac Setup Script
# Run once on a fresh Mac to get the project running locally.
#
# Usage:
#   chmod +x setup-mac.sh
#   ./setup-mac.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e  # exit on any error

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[setup]${NC} $1"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $1"; }
die()     { echo -e "${RED}[error]${NC} $1"; exit 1; }

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── 1. Homebrew ───────────────────────────────────────────────────────────────
info "Checking Homebrew..."
if ! command -v brew &>/dev/null; then
  info "Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Add brew to PATH for Apple Silicon Macs
  if [[ -f /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi
else
  info "Homebrew already installed."
fi

# ── 2. System dependencies ────────────────────────────────────────────────────
info "Installing system dependencies (ffmpeg, postgresql, redis, python)..."
brew install ffmpeg postgresql@15 redis python@3.11 node || true

# Start Postgres and Redis as background services
info "Starting PostgreSQL and Redis..."
brew services start postgresql@15 || true
brew services start redis || true

# Add postgres to PATH (brew may install to /opt/homebrew/opt/postgresql@15/bin)
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"
echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc 2>/dev/null || true

# ── 3. pgvector extension ─────────────────────────────────────────────────────
info "Installing pgvector..."
brew install pgvector || true

# ── 4. Create local database ───────────────────────────────────────────────────
info "Creating local database 'ai_receptionist'..."
createdb ai_receptionist 2>/dev/null || warn "Database may already exist — continuing."

# Enable pgvector extension
psql ai_receptionist -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || \
  warn "Could not enable vector extension — you may need to do this manually."

# ── 5. Python virtual environment ─────────────────────────────────────────────
info "Setting up Python virtual environment..."
cd "$REPO_ROOT/backend"

if [[ ! -d .venv ]]; then
  python3.11 -m venv .venv
fi
source .venv/bin/activate

info "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# ── 6. Environment file ───────────────────────────────────────────────────────
if [[ ! -f "$REPO_ROOT/.env" ]]; then
  info "Copying .env.example → .env"
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
  warn "IMPORTANT: Edit .env and fill in your values before starting the backend."
else
  info ".env already exists — skipping copy."
fi

# ── 7. Database migrations ────────────────────────────────────────────────────
if [[ -f "$REPO_ROOT/.env" ]]; then
  # Only run migrations if DATABASE_URL is set to something real
  DB_URL=$(grep "^DATABASE_URL=" "$REPO_ROOT/.env" | cut -d= -f2-)
  if [[ "$DB_URL" != *"password@localhost"* ]] || psql ai_receptionist -c "SELECT 1" &>/dev/null; then
    info "Running database migrations..."
    cd "$REPO_ROOT/backend"
    source .venv/bin/activate
    alembic upgrade head || warn "Migration failed — check DATABASE_URL in .env"
  fi
fi

# ── 8. Frontend dependencies ───────────────────────────────────────────────────
info "Installing frontend dependencies..."
cd "$REPO_ROOT/frontend"
npm install

# Copy frontend .env if missing
if [[ ! -f "$REPO_ROOT/frontend/.env" ]]; then
  cp "$REPO_ROOT/frontend/.env.example" "$REPO_ROOT/frontend/.env"
  info "Copied frontend/.env.example → frontend/.env"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Edit .env and fill in your values:"
echo "       - JWT_SECRET_KEY (generate one — see the file)"
echo "       - MASTER_ENCRYPTION_KEY (generate one — see the file)"
echo "       - SUPER_ADMIN_EMAIL"
echo "       - SMTP credentials (for OTP email delivery)"
echo ""
echo "  2. Start the backend:"
echo "       cd backend"
echo "       source .venv/bin/activate"
echo "       uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "  3. (Optional) Start the Arq worker in a second terminal:"
echo "       cd backend && source .venv/bin/activate"
echo "       arq app.tasks.worker.WorkerSettings"
echo ""
echo "  4. Start the frontend:"
echo "       cd frontend && npm run dev"
echo ""
echo "  5. Open http://localhost:5173 in your browser."
echo ""
echo -e "${YELLOW}  TIP: If the backend is already running on Railway, skip steps 2-3${NC}"
echo -e "${YELLOW}  and just set VITE_API_URL in frontend/.env to the Railway URL.${NC}"
echo ""
