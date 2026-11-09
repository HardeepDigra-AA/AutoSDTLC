# AI SDLC Orchestrator

A governed, reusable, **Python-only** framework for coordinating business analysis, product ownership,
solution architecture, software development, quality engineering, and release management.

> **Current status:** M0–M5 local foundation implemented. The repository includes deterministic
> feature and requirements workflows, SQLite persistence, resource/task tracking, versioned BRDs,
> clarification handling, BA/PO gates, AC-to-test traceability, and versioned solution-architecture
> packages with mandatory technical-design, database, API, security, coding-standard, test-first,
> test-strategy and deployment/rollback artifacts. Architecture approval requires an independent
> reviewer and is enforced before development. M5 adds local credential-backed identities, scoped
> authorization, authenticated feature transitions, GitHub provider adapters, branch/PR governance,
> and isolated Git worktrees. It does not yet run independent LLM agents or execute real Playwright/RAG evaluations.

## Design principles

1. **Requirements before implementation.** A feature cannot enter development until BA, PO, and
   architecture approvals have been recorded.
2. **Deterministic gates around probabilistic agents.** LLMs may draft work products, but a
   workflow engine enforces permissions, approvals, required evidence, and state transitions.
3. **Traceability.** Requirements, acceptance criteria, test cases, defects, PRs, and releases
   receive stable identifiers and linked evidence references.
4. **Human approval for consequential actions.** Protected-branch merges and production releases
   require explicit authorization.
5. **Evidence-based reporting.** Status and performance reports are derived from actual work items,
   assignments, workflow events, CI, PRs, and test runs—not invented estimates or agent claims.
6. **Least privilege and isolation.** Agents receive scoped tasks, repository permissions, and file
   ownership; parallel work uses isolated branches/worktrees.

## Repository map

```text
ai-sdlc-orchestrator/
├── .github/                     # PR template, CI workflow, code owners
├── config/                      # Example target-project and team configuration
├── migrations/                  # Versioned additive SQL migrations
├── docs/
│   ├── architecture/            # System design, data model, implementation roadmap
│   ├── learning/                # Step-by-step beginner guides
│   └── standards/               # Engineering and QA policies
├── examples/                    # Runnable domain workflow demonstration
├── src/ai_sdlc/
│   ├── domain/                  # Deterministic workflow, requirement and architecture rules
│   ├── infrastructure/          # SQLite repository adapter
│   ├── services/                # Workflow, requirements and architecture services
│   └── cli.py                   # Command-line interface
├── templates/                   # BRD, story, criteria, test and architecture templates
│   └── architecture/            # Ten design sections and ADR template
├── tests/                       # Workflow, persistence, and CLI automated tests
├── reports/                     # Generated local test reports (not committed)
├── scripts/                     # Python setup and test-runner helpers
├── AGENTS.md                    # Rules for AI and human contributors
└── pyproject.toml               # Python package and tool configuration
```

## Quick start (Windows)

Requirements: Python 3.11 or newer.

```powershell
# 1. Open this folder in VS Code and open Terminal > New Terminal.

# 2. Create a virtual environment and install the project plus development tools.
python scripts/bootstrap_environment.py

# 3. Run all automated tests.
python scripts/run_tests.py

# 4. Initialize a local database.
python -m ai_sdlc --db data/demo.db init-db

# 5. Run the CLI help.
python -m ai_sdlc --help
```

The setup helper is Python and invokes the virtual environment interpreter directly; activation is not required. To install the optional Python web stack, use `python -m pip install -e ".[web]"`. To install Python browser-test tools, use `python -m pip install -e ".[qa]"`; RAG evaluation dependencies are available through `python -m pip install -e ".[rag]"`.

## Quick start (macOS/Linux)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -v
python -m ai_sdlc --db data/demo.db init-db
```

## First local CLI walkthrough

```powershell
# Create a feature request and acceptance criteria.
python -m ai_sdlc --db data/demo.db feature create `
  --id AUTH-001 `
  --title "User login" `
  --problem "Registered users need to sign in securely." `
  --ac "Valid credentials allow access." `
  --ac "Invalid credentials are rejected."

# Inspect feature state and its audit history.
python -m ai_sdlc --db data/demo.db feature show AUTH-001

# Move it to BA review. The engine validates that the action is allowed.
python -m ai_sdlc --db data/demo.db feature transition AUTH-001 submit_for_ba_review `
  --unsafe-local-demo --unsafe-local-demo-role business_analyst `
  --unsafe-local-demo-actor-id BA-01 --note "Requirements submitted for review."

# Review current feature list and Scrum summary.
python -m ai_sdlc --db data/demo.db feature list
python -m ai_sdlc --db data/demo.db scrum summary
```

