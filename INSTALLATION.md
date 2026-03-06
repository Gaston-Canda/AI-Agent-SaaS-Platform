# Installation Guide

## One-command deployment

1. Copy environment template (if `.env` does not exist):

```bash
cp .env.example .env
```

2. Run installer:

```bash
./scripts/install.sh
```

On Windows PowerShell:

```powershell
./scripts/install.ps1
```

3. Start stack manually (optional):

```bash
docker compose up --build
```

## Services

- API: `http://localhost:8000`
- API docs: `http://localhost:8000/api/docs`
- Health: `http://localhost:8000/api/health`
- Frontend: `http://localhost:3000`
- Flower: `http://localhost:5555`

## First run defaults

- Tenant slug: `default`
- Admin email: `admin@example.com`
- Admin password: value from `DEFAULT_ADMIN_PASSWORD` in `.env`

You can disable bootstrap with:

```env
BOOTSTRAP_DEFAULT_ADMIN=False
```
