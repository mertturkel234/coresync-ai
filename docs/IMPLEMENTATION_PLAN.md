# CoreSync AI — Implementation Plan

Status legend: ☐ not started · ◐ in progress · ☑ done and verified · ⛔ blocked.
Complexity: S, M, L. Tasks are reviewable feature units, not trivial chores.

> **Status updates are made only after the checks listed under "Tests" have actually run.**

## Phase checklist

- [x] Phase 0 — Inspection and planning
- [ ] Phase 1 — Monorepo and infrastructure
- [ ] Phase 2 — Data model and access control
- [ ] Phase 3 — Documentation ingestion
- [ ] Phase 4 — AI orchestration and retrieval
- [ ] Phase 5 — Sandbox credentials and controlled test execution
- [ ] Phase 6 — Frontend implementation
- [ ] Phase 7 — End-to-end integration
- [ ] Phase 8 — Quality, security, documentation

## Phase 0 — Inspection and planning

| ID | Title | Description | Depends | Files | Acceptance | Tests | Size | Status |
|----|-------|-------------|---------|-------|------------|-------|------|--------|
| DOCS-000 | Planning documents | Write PRD, architecture and ADRs, security model, and this plan. Verify the target repo and branch. | none | `docs/*.md` | Documents exist and are consistent with the MVP. Remote verified. No secrets. | Manual review. `git ls-remote`. | M | ☑ |

## Phase 1 — Monorepo and infrastructure

| ID | Title | Description | Depends | Files | Acceptance | Tests | Size | Status |
|----|-------|-------------|---------|-------|------------|-------|------|--------|
| INFRA-001 | Backend skeleton and health | FastAPI app factory, settings, request-id middleware, `/health/live` and `/health/ready` with real DB and Redis checks. | DOCS-000 | `services/api/app/{main,core,db}` | Health returns correct status for DB and Redis (ok, error, or not_configured). | `tests/test_health.py` | M | ☐ |
| INFRA-002 | Tooling | Ruff config, pytest config, Makefile, `.env.example`. | INFRA-001 | `pyproject.toml`, `Makefile`, `.env.example` | `make lint test` pass. | lint and test run | S | ☐ |
| INFRA-003 | Frontend skeleton | Next.js App Router, strict TypeScript, Tailwind, shadcn/ui, dark theme, Vitest. | DOCS-000 | `apps/web` | `npm run dev`, `build`, `typecheck`, `lint`, and `test` pass. | Vitest smoke test | M | ☐ |
| INFRA-004 | Docker Compose | Postgres (pgvector image), Redis, api, web, optional PgAdmin profile, Dockerfiles. | INFRA-001, INFRA-003 | `docker-compose.yml`, Dockerfiles | `docker compose config` validates. A full `up` is verified only if Docker is available. | `compose config` | M | ☐ |
| INFRA-005 | README and dev docs | Setup instructions, commands, and troubleshooting. | INFRA-002 | `README.md`, `docs/DEVELOPMENT.md` | A fresh developer can follow the steps. | Follow steps | S | ☐ |

## Phase 2 — Data model and access control

| ID | Title | Description | Depends | Files | Acceptance | Tests | Size | Status |
|----|-------|-------------|---------|-------|------------|-------|------|--------|
| AUTH-001 | Models and migrations | All entities, an initial Alembic migration, and SQLite and PostgreSQL portability. | INFRA-001 | `models/`, `migrations/` | `alembic upgrade head` works on a fresh DB, and the model/migration diff is empty. | migration test | L | ☐ |
| AUTH-002 | Registration and login | Argon2id, JWT, rate limiting, and audit events. | AUTH-001 | `security/`, `api/v1/auth.py` | Bad credentials return generic errors. | `test_auth.py` | M | ☐ |
| AUTH-003 | Tenants, roles, projects | Project CRUD with membership checks, developer invites, and audit events. | AUTH-002 | `services/projects.py`, `api/v1/projects.py` | A cross-tenant request returns 404. Role rules are enforced. | `test_projects.py`, `test_tenant_isolation.py` | L | ☐ |
| AUTH-004 | Central errors and versioning | Predictable error envelope with `request_id`, `/v1` prefix, and validation errors. | INFRA-001 | `core/errors.py` | Validation, 401, 403, 404, and 500 share one schema, and the 500 leaks nothing. | `test_errors.py` | S | ☐ |

## Phase 3 — Documentation ingestion

| ID | Title | Description | Depends | Files | Acceptance | Tests | Size | Status |
|----|-------|-------------|---------|-------|------------|-------|------|--------|
| DOCS-001 | Upload and storage | Multipart upload, type and size validation, random storage key, sha256, and versioning. | AUTH-003 | `api/v1/documents.py`, `services/storage.py` | Bad type, oversize, and non-UTF-8 files are rejected with clear errors. | `test_documents_upload.py` | M | ☐ |
| DOCS-002 | OpenAPI parser | JSON and YAML, structural validation, local `$ref` resolution, alias rejection, and endpoint and schema extraction. | DOCS-001 | `ai/openapi.py` | Valid samples parse. Malformed and external `$ref` files are rejected. | `test_openapi_parser.py` | L | ☐ |
| DOCS-003 | Markdown ingestion and index | Heading-based chunks and endpoint-heading detection. Persist endpoints and chunks. Processing status. | DOCS-002 | `ai/markdown.py`, `services/ingestion.py` | The status transitions to processed or failed with error details. | `test_ingestion.py` | M | ☐ |
| DOCS-004 | Document and endpoint APIs | List and get documents, list endpoints, and enforce ownership. | DOCS-003 | `api/v1/documents.py`, `api/v1/endpoints.py` | Cross-tenant access returns 404. | `test_documents_api.py` | S | ☐ |

