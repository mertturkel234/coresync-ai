# CoreSync AI — Security

Security is a product requirement. This document states the controls that are **implemented**, those that are **planned**, and the known **limitations**. Anything not listed as implemented should be treated as not implemented. This is an MVP. Passing its tests does not make it production-ready.

## 1. Assets and trust boundaries

| Asset | Threat | Control |
|-------|--------|---------|
| Tenant data (projects, docs, sessions, runs) | Cross-tenant access | Tenant-scoped repositories, membership checks on every route, and negative tests. |
| User passwords | Theft or brute force | Argon2id hashing, generic login errors, rate limiting on login and register. |
| Access tokens | Theft or forgery | Short TTL, HS256 with a server-side secret that is required in production, and validation of `exp`, `iss`, and `sub`. |
| Sandbox credentials | Leak, replay, over-use | High entropy, hash-only storage, scope, TTL, revocation, quota, rate limit, and never logged. |
| Production API credentials | Exposure to browser or LLM | **Never** accepted or stored by the MVP. Only synthetic demo credentials exist. |
| Server host | Remote code execution | No execution of arbitrary code. The request-plan runner has an allowlist and no egress. |
| LLM context | Prompt injection | Documents are untrusted. The LLM has no tools. Tool arguments are server-derived. |

Untrusted inputs: uploaded documents, retrieved passages, user chat text, LLM output, and demo API response bodies.

## 2. Authentication and authorization

- Email and password registration and login. Passwords require at least 10 characters. Argon2id is used (`argon2-cffi` defaults).
- JWT access tokens are validated on every protected route. Inactive users are rejected.
- Roles per tenant: `owner`, `member`, `developer`.
  - Vendor actions (project and document management, inviting developers, revoking credentials, audit view) require `owner` or `member`.
  - `developer` can only use sessions they own, on projects in tenants they belong to.
- Cross-tenant access returns **404**, not 403, so resource existence is not leaked.
- Authorization is enforced in services and repositories, never only in the UI.

## 3. Sandbox credentials

- Format: `csk_<public_id>_<secret>`. The secret is `secrets.token_urlsafe(32)`, which gives 256 bits from the OS CSPRNG.
- Only `sha256(token)` and a non-secret prefix (`csk_<public_id>`) are stored. The raw token is shown **once** at issue.
- Scoped to `tenant_id`, `project_id`, and `environment="demo"`. A credential cannot be used for another project or tenant.
- The default TTL is 30 minutes and the maximum is 24 hours. `expires_at` and `revoked_at` are checked **in the database row on every use**. No cache can extend validity.
- Quota: `max_requests` per credential, enforced with an atomic conditional `UPDATE`. Rate limit: fixed window per credential through the `RateLimiter`.
- Token comparison uses a constant-time compare on the hash.
- Rejected uses (unknown, expired, revoked, scope mismatch, quota exhausted) produce an audit event that contains the credential's public id and never the raw token.
- Redis is used for rate limiting only. It is **not** an authorization store.
- A temporary key does not by itself make an integration secure. It limits blast radius and lifetime.

## 4. Test execution (read this)

**The MVP does not execute arbitrary or LLM-generated Python.** Isolation (ephemeral containers, resource limits, restricted filesystem, network egress policy) cannot be implemented and verified in the current development environment, because Docker is unavailable. The product therefore ships a **demo-only** path:

- The runner receives a server-stored `RequestPlan` (method, path, query, JSON body), not code. Plans come from deterministic generation. Edits made in the code editor are **not** executed. The UI states this.
- The plan is re-validated on execution:
  - the method must be in an allowlist,
  - the path must be under the demo API prefix and contain no `..`, scheme, or host,
  - the body is limited in size.
- The request is dispatched through an in-process ASGI transport to the demo API. There is **no network egress**, so SSRF to arbitrary hosts is not possible by construction.
- Timeout (`SANDBOX_TIMEOUT_SECONDS`) and response-size cap (`SANDBOX_MAX_OUTPUT_BYTES`) apply. Output is sanitized: bearer tokens, `csk_` tokens, and common secret patterns are redacted, and bodies are truncated.
- The demo API holds synthetic data only. It has no connection to the database tables of real tenants and no production secrets.

