#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# AI Receptionist — Start Script  (macOS)
#
# First time:
#   chmod +x start.sh
#   ./start.sh
#
# Every time after that:
#   ./start.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e
REPO="$(cd "$(dirname "$0")" && pwd)"
FRONTEND="$REPO/frontend"
BACKEND="$REPO/backend"
VENV="$BACKEND/.venv"

# ── Colors ────────────────────────────────────────────────────────────────────
BOLD='\033[1m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'
YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

step() { echo -e "\n${BOLD}${BLUE}▶ $1${NC}"; }
ok()   { echo -e "  ${GREEN}✓ $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠ $1${NC}"; }
die()  { echo -e "\n${RED}✗ ERROR: $1${NC}\n"; exit 1; }

echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║     AI Receptionist Platform         ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ── Detect mode: frontend-only vs full-stack ──────────────────────────────────
# If VITE_API_URL in frontend/.env points to a remote host (not localhost),
# we skip Python/backend setup — the backend is already running on Railway.

FRONTEND_ENV="$FRONTEND/.env"
if [[ ! -f "$FRONTEND_ENV" ]]; then
  [[ -f "$FRONTEND/.env.example" ]] && cp "$FRONTEND/.env.example" "$FRONTEND_ENV"
fi

API_URL=$(grep "^VITE_API_URL=" "$FRONTEND_ENV" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
FULL_STACK=true
if [[ "$API_URL" == *"localhost"* || "$API_URL" == *"127.0.0.1"* || -z "$API_URL" ]]; then
  FULL_STACK=true
  echo -e "  Mode: ${BOLD}Full-stack local${NC}  (backend + frontend)"
else
  FULL_STACK=false
  echo -e "  Mode: ${BOLD}Frontend only${NC}  (backend → $API_URL)"
fi

# ── Check Node.js (always required) ──────────────────────────────────────────
step "Checking Node.js..."
if ! command -v node &>/dev/null; then
  die "Node.js not found.\n  Install LTS from https://nodejs.org then run this script again."
fi
NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
if [[ "$NODE_VER" -lt 18 ]]; then
  die "Node.js 18+ required (you have $(node -v)).\n  Download LTS from https://nodejs.org"
fi
ok "Node.js $(node -v)"

# ── Frontend: install deps ────────────────────────────────────────────────────
step "Frontend dependencies..."
if [[ ! -d "$FRONTEND/node_modules" ]]; then
  echo "  Installing npm packages (first time — takes ~1 min)..."
  cd "$FRONTEND" && npm install --silent
  ok "npm packages installed"
else
  ok "Already installed"
fi

if $FULL_STACK; then
  # ── Check Python ────────────────────────────────────────────────────────────
  step "Checking Python 3.11+..."
  PYTHON=""
  for cmd in python3.11 python3.12 python3.13 python3; do
    if command -v "$cmd" &>/dev/null; then
      PY_MINOR=$("$cmd" -c "import sys; print(sys.version_info.minor)")
      PY_MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)")
      if [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -ge 11 ]]; then
        PYTHON="$cmd"; break
      fi
    fi
  done
  if [[ -z "$PYTHON" ]]; then
    die "Python 3.11+ not found.\n  Install with: brew install python@3.11\n  Or from: https://www.python.org/downloads/macos/"
  fi
  ok "Python $($PYTHON --version)"

  # ── Backend: virtual environment ────────────────────────────────────────────
  step "Python virtual environment..."
  if [[ ! -d "$VENV" ]]; then
    "$PYTHON" -m venv "$VENV"
    ok "Created .venv"
  else
    ok "Already exists"
  fi

  # ── Backend: install deps ────────────────────────────────────────────────────
  step "Backend dependencies..."
  if ! "$VENV/bin/python" -c "import fastapi" &>/dev/null 2>&1; then
    echo "  Installing Python packages..."
    echo "  (First time: sentence-transformers downloads ~900 MB of AI model files."
    echo "   Subsequent runs skip this entirely.)"
    "$VENV/bin/pip" install --upgrade pip -q
    "$VENV/bin/pip" install -r "$BACKEND/requirements.txt"
    ok "Python packages installed"
  else
    ok "Already installed"
  fi

  # ── Database migrations ──────────────────────────────────────────────────────
  step "Database migrations..."
  cd "$BACKEND"
  if "$VENV/bin/alembic" upgrade head 2>/dev/null; then
    ok "Database up to date"
  else
    warn "Migration failed — check DATABASE_URL in .env  (continuing anyway)"
  fi
fi

# ── Check .env ────────────────────────────────────────────────────────────────
step "Environment config..."
if [[ ! -f "$REPO/.env" ]] && $FULL_STACK; then
  die ".env file missing from the project root.\n  Make sure the .env file was included in the zip."
fi
ok ".env present"

# ── Launch in Terminal tabs ───────────────────────────────────────────────────
step "Launching servers..."

if $FULL_STACK; then
  BACKEND_CMD="cd '$BACKEND' && source '$VENV/bin/activate' && clear && echo '' && echo '  BACKEND  →  http://localhost:8000' && echo '' && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
  WORKER_CMD="cd '$BACKEND' && source '$VENV/bin/activate' && clear && echo '' && echo '  ARQ WORKER  (background jobs)' && echo '' && arq app.tasks.worker.WorkerSettings"
  FRONTEND_CMD="cd '$FRONTEND' && clear && echo '' && echo '  FRONTEND  →  http://localhost:5173' && echo '' && npm run dev"

  osascript <<EOF
tell application "Terminal"
  do script "$BACKEND_CMD"
  delay 1
  tell application "System Events" to keystroke "t" using command down
  delay 0.5
  do script "$FRONTEND_CMD" in front window
  tell application "System Events" to keystroke "t" using command down
  delay 0.5
  do script "$WORKER_CMD" in front window
  activate
end tell
EOF

else
  FRONTEND_CMD="cd '$FRONTEND' && clear && echo '' && echo '  FRONTEND  →  http://localhost:5173' && echo '' && npm run dev"

  osascript <<EOF
tell application "Terminal"
  do script "$FRONTEND_CMD"
  activate
end tell
EOF
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${GREEN}  Servers are starting up!${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if $FULL_STACK; then
  echo -e "  ${BOLD}Frontend  →${NC}  http://localhost:5173"
  echo -e "  ${BOLD}Backend   →${NC}  http://localhost:8000"
  echo -e "  ${BOLD}API docs  →${NC}  http://localhost:8000/docs"
  echo ""
  echo -e "  ${YELLOW}Wait ~20 seconds for the AI embedding model to load,${NC}"
  echo -e "  ${YELLOW}then open http://localhost:5173 in your browser.${NC}"
else
  echo -e "  ${BOLD}Frontend  →${NC}  http://localhost:5173"
  echo -e "  ${BOLD}Backend   →${NC}  $API_URL  (Railway)"
  echo ""
  echo -e "  Open ${BOLD}http://localhost:5173${NC} in your browser."
fi
echo ""
