# Development guide

## Environment

| Tool | Required | Notes |
|------|----------|-------|
| Python | 3.11+ | Tested on 3.14.6 |
| Node.js / npm | 20.19+ / 22+ | Tested on Node 24, npm 11 |
| Docker | optional | Needed for the Compose stack and for real PostgreSQL/Redis |

Configuration comes from environment variables (see [../.env.example](../.env.example)). The API also reads `services/api/.env` if present.

## Backend commands (run from `services/api`)

```powershell
.\.venv\Scripts\python -m pytest                 # tests
.\.venv\Scripts\python -m ruff check .           # lint
.\.venv\Scripts\python -m ruff format --check .  # formatting
.\.venv\Scripts\python -m alembic upgrade head   # migrations
.\.venv\Scripts\python -m uvicorn app.main:create_app --factory --reload --port 8000
```

## Frontend commands (run from `apps/web`)

```bash
npm run dev         # dev server on :3000
npm run build       # production build
npm run typecheck
npm run lint
npm test            # vitest
npm run test:e2e    # playwright (needs backend + browsers installed)
```

## Test strategy

- **Backend:** pytest with a file-backed SQLite database per test and fake Redis. Tests that cover security boundaries are named `test_*isolation*`, `test_*credentials*`, and so on.
- **Frontend:** Vitest and Testing Library for components. Playwright for the critical browser flow.
- **AI:** deterministic offline provider, so tests never call a real LLM. Provider failure mapping is tested with a mocked HTTP transport.

## Verification status

This section records what has actually been run. It is updated as part of each phase.

| Check | Status | Notes |
|-------|--------|-------|
| Backend tests (pytest, SQLite, fake Redis) | ✅ run | See the latest commit message and `make api-test` |
| Ruff lint and format | ✅ run | |
| Frontend typecheck, lint, vitest, `next build` | ✅ run | |
| Docker Compose stack | ⛔ not run | Docker is not installed on the development machine. `docker compose config` could not be run either |
| Real PostgreSQL | ⛔ not run | Models use portable types. Migration is verified on SQLite only |
| Real Redis | ⛔ not run | Redis code is tested against `fakeredis` |
| Live LLM provider | ⛔ not run | No credentials were available. Offline mode is tested. The OpenAI-compatible client is tested only with a mocked transport |

## Troubleshooting

- **`JWT_SECRET must be set` on startup:** you are running with `ENVIRONMENT=production`. Set a random secret of at least 32 characters.
- **Sessions end after an API restart in development:** expected. A random secret is generated per process unless `JWT_SECRET` is set.
- **Web shows "API unreachable":** check that the API is running on `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`) and that `CORS_ORIGINS` includes the web origin.
- **`pip install` fails on a very new Python:** use a supported Python (3.11–3.14) and a fresh virtualenv.