## Phase 4 — AI orchestration and retrieval

| ID | Title | Description | Depends | Files | Acceptance | Tests | Size | Status |
|----|-------|-------------|---------|-------|------------|-------|------|--------|
| AI-001 | Provider abstraction | `LLMProvider`, `OfflineProvider`, and `OpenAICompatibleProvider` with timeouts and error mapping. | INFRA-001 | `ai/providers.py` | Provider failures map to a typed error. Offline mode is labelled. | `test_providers.py` (mocked transport) | M | ☐ |
| AI-002 | Retrieval | Tenant- and project-filtered lexical retrieval with a sufficiency threshold. | DOCS-003 | `ai/retrieval.py` | The right endpoint ranks first, and other tenants' chunks never appear. | `test_retrieval.py` | M | ☐ |
| AI-003 | Grounded Q&A | Context builder with injection-safe delimiting, references, and an insufficient-evidence path. | AI-001, AI-002 | `services/chat.py`, `api/v1/sessions.py` | Answers cite refs. Unknown topics get an explicit "not documented" reply. | `test_chat.py` | L | ☐ |
| AI-004 | Python code generation | A request plan from an endpoint, a code template with placeholders, and a persisted `CodeExample`. | AI-002 | `ai/codegen.py` | Code contains no real secrets. The plan is validated. No code is produced for missing endpoints. | `test_codegen.py` | M | ☐ |

## Phase 5 — Sandbox credentials and controlled test execution

| ID | Title | Description | Depends | Files | Acceptance | Tests | Size | Status |
|----|-------|-------------|---------|-------|------------|-------|------|--------|
| SANDBOX-001 | Credential lifecycle | Issue, hash, scope, TTL, revoke, quota, and rate limit. | AUTH-003 | `security/sandbox_tokens.py`, `services/credentials.py` | Expired, revoked, wrong-scope, and exhausted credentials are rejected even with a stale cache. | `test_credentials.py` | L | ☐ |
| SANDBOX-002 | Demo API | A synthetic Orders API with independent credential validation. | SANDBOX-001 | `sandbox/demo_api.py`, `samples/` | Works with a valid token and returns 401 otherwise. | `test_demo_api.py` | M | ☐ |
| SANDBOX-003 | Runner adapter | `SandboxRunner` protocol and `DemoApiRunner` with plan validation, timeout, output cap, and sanitization. | SANDBOX-002, AI-004 | `sandbox/runner.py` | Timeouts and oversized outputs are handled. Traversal, host, and scheme plans are rejected. | `test_runner.py` | L | ☐ |
| SANDBOX-004 | Run API and audit | Run endpoint, `TestRun` persistence, and audit events. | SANDBOX-003 | `api/v1/runs.py` | The result reflects the actual call. | `test_runs.py` | M | ☐ |

## Phase 6 — Frontend

| ID | Title | Description | Depends | Files | Acceptance | Tests | Size | Status |
|----|-------|-------------|---------|-------|------------|-------|------|--------|
| UI-001 | Design system and shell | Dark theme tokens, shadcn components, responsive navigation, and auth pages. | INFRA-003 | `components/`, `app/` | Navigation works at mobile and desktop widths. | component tests | M | ☐ |
| UI-002 | API client and auth state | Typed client, TanStack Query, and error handling with request ids. | UI-001, AUTH-002 | `lib/api.ts` | 401 returns the user to login. | unit tests | M | ☐ |
| UI-003 | Vendor dashboard and projects | Project selector and creation, upload with status polling, endpoint overview, sessions and credentials, and member invites. | UI-002, DOCS-004 | `features/vendor` | Uploads reflect real server status. | component tests | L | ☐ |
| UI-004 | Developer workspace | Chat with references, Monaco editor, copy and export, credential issue, run, and results. | UI-002, AI-003, SANDBOX-004 | `features/workspace` | The UI never shows "executed" before a real run. | component tests | L | ☐ |

## Phase 7 — End-to-end

| ID | Title | Description | Depends | Files | Acceptance | Tests | Size | Status |
|----|-------|-------------|---------|-------|------------|-------|------|--------|
| E2E-001 | Backend workflow test | The full MVP flow through the API. | Phases 2–5 | `tests/test_e2e_workflow.py` | Steps 1–11 pass, including expired and unauthorized credentials. | pytest | M | ☐ |
| E2E-002 | Browser workflow | Playwright test of vendor and developer flows against a running stack. | Phase 6 | `apps/web/tests/e2e` | The flow passes, or the blocker is documented. | Playwright | L | ☐ |

## Phase 8 — Quality, security, documentation

| ID | Title | Description | Depends | Files | Acceptance | Tests | Size | Status |
|----|-------|-------------|---------|-------|------------|-------|------|--------|
| QA-001 | Full check sweep | Run all tests, lint, typecheck, migration checks, and secret and dependency audits. | all | n/a | Results recorded in DEVELOPMENT.md. Unavailable checks are listed. | all | M | ☐ |
| QA-002 | Final docs review | Update README, API, SECURITY, DEVELOPMENT, and known limitations. | QA-001 | `docs/`, `README.md` | Docs match behavior. | review | S | ☐ |

## Creating GitHub issues later

No issues are created automatically. To create them from this backlog with the GitHub CLI:

```bash
gh issue create --repo mertturkel234/coresync-ai --title "AUTH-001: Models and migrations" --body-file issue-body.md --label phase-2
```

One issue per task ID above is a sensible starting point.
