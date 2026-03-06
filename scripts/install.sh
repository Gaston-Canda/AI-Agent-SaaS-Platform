#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "[install] Starting installation..."

if ! command -v docker >/dev/null 2>&1; then
  echo "[install] ERROR: Docker is required." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "[install] ERROR: docker compose plugin is required." >&2
  exit 1
fi

if ! command -v python >/dev/null 2>&1; then
  echo "[install] ERROR: Python 3.11+ is required." >&2
  exit 1
fi

python - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("[install] ERROR: Python 3.11+ is required")
print(f"[install] Python OK: {sys.version.split()[0]}")
PY

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[install] Created .env from .env.example"
fi

python - <<'PY'
import pathlib
import re
import secrets

env_path = pathlib.Path('.env')
content = env_path.read_text(encoding='utf-8')
if re.search(r'^SECRET_KEY=(?:your-super-secret-key-change-this-in-production-12345678|change-me)?\s*$', content, flags=re.MULTILINE):
    key = secrets.token_urlsafe(48)
    content = re.sub(r'^SECRET_KEY=.*$', f'SECRET_KEY={key}', content, flags=re.MULTILINE)
    env_path.write_text(content, encoding='utf-8')
    print('[install] Generated SECRET_KEY in .env')
else:
    print('[install] SECRET_KEY already configured')
PY

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ -f frontend/package.json ]; then
  if command -v npm >/dev/null 2>&1; then
    (cd frontend && npm install && npm run build)
  else
    echo "[install] WARNING: npm not found, skipping local frontend build."
  fi
fi

docker compose up -d --build postgres redis
docker compose run --rm api python scripts/init_db.py

docker compose up -d --build api worker flower frontend

echo "[install] Installation completed."
echo "[install] API:      http://localhost:${API_PORT:-8000}/api/docs"
echo "[install] Frontend: http://localhost:${FRONTEND_PORT:-3000}"
echo "[install] Flower:   http://localhost:${FLOWER_PORT:-5555}"