All authored application and automation code is Python. The planned business application UI uses Streamlit, the HTTP API uses FastAPI, and browser automation uses Playwright for Python with pytest. JavaScript, TypeScript, React, Node.js and npm are prohibited. See [the Python-only development standard](docs/standards/python-only-development.md).

The `--db` option is placed before the command. It can also be set through `AI_SDLC_DB_PATH`.
See [the persistence and CLI learning guide](docs/learning/persistence-and-cli.md) for the complete
resource/task walkthrough and more commands. See [the Python-only stack guide](docs/learning/python-only-stack.md) for the approved UI, API, browser automation and RAG libraries.

## M3 requirement lifecycle walkthrough

The requirements module gives BA, PO, and QA a governed preparation process before a feature moves
into architecture and development. The local command-line actor/role arguments are demonstration
inputs only; they are not authentication.

```powershell
# 1. Capture the business need (a requester starts the record).
python -m ai_sdlc --db data/demo.db requirement create `
  --id REQ-AUTH-001 `
  --title "Secure user login" `
  --description "Registered users must sign in using valid credentials." `
  --business-value "Protect user data and provide authenticated access." `
  --priority high `
  --created-by REQUESTER-01

# 2. BA creates a user story and stable acceptance-criteria IDs.
python -m ai_sdlc --db data/demo.db requirement story `
  --id US-AUTH-001 --requirement REQ-AUTH-001 `
  --title "Sign in with credentials" --as-a "registered user" `
  --i-want "to sign in with my email and password" `
  --so-that "I can securely access my account" --created-by BA-01

python -m ai_sdlc --db data/demo.db requirement criterion `
  --id AC-AUTH-001 --story US-AUTH-001 `
  --description "Valid credentials authenticate the user." --created-by BA-01

# 3. BA submits and approves; the item moves to Product Owner review.
python -m ai_sdlc --db data/demo.db requirement submit-ba REQ-AUTH-001 `
  --actor-id BA-01 --note "Requirement, story and criteria reviewed."
python -m ai_sdlc --db data/demo.db requirement approve-ba REQ-AUTH-001 `
  --actor-id BA-01 --note "BA review complete."

# 4. QA authors test cases and maps each test to the AC it verifies.
python -m ai_sdlc --db data/demo.db requirement test-case `
  --id TC-AUTH-001 --title "Valid credentials succeed" `
  --description "Submit an active user's valid credentials." `
  --level api --created-by QA-02
python -m ai_sdlc --db data/demo.db requirement map-test `
  --criterion AC-AUTH-001 --test-case TC-AUTH-001 --mapped-by QA-02

# 5. PO approval is blocked until every AC has at least one mapped test case.
python -m ai_sdlc --db data/demo.db requirement approve-po REQ-AUTH-001 `
  --actor-id PO-01 --note "Scope and traceability accepted."

# 6. Inspect the traceability matrix or print a Markdown BRD.
python -m ai_sdlc --db data/demo.db requirement show REQ-AUTH-001
python -m ai_sdlc --db data/demo.db requirement brd REQ-AUTH-001
```

For clarification handling, use `requirement clarification add` and `requirement clarification answer`.
BA submission is blocked while any question is still open. For requirement changes, use
`requirement update` with a change note and (recommended) `--expected-version` to prevent stale writes.
See [the requirements and traceability tutorial](docs/learning/requirements-and-traceability.md).

## M4 solution architecture and technical-design gate

M4 introduces a persisted architecture package. A feature must be in `architecture_review`, and
its linked business requirement must be PO-approved. The architect then creates a package and
supplies ten mandatory artifacts: solution overview, component design, Technical Design Document,
database design, API contracts, security threat model, coding standards, test-driven development
plan, test strategy and deployment/rollback plan. At least one ADR and mappings for every linked user
story are also required.

An independent `architecture_reviewer` must approve the submitted package; its author cannot approve
it. A new approved package supersedes the previous approved version. The architect then records the
exact package ID as evidence in the feature workflow. The application service blocks architecture
approval without an approved package and blocks developer start if the recorded package does not
match the current approved design.

```powershell
# Create the package after the feature enters architecture_review and the requirement is PO approved.
python -m ai_sdlc --db data/demo.db architecture create `
  --id ARCH-AUTH-001 --feature AUTH-001 --requirement REQ-AUTH-001 `
  --created-by ARCH-01

