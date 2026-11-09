# M5 Implementation Report — Python-only Orchestrator v0.5.0

## Status

**M5 implemented locally.** The repository now contains credential-backed agent identities, role/scope authorization, an authenticated feature-workflow gateway, GitHub provider interfaces, branch and worktree policies, PR review controls, CI merge gates, and an enforced Python-only implementation standard.

## Python-only decision

All authored application, orchestration, integration, UI, setup-helper and QA automation implementation is Python. No JavaScript/TypeScript source, Node package manifest, PowerShell setup script, shell helper or batch helper is included.

The planned user interface is Streamlit (Python), the API is FastAPI (Python), unit/API tests use pytest, browser automation uses Playwright for Python, and RAG evaluation will use Python packages such as DeepEval/RAGAS. YAML/TOML configuration, Markdown documentation and SQL DDL migration declarations remain declarative assets rather than application implementation code.

The repository contains automated policy tests at `tests/test_python_only_policy.py`. CI runs them as a named quality gate. The tests reject forbidden source/script extensions and Node package manifests, require executable project folders to contain Python files only, and check that the sample application configuration selects Streamlit, FastAPI and Playwright for Python.

## M5 capabilities

- One-time control-plane administrator bootstrap.
- Individual human, agent and service identities associated with Scrum resource records.
- Opaque credentials with random secrets, salted PBKDF2-HMAC-SHA256 hashes, expiry, revocation and rotation.
- Identity disablement/reactivation and append-only identity audit events.
- Explicit role-to-scope permissions and authenticated feature transition gateway; actor and role are derived from verified credentials.
- GitHub provider protocol with deterministic mock provider and official GitHub CLI adapter.
- Safe branch naming, isolated Git worktree creation/removal, traceable PR templates, independent review and CI merge gates.
- Protected default-branch merge restricted to a release-manager principal.
- Python setup and test helpers: `scripts/bootstrap_environment.py` and `scripts/run_tests.py`.
- Python-only development policy and CI enforcement.

## Defects found and fixed during verification

1. The Python migration constant did not create `control_plane_bootstrap`, although the external SQL migration definition included it. The executable Python migration now creates the table.
2. The first-admin bootstrap service returned the identity ID in the credential-ID field. It now returns the actual credential ID; the hashed credential can be retrieved and revoked/rotated correctly.
3. Two migration-upgrade tests attempted to drop `control_plane_bootstrap` twice. The duplicate drops were removed so the tests represent a valid prior schema.
4. Previous Playwright automation references used TypeScript spec filenames. They now use Python pytest module paths such as `tests/api/test_login.py`.
5. Windows setup/test helpers were PowerShell. They have been replaced with Python scripts and the old non-Python helper files were removed.
6. Example target configuration now selects a Python-only stack: Streamlit, FastAPI, pytest, Playwright for Python and Python RAG evaluation packages.

## Verification results

- Automated suite: **98 passed, 0 failed, 0 skipped**.
- Python compilation: passed (`compileall` over `src`, `tests`, `examples` and `scripts`).
- CLI version/help and database initialization smoke tests: passed.
- Python-only policy: passed; no forbidden source extensions or package manifests were found.
- Package build: wheel build completed successfully.
- Ruff: **not run** because Ruff is not installed in the execution environment and package-index access was unavailable during this run.

JUnit output: `reports/m5-test-results.xml`.

## Security and integration boundaries

- GitHub provider behavior is tested using the mock provider and local Git repositories. The live GitHub CLI provider is implemented but no user GitHub account or remote repository was connected during this run.
- External OIDC/SSO, TLS-terminated hosted API, managed secret storage, GitHub App installation tokens, production PostgreSQL operations, backups and server-side branch protection remain production-hardening work.
- Requirement and architecture command paths still include local demonstration actor fields; production endpoints must require the authenticated principal in the same way as the feature workflow gateway.
- Independent LLM agents, the Streamlit administration UI, the sample business application, actual Playwright execution and RAG evaluation are not yet implemented. The Python dependency groups and architecture configuration establish the approved stack for those milestones.
- A green test suite demonstrates the tested behavior only. It is not proof that the application is bug-free or that an external GitHub deployment occurred.
