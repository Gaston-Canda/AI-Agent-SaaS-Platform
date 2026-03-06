$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

Write-Host "[install] Starting installation..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "[install] ERROR: Docker is required."
}

docker compose version | Out-Null

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "[install] ERROR: Python 3.11+ is required."
}

python -c "import sys; assert sys.version_info >= (3,11), '[install] ERROR: Python 3.11+ is required'; print(f'[install] Python OK: {sys.version.split()[0]}')"

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "[install] Created .env from .env.example"
}

@'
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
'@ | python -

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if (Test-Path frontend\package.json) {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Push-Location frontend
        npm install
        npm run build
        Pop-Location
    } else {
        Write-Host "[install] WARNING: npm not found, skipping local frontend build."
    }
}

docker compose up -d --build postgres redis
docker compose run --rm api python scripts/init_db.py

docker compose up -d --build api worker flower frontend

Write-Host "[install] Installation completed."
Write-Host "[install] API:      http://localhost:8000/api/docs"
Write-Host "[install] Frontend: http://localhost:3000"
Write-Host "[install] Flower:   http://localhost:5555"