# Import each architecture section from a Markdown file.
python -m ai_sdlc --db data/demo.db architecture artifact `
  --package ARCH-AUTH-001 --type technical_design `
  --title "Login Technical Design" --file docs/design/login-technical-design.md `
  --created-by ARCH-01

# Record an ADR and map every story in the linked requirement.
python -m ai_sdlc --db data/demo.db architecture adr `
  --id ADR-AUTH-001 --package ARCH-AUTH-001 --title "Use PostgreSQL" `
  --context "Login transactions need reliable persistence." `
  --decision "Use PostgreSQL for identity and session data." `
  --consequences "Reviewed migrations, backups and least-privilege roles are required." `
  --created-by ARCH-01
python -m ai_sdlc --db data/demo.db architecture map-story `
  --package ARCH-AUTH-001 --story US-AUTH-001 --mapped-by ARCH-01

# Check completeness, submit, and obtain a four-eyes review.
python -m ai_sdlc --db data/demo.db architecture checklist ARCH-AUTH-001
python -m ai_sdlc --db data/demo.db architecture submit ARCH-AUTH-001 `
  --actor-id ARCH-01 --note "All required design evidence is complete."
python -m ai_sdlc --db data/demo.db architecture review ARCH-AUTH-001 `
  --outcome approved --reviewer-id ARCH-REVIEWER-01 `
  --note "Independent design review passed." --evidence reviews/ARCH-AUTH-001.md

# Record the exact approved package before developer work starts.
python -m ai_sdlc --db data/demo.db feature transition AUTH-001 approve_architecture `
  --unsafe-local-demo --unsafe-local-demo-role architect `
  --unsafe-local-demo-actor-id ARCH-01 --note "Architecture approved." `
  --evidence ARCH-AUTH-001
python -m ai_sdlc --db data/demo.db feature transition AUTH-001 start_development `
  --unsafe-local-demo --unsafe-local-demo-role developer `
  --unsafe-local-demo-actor-id DEV-01 --note "Start against approved design."
```

For all ten artifact keys, rationale for N/A sections, ADR guidance and the complete beginner
walkthrough, see [the M4 architecture/TDD guide](docs/learning/solution-architecture-tdd.md) and
[the architecture gate specification](docs/architecture/solution-architecture-and-tdd-gate.md).


## M5 authenticated identities and GitHub governance

M5 adds a one-time control-plane bootstrap, identity-scoped API credentials, role-to-scope
authorization, an authenticated workflow gateway, a GitHub CLI provider, a deterministic mock
provider, Git branch policy, isolated worktrees, PR traceability and merge gates.

```powershell
# Bootstrap the first admin only on a fresh identity database. Copy the one-time token.
python -m ai_sdlc --db data/demo.db agent bootstrap-admin `
  --id ORCH-ADMIN --name "Orchestrator Administrator"

# Save the copied token only in the current terminal session or your secret manager.
$env:AI_SDLC_ADMIN_TOKEN = "aisdlc.<credential-id>.<secret>"

# Register each team member with an independent identity and role.
python -m ai_sdlc --db data/demo.db agent create `
  --id DEV-01 --name "Developer One" --role developer --capacity 8

# Copy the developer's one-time token into that worker's secret store.
$env:AI_SDLC_AGENT_TOKEN = "aisdlc.<credential-id>.<secret>"
python -m ai_sdlc --db data/demo.db auth verify --require-scope github.pr.create

# Secure workflow transitions now derive actor and role from the token.
python -m ai_sdlc --db data/demo.db feature transition AUTH-001 start_development `
  --note "Start work against the currently approved design package."

