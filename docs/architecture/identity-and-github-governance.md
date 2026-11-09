# M5 — Authenticated identity and GitHub governance

## Purpose

M5 establishes a local authenticated identity boundary and a GitHub provider boundary. It does not claim that the current CLI is a hosted multi-user identity platform. The secure services are reusable application components; a future API server must authenticate every request and must not accept caller-supplied role strings.

## Identity model

- `agent_identities` stores identity ID, display name, role, type and active/disabled state.
- `agent_credentials` stores a credential ID, random salt, PBKDF2-HMAC-SHA256 hash, iteration count, expiry, last-use and revocation timestamps.
- Raw bearer tokens are shown once and are not stored in SQLite, logs or reports.
- `identity_events` records lifecycle and successful authentication events. SQLite triggers prevent update/delete of event rows.
- Creating an identity also creates a corresponding `resources` row so Scrum workload reporting can use the same stable identity ID.
- The first `identity_admin` is created through a one-time bootstrap command. Subsequent identities require `identity.manage`.

Bearer token format: `aisdlc.<credential-id>.<random-secret>`. The credential ID is a lookup key, not a secret. The secret portion is verified using constant-time hash comparison.

## Role-to-scope matrix

| Role | Main scopes |
|---|---|
| Business Analyst | requirements.read/write, requirements.ba_review |
| Product Owner | requirements.read, requirements.po_approve, product.accept |
| Architect | architecture.read/write, architecture.authorize |
| Architecture Reviewer | architecture.read/review, github.pr.review |
| Developer | development.start, developer.fix, code.write, github.branch.create, github.pr.create |
| QA Engineer | qa.execute, qa.defect.write, qa.retest, qa.test.write, github.branch.create, github.pr.create |
| QA Lead | qa.signoff/review, github.branch.create, github.pr.create/review/merge |
| Scrum Master | scrum.read, activity.read, github.read |
| Release Manager | release.authorize/deploy, github.pr.merge |
| Identity Admin | identity.manage, github.repository.register |

The identity administrator is a control-plane operator and is not one of the 12 delivery-team seats. Scope policy is code-owned; agents cannot grant themselves additional scopes.

## Workflow authentication

`AuthenticatedWorkflowGateway` validates the token, resolves identity and role from the database, checks the scope associated with the requested `Action`, and calls `WorkflowService` using the verified `identity_id` and `role`. The secure gateway does not accept role or actor ID input from the caller.

The legacy requirement and architecture CLI commands still expose local demonstration actor fields. They are not suitable as a production-facing API. A future API adapter must use the same `IdentityService` and enforce a principal before invoking these services. Feature transition CLI now uses authenticated environment tokens by default; the old actor flags are available only behind the explicitly named `--unsafe-local-demo` switch.

## GitHub provider boundary

- `GitHubProvider` defines the required operations.
- `MockGitHubAdapter` supports deterministic tests without internet or credentials.
- `GitHubCLIAdapter` delegates credentials to the official `gh` CLI; it never stores or prints GitHub tokens.
- `GitWorktreeManager` creates an isolated worktree per resource/branch using Git's worktree mechanism.
- `GitHubGovernanceService` enforces role scopes, safe branch prefixes, PR template sections, independent review and CI status before merge.
- The default branch (`main` or `master`) can be merged through the orchestration service only by a `release_manager`. GitHub branch protection remains the authoritative server-side control.

## Merge gate

A pull request is mergeable only when all of these are true:

1. It is not a draft.
2. GitHub reports the review decision as `APPROVED`.
3. GitHub reports merge state `CLEAN`.
4. At least one CI check exists.
5. Every reported check is `success`.
6. The requesting identity has `github.pr.merge`.
7. The PR author is not the reviewer for approval.
8. A merge into `main` or `master` is requested by a release manager.

GitHub branch protection must independently require the relevant status checks, code-owner review and conversation resolution. Client-side checks are defense in depth, not a replacement for server-side protection.

## Remaining security work

- Use an external identity provider/OIDC for production human accounts and agent workload identities.
- Put API endpoints behind TLS and short-lived signed access tokens; do not expose a local SQLite file to multiple untrusted workers.
- Use GitHub App installation tokens with repository-scoped permissions for production instead of personal access tokens.
- Store secrets in a secret manager, rotate credentials, rate-limit authentication, and add lockout/alerting for repeated failures.
- Pin GitHub Actions to verified commit SHAs and adopt dependency/supply-chain scanning before production.
- Add database backup/restore, multi-process concurrency and PostgreSQL deployment verification.


## Python-only implementation constraint

The integration and orchestration adapters are authored in Python. The GitHub CLI and Git executable are external tools invoked by Python subprocess wrappers; no JavaScript or TypeScript adapter, action, package or source file is permitted. The Python-only repository policy is enforced by `tests/test_python_only_policy.py`.
