# Beginner guide — identities, permissions and GitHub work

## 1. Why an identity is different from a role

A role says what kind of work a resource is allowed to do. An identity answers *which exact resource* is making the request. `DEV-01` and `DEV-02` can both have the `developer` role, but they remain separate identities in history and workload reporting.

Never trust a caller that sends `actor_id=DEV-01` and `role=developer` by itself. Those values can be typed by anyone. The authenticated workflow gateway instead validates a bearer token and looks up the identity and role in the database.

## 2. What is a token?

A token is a secret credential used to prove the caller is the identity that was registered. The orchestrator displays a token once. It stores only a salted password-style hash of the secret, not the original token. The token should be placed in an environment variable or a secret manager, never in source code, screenshots, chat, `.env` committed to Git, or a command-line argument.

## 3. First-time setup (Windows PowerShell)

```powershell
# Initialize / upgrade the local database.
python -m ai_sdlc --db data/demo.db init-db

# Create the first control-plane administrator. Copy the token from the output.
python -m ai_sdlc --db data/demo.db agent bootstrap-admin `
  --id ORCH-ADMIN --name "Orchestrator Administrator"

# Keep the copied token in this terminal session only.
$env:AI_SDLC_ADMIN_TOKEN = "aisdlc.<credential-id>.<secret>"

# Create one agent identity. Repeat with unique IDs and appropriate roles.
python -m ai_sdlc --db data/demo.db agent create `
  --id DEV-01 --name "Developer One" --role developer --capacity 8

# The command displays a new one-time token. Put it in the correct runtime secret store.
$env:AI_SDLC_AGENT_TOKEN = "aisdlc.<credential-id>.<secret>"

# Verify identity and scopes. This does not print the token.
python -m ai_sdlc --db data/demo.db auth verify --require-scope github.pr.create
```

The first administrator bootstrap is permitted only when the identity table is empty. After the first admin exists, another identity must be created by an authenticated `identity_admin`.

## 4. Use authenticated workflow transitions

The feature transition command reads `AI_SDLC_AGENT_TOKEN` by default. The actor ID and role come from the verified token—not command-line arguments.

```powershell
python -m ai_sdlc --db data/demo.db feature transition AUTH-001 submit_for_ba_review `
  --note "BA has completed the initial requirement review."
```

For isolated unit-test demonstrations only, older examples can use `--unsafe-local-demo` together with `--unsafe-local-demo-role` and `--unsafe-local-demo-actor-id`. Never use that escape hatch in a shared or deployed environment.

## 5. GitHub CLI setup

Install the GitHub CLI from the official GitHub documentation and authenticate interactively:

```powershell
gh auth login --hostname github.com
gh auth status --hostname github.com
```

Register a repository with an authenticated control-plane admin:

```powershell
python -m ai_sdlc --db data/demo.db github repo add --owner YOUR_ORG --name YOUR_REPO
```

`YOUR_ORG` and `YOUR_REPO` are placeholders. The repository must exist and the GitHub CLI identity must have the permissions required by the requested action.

Generate a branch name:

```powershell
python -m ai_sdlc --db data/demo.db github branch-name `
  --kind feature --work-id US-AUTH-001 --summary "Login page"
```

Create an isolated worktree from a local clone with an `origin` remote:

```powershell
python -m ai_sdlc --db data/demo.db github worktree add `
  --repository-id YOUR_ORG/YOUR_REPO `
  --repo-path C:\work\YOUR_REPO `
  --path C:\worktrees\DEV-01-AUTH-001 `
  --branch feature/US-AUTH-001-login-page
```

## 6. Pull request gates

The PR body file must contain these exact headings:

- `## Requirements`
- `## Acceptance criteria`
- `## Test evidence`
- `## Risk and rollback`

An independent reviewer must approve. Every reported CI check must be successful, and GitHub must report a clean merge state. The protected default branch requires a release-manager identity in the orchestration service. GitHub branch protection must still enforce the same controls server-side.

## 7. What not to do

- Do not commit any token or put it in the repository `.env` file.
- Do not use an administrator token as a developer or QA token.
- Do not let an author approve their own PR.
- Do not merge when checks are pending, failed, skipped or missing.
- Do not use the mock provider as proof that a real GitHub operation succeeded.
- Do not claim production identity security until an API gateway, external identity provider, TLS, secret management and GitHub App installation permissions are configured.


## 6. Python-only implementation choice

All source code and automation are Python. The target application UI will use Streamlit, the HTTP API will use FastAPI, and browser automation will use Playwright for Python through pytest. There are no JavaScript or TypeScript source files or Node package manifests in this repository. The official GitHub CLI and Git CLI may be invoked by Python adapters as external developer tools; their use does not introduce JavaScript or TypeScript source into the project.