# Connect GitHub CLI and register the repository (replace placeholders).
gh auth login --hostname github.com
python -m ai_sdlc --db data/demo.db github repo add --owner YOUR_ORG --name YOUR_REPO

# Generate a policy-compliant branch name.
python -m ai_sdlc --db data/demo.db github branch-name `
  --kind feature --work-id US-AUTH-001 --summary "Login page"
```

Feature transition no longer accepts caller-supplied roles by default. The legacy identity
arguments are available only with the explicit `--unsafe-local-demo` option for isolated tests.
The earlier requirement and architecture CLI shortcuts still operate as local demonstration
interfaces; a deployed API must validate a principal before invoking those service methods.

The GitHub CLI adapter uses the official `gh` authentication store and does not read or persist
GitHub tokens itself. The mock adapter is for tests only. A PR requires requirement IDs, acceptance
criteria, test evidence and rollback notes. Merge is blocked unless GitHub reports an approved
review, clean merge state and at least one CI check with every check successful. The author cannot
review their own PR. Direct merge to `main`/`master` requires a release-manager identity.

**Before using a real target repository:** replace sample CODEOWNERS team handles, enable GitHub
branch protection for `main` and `develop`, require the `tests` CI check, require code-owner review,
require conversation resolution, and disallow force pushes and direct pushes. GitHub's server-side
branch protection is authoritative; orchestrator checks are defense in depth.

See [the identity and GitHub architecture](docs/architecture/identity-and-github-governance.md)
and [the beginner identity/GitHub guide](docs/learning/identity-and-github.md).

## Implemented workflow behavior

The workflow engine accepts an action only when:

- the action is valid for the current workflow state;
- the actor has the required role;
- required feature information is present;
- an audit note is supplied; and
- required evidence is attached for design approval, QA, PR, sign-off, and release actions.

M2 stores accepted transitions and their evidence references in SQLite. Each transition is saved
atomically with an optimistic state/version check so an old workflow snapshot cannot overwrite a
newer state. Task creation, assignment, and status changes are also recorded in a task activity log.

## Important prototype limitations

- The local identity service demonstrates credential authentication and RBAC; it is not enterprise SSO or a hosted multi-user identity platform.
- Evidence is stored as a reference; the framework does not yet verify artifact existence,
  permissions, integrity, or expiry.
- SQLite is for local development. Shared deployment requires authenticated identity, a PostgreSQL
  adapter, proper migrations, backups, access control, and operational monitoring.
- Task/resource metrics are counts from local records. Accurate cycle times and agent performance
  require measured start/end events and connected PR/CI/test telemetry.
- No LLM agent can independently change code or deploy at this stage. The GitHub provider is available but has not been connected to your remote repository.
- Role arguments on local requirement commands are demonstration gates, not verified identities.
- Requirement-to-test links prove planned coverage, not that the tests have executed or passed.
- Requirement approval does not automatically approve the separate solution architecture or feature workflow.
- Architecture completeness checks verify artifact presence and basic placeholder rules, not whether the design is technically correct; an independent reviewer must assess design quality.
- The architecture reviewer ID is a CLI-supplied demonstration value. It is not authenticated and must be replaced by server-side identity and RBAC before shared use.

Do not connect this prototype directly to a production repository or release environment.

## Initialize local Git history (first time only)

```powershell
git init -b main
git status
git add .
git commit -m "chore: bootstrap AI SDLC orchestrator"
```

The GitHub provider is implemented but no remote repository has been connected in this starter
package; remote side effects remain opt-in and require a separately authenticated GitHub CLI session. See the standards baseline in [the standards reference](docs/standards/standards-reference.md).

### M5 security boundary

The local identity service demonstrates authentication and RBAC, not enterprise SSO. Production
use still requires an authenticated API gateway, external identity provider/OIDC, TLS, secret
management, GitHub App installation tokens, rate limiting, backups and server-side branch protection.
Do not expose the SQLite database to untrusted agents. The identity administrator is a control-plane
operator and is separate from the 12 delivery-team resources.


## Python-only implementation policy

All authored application, orchestration, integration, UI and test code is Python. The planned UI uses Streamlit, the HTTP API uses FastAPI, and browser automation uses Playwright for Python with pytest. No JavaScript/TypeScript source or Node package manifests are allowed; CI enforces this rule.
