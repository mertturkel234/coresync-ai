# CoreSync AI

**Autonomous Intelligence for B2B Integration.**

CoreSync AI is an AI-powered B2B API integration and technical onboarding platform. Vendors upload API documentation. Developers ask questions that are grounded in that documentation, get Python integration examples, and **run approved tests against a controlled demo API**. The product keeps *generated suggestions* separate from *verified execution results*.

> **Status:** MVP under active development. See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for what is done and verified. This is not production-ready. See [docs/SECURITY.md](docs/SECURITY.md) for limitations.

## Repository layout

| Path | Contents |
|------|----------|
| `apps/web` | Next.js (App Router), TypeScript, Tailwind, shadcn/ui, Monaco |
| `services/api` | FastAPI, SQLAlchemy, Alembic, pytest |
| `docs/` | [PRD](docs/PRD.md), [Architecture](docs/ARCHITECTURE.md), [Security](docs/SECURITY.md), [Development](docs/DEVELOPMENT.md), [Implementation plan](docs/IMPLEMENTATION_PLAN.md) |
| `docker-compose.yml` | Local PostgreSQL (pgvector image), Redis, API, web, optional PgAdmin |

## Prerequisites

- Python 3.11+ (tested on 3.14)
- Node.js 20.19+ or 22+ (tested on 24) and npm
- Optional: Docker, for PostgreSQL and Redis. Without Docker the API runs on SQLite with in-memory rate limiting.

## Quick start (without Docker)

PowerShell:

```powershell
# Backend
cd services/api
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m uvicorn app.main:create_app --factory --reload --port 8000

# Frontend (new terminal)
cd apps/web
npm ci
npm run dev
```

bash:

```bash
cd services/api && python -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:create_app --factory --reload --port 8000
# in another terminal
cd apps/web && npm ci && npm run dev
```

Open http://localhost:3000. The API is at http://localhost:8000 (interactive docs at `/docs` in development).

With no `.env`, the API uses a SQLite file under `services/api/.data/` and a random per-process JWT secret (sessions end when the API restarts).

## With Docker (PostgreSQL + Redis)

```bash
cp .env.example .env      # then edit: set POSTGRES_PASSWORD and JWT_SECRET
docker compose up -d postgres redis
# run the API and web locally against them (set DATABASE_URL / REDIS_URL from .env), or:
docker compose up --build
```

PgAdmin is optional: `docker compose --profile tools up -d pgadmin` (http://localhost:5050, bound to localhost only).

> Docker is not installed on the author's development machine, so the Compose stack has **not** been run end to end. See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#verification-status) for exactly what has and has not been verified.

## Common commands

```bash
make api-test      # pytest
make api-lint      # ruff check + format check
make web-test      # vitest
make web-lint      # eslint
make web-typecheck # tsc --noEmit
```

On Windows without `make`, run the underlying commands shown in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Health endpoints

- `GET /health/live`: process liveness.
- `GET /health/ready`: database and Redis checks. Returns 503 when a configured dependency is down.

## Security

No secrets are committed. Copy `.env.example` to `.env` (ignored by Git). See [docs/SECURITY.md](docs/SECURITY.md).
