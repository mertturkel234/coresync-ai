# CoreSync AI — Product Requirements Document

**Tagline:** Autonomous Intelligence for B2B Integration.
**Status:** MVP in development. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for task status.

## 1. Problem statement

Technical integration is the slowest stage of many B2B SaaS sales cycles. A customer's developers must read API documentation, pick endpoints and an authentication method, write code, test it, and diagnose errors. Today this depends on the vendor's solutions engineers, so it is slow, expensive, and hard to repeat.

## 2. Product vision

CoreSync AI guides a customer developer from reading an API to a **verified** integration result:

1. Understand the API.
2. Select the right endpoint and authentication method.
3. Generate a relevant integration example.
4. Test it in a controlled environment.
5. Inspect the actual responses and diagnose errors.
6. Receive a reproducible result and implementation instructions.

It is not a documentation chatbot. The product **always distinguishes generated suggestions from verified execution results**. Code that was only generated is labelled "Not executed". A result is shown only after a test actually ran.

## 3. Target users and roles

| Role | Description | MVP capabilities |
|------|-------------|------------------|
| **Vendor** (tenant `owner` / `member`) | Company that owns an API and wants faster onboarding of technical customers. | Create projects, upload docs, inspect processing, review developer sessions and sandbox credentials, invite developers, view audit events. |
| **Developer** (tenant `developer`) | Technical customer integrating a vendor's API. | Open sessions on authorized projects, ask grounded questions, generate Python examples, issue short-lived sandbox credentials, run approved tests, export examples. |
| **Administrator** | Future platform operator. | **Out of MVP scope.** The data model leaves room for it. |

## 4. Scope

### In scope (MVP)
- Email and password accounts with JWT bearer authentication.
- Tenants, memberships, and roles.
- Projects, documentation ingestion (OpenAPI JSON/YAML, Markdown), endpoint extraction, and a retrieval index.
- Provider-agnostic AI layer: an offline/demo provider that is always available and an OpenAI-compatible provider that is configured server-side.
- Python code generation from indexed endpoints.
- Scoped, expiring, revocable sandbox credentials with quotas and rate limits.
- A controlled **demo API** with synthetic data and a restricted, demo-only test runner behind an adapter interface.
- Vendor dashboard, project/document management, and developer workspace UI.
- Audit log.

### Out of scope (MVP)
- Arbitrary execution of LLM-generated or user-edited code (see [SECURITY.md](SECURITY.md)).
- Connecting to real customer APIs or production credentials.
- SSO/OIDC, billing, an admin console, and email delivery.
- Semantic (embedding) retrieval. The MVP uses lexical retrieval behind an interface; pgvector is a planned extension.
- Multi-language code generation. Python only.

## 5. Functional requirements

| ID | Requirement | Summary |
|----|-------------|---------|
| FR-01 | Project management | Create, list, update, and archive projects inside a tenant boundary. |
| FR-02 | Documentation ingestion | Accept OpenAPI 3.x JSON/YAML and Markdown. Validate type, size, content, and structure before processing. |
| FR-03 | Documentation indexing | Extract endpoints, methods, parameters, request/response schemas, security requirements, descriptions, and error responses. |
| FR-04 | Grounded AI | Answer from retrieved docs, show endpoint/document references, and say so when docs are insufficient. |
| FR-05 | Code generation | Generate Python examples with error handling and secret placeholders. |
| FR-06 | Controlled testing | Run approved examples against the demo API through a restricted runner and return the real status, HTTP response, and sanitized diagnostics. |
| FR-07 | Sandbox credentials | Scoped, expiring, revocable credentials validated server-side, with quotas and rate limits. |
| FR-08 | Developer workspace | Chat, code editor, run, and results in one UI. |
| FR-09 | Vendor dashboard | Documents, project status, sandbox sessions, and summaries backed by real data. |
| FR-10 | Auditability | Record security-sensitive actions without raw secrets. |
| FR-11 | Failure handling | Useful errors with request IDs and recoverable states. |
| FR-12 | Tenant isolation | No cross-tenant access to any resource. |

## 6. Non-functional requirements

- **Security first:** see [SECURITY.md](SECURITY.md). No secrets in the repository. All authorization is enforced server-side.
- **Reliability:** AI-provider failures must not crash the API. Errors are structured with a `request_id`.
- **Performance targets (MVP):** ingestion of a 2 MB OpenAPI file in under 5 s. Retrieval p95 under 200 ms for a project with 1,000 chunks. These are targets and are not yet measured.
- **Maintainability:** modular monolith with layered backend (API, services, repositories, models). Strict TypeScript. Ruff-clean Python.
- **Accessibility and UI:** strictly dark theme, responsive layouts, visible focus states, and loading/empty/error/success states.
- **Testability:** deterministic offline AI mode for tests. Negative security tests are required.

## 7. Data entities

`User`, `Tenant`, `Membership(role)`, `Project`, `Document` (with version and status), `Endpoint`, `DocChunk`, `IntegrationSession`, `Message`, `CodeExample`, `SandboxCredential` (hash only), `TestRun`, `AuditEvent`. Details are in [ARCHITECTURE.md](ARCHITECTURE.md).

## 8. MVP acceptance criteria

The MVP is accepted when the following is demonstrated end to end and covered by automated tests where practical:

1. A vendor registers and creates a project.
2. The vendor uploads a valid OpenAPI document.
3. The backend validates and parses it. Invalid documents are rejected with useful errors.
4. A developer, invited by the vendor, asks about an endpoint.
5. The AI returns a grounded answer with references and a Python example. Offline mode is labelled as such.
6. The developer issues a sandbox credential and runs the approved example against the demo API.
7. The UI shows the actual execution result.
8. The developer can inspect, copy, and export the example.
9. Expired, revoked, and cross-tenant credentials are rejected.
10. Automated tests cover the main workflow and critical authorization boundaries.

## 9. Risks

| Risk | Mitigation |
|------|------------|
| Prompt injection via uploaded documents | Docs are treated as untrusted data. The LLM has no tools with side effects. Tool arguments are derived and validated server-side. |
| Unsafe code execution | No arbitrary code execution. A demo-only request-plan runner is in the MVP. |
| LLM hallucination | Grounded answers with references. Refusal when evidence is missing. Generated code is based on indexed endpoints only. |
| Tenant data leakage | Every query is tenant-scoped. Negative tests are required. |
| Infrastructure unavailable locally (Docker, PostgreSQL, Redis) | Tests run on SQLite and in-memory Redis. Real-service checks are documented as separate verification steps. |

## 10. Success metrics (to be measured after launch, not claimed now)

- Time from project creation to first verified integration run.
- Share of developer sessions that reach a passing test run.
- Share of answers with at least one document reference.
- Ingestion failure rate and median processing time.