**Future container runner:** must provide a non-root user, a read-only root filesystem, no network or egress allowlisting, CPU, memory, pids, and time limits, a clean environment without inherited secrets, and teardown after each run. Until it is verified, free-form execution stays disabled.

## 5. Document and prompt injection

- Uploaded text never reaches a system prompt. It is placed in a delimited, labelled data block that tells the model to treat it as untrusted reference material.
- The LLM interface exposes **no tools** that can cause side effects. Code generation and plan building are deterministic server code.
- Retrieval is filtered by `tenant_id` and `project_id` in the SQL query, so another tenant's documents cannot enter the context.
- Answers cite the chunk refs they were built from. Citations are produced by the retriever, not parsed from model text, so a model cannot fabricate a reference.
- If evidence is insufficient the system says so and generates no code.
- YAML is loaded with `safe_load` only, and documents that use anchors or aliases are rejected to prevent expansion attacks. Size limits apply to the raw upload and to the number of endpoints.
- External `$ref`s are rejected (no SSRF). Only local `#/` references are resolved, with a depth limit.
- Limitation: a prompt-injection string in an uploaded document can still influence the **wording** of an LLM answer. It cannot trigger actions or reveal other tenants' data. Offline mode is extractive and does not interpret instructions.

## 6. Input validation and web security

- All request bodies use Pydantic with strict length limits.
- Uploads: extension and content-type allowlist, a size cap (`MAX_UPLOAD_BYTES`, default 2 MiB), UTF-8 validation, and content sniffing (JSON/YAML/Markdown must parse). The stored file name is random. The user-supplied name is stored only as sanitized display metadata.
- Database access uses SQLAlchemy, so queries are parameterized. No raw string SQL with user input.
- CORS uses an explicit origin allowlist (`CORS_ORIGINS`). There is no wildcard with credentials.
- Security headers on API responses: `X-Content-Type-Options`, `Referrer-Policy`, `Cache-Control: no-store` on authenticated JSON. The web app sets a CSP and frame protections.
- Error handling is centralized. Unhandled exceptions return a generic message with a `request_id`. Stack traces are logged server-side only, with secrets scrubbed.
- Rate limits: login, register, ask (AI), credential issue, and run endpoints.

## 7. Audit and logging

Audit events record actions such as `auth.register`, `auth.login`, `auth.login_failed`, `project.create`, `document.upload`, `document.processed`, `document.failed`, `session.create`, `credential.issue`, `credential.revoke`, `credential.rejected`, `test.run`, and `member.add`. Metadata passes through a scrubber that drops keys such as `password`, `token`, `secret`, and `authorization`, and redacts `csk_` patterns. Request and response bodies are not logged.

## 8. Secrets management

- Secrets come from environment variables. `.env` is gitignored and `.env.example` contains placeholders only.
- In `ENVIRONMENT=production` the API refuses to start with a missing or placeholder `JWT_SECRET` or `DATABASE_URL` default credentials. In development a random per-process secret is generated when none is set.
- `LLM_API_KEY` is read server-side and is never sent to the browser or into prompts.
- Docker Compose default credentials and PgAdmin are for **local development only**. PgAdmin is behind a compose profile and bound to localhost.

## 9. Known limitations and unresolved risks

- No arbitrary code execution (by design, see section 4).
- No email verification, password reset, MFA, or account lockout beyond rate limiting.
- The JWT lives in `sessionStorage`. XSS would expose it. There is no token revocation list, only a short TTL.
- The in-memory rate limiter is per process. Use Redis for multi-instance deployments.
- No dependency vulnerability scanning in CI yet. Planned: `pip-audit` and `npm audit` (run manually, see DEVELOPMENT.md).
- Real PostgreSQL, Redis, and Docker paths are not verified on the author's machine. See DEVELOPMENT.md for what has been checked.
- The in-process demo API shares the API process, which is acceptable only because it serves synthetic data and is not user-programmable.
