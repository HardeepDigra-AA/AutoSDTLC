# Implementation plan

## Guiding strategy

Build and validate one vertical slice at a time. The orchestrator itself must be tested like a
production application. The login application will be the first target project only after the
framework can reliably govern a feature lifecycle, persist evidence, and enforce agent permissions.

## Milestones

| Milestone | Deliverable | Status / exit criteria |
|---|---|---|
| M0 — Bootstrap | Repository structure, standards, tests, local setup | **Implemented** — project structure and starter tests exist |
| M1 — Workflow core | Role-aware feature state machine and audit events | **Implemented** — invalid actions, unauthorized roles, missing requirements/evidence rejected |
| M2 — Persistence + CLI | SQLite feature/workflow storage, resources, work items, assignments, activity, CLI | **Implemented locally** — data survives restart; optimistic transitions and task audit history tested |
| M3 — Requirement lifecycle | BRD/story/AC templates, BA and PO review gates, clarification log | **Implemented locally** — versioned requirements, clarifications, stories, AC IDs, QA test mappings and PO traceability gate |
| M4 — Architecture gate | Versioned design package, TDD, data model, API, security and coding checklists | **Implemented locally** — ten mandatory artifacts, ADR, story mapping, independent reviewer and pre-development gate |
| M5 — Identity + Git integration | Authenticated identities, RBAC, Python GitHub adapter, isolated worktrees and PR gates | Implemented locally — authenticated identity services, mock and GitHub CLI providers, branch/PR rules and worktree isolation; real remote connection remains opt-in |
| M6 — Python application and agent runtime | FastAPI API, Streamlit UI, provider-neutral Python LLM adapter and role prompts | Next — all UI/API/agent source stays Python; deterministic policy controls actions |
| M7 — QA orchestration | Playwright for Python, pytest API/unit tests and Python RAG evaluation runners | Next — reports link back to story, AC, test and defect IDs |
| M8 — RAG and chatbot evaluation | Python retrieval pipeline, chatbot endpoints, DeepEval/RAGAS evaluation datasets and metrics | Next — answer quality, retrieval and groundedness gates are linked to stories and test cases |
| M9 — Defect loop and Scrum/reporting | Python bug-fix agents, retest/regression runner, workload, status, blockers and audit reports | Partial — local assignment/completion counts exist; connected PR/CI/test telemetry remains |
| M10 — Plug-and-play validation | Integrate with a second sample repository | Future — configuration-only onboarding works without copying app-specific code |

## M2 implementation details

- SQLite schema: `features`, `acceptance_criteria`, `workflow_events`, `resources`,
  `work_items`, `work_item_assignments`, `work_item_activity`, and `schema_migrations`.
- Workflow transition service loads current state, invokes the domain policy engine, then atomically
  appends the transition and updates feature state.
- A stale workflow snapshot is rejected rather than overwriting a newer state.
- CLI commands create/show/list features, apply feature transitions, register resources, create and
  assign tasks/defects/test cases, update task status, inspect task history, and view Scrum counts.
- Resource report metrics are limited to persisted assignment and completion counts. No work-hour,
  productivity, or time estimates are invented.

## M3 implementation details

- Added additive schema migration 0002 for business requirements, requirement versions, clarification
  questions, user stories, story acceptance criteria, traceability test cases, AC-to-test mappings,
  and requirement audit events.
- Requirements are versioned; updates require a change note and can use an optimistic expected-version
  check. Approved requirement records are locked against direct edits.
- BA submission is blocked by open clarifications, missing user stories, or a story without acceptance
  criteria. BA approval moves the package to PO review.
- QA Engineers create test-case records and map them to acceptance criteria during PO review.
- PO approval is blocked until every AC has at least one mapped test case. PO approval then marks the
  stories approved and records the approval event.
- The CLI can print a Markdown BRD and a live traceability summary.
- Actor-role values are still supplied as local CLI arguments; verified identity/authorization is a
  later security milestone. Test-case links represent planned coverage, not execution results.

## Language policy

All authored implementation and automation code is Python. The business application UI will use Streamlit and the API will use FastAPI. Browser automation will use the Playwright Python package with pytest. JavaScript, TypeScript, React, Node.js and npm are not permitted. See [the Python-only development standard](../standards/python-only-development.md).

## Branch and PR convention

- `main`: protected, releasable baseline.
- `feature/<story-id>-<short-name>`: application feature work.
- `bugfix/<bug-id>-<short-name>`: defect fixes.
- `qa/<story-id>-<suite-or-area>`: automation work.
- `chore/<short-name>`: framework maintenance.

For parallel work, each agent uses an isolated branch/worktree. Shared files have an explicit owner.
PRs require automated checks and code-owner review. Do not merge directly to `main`.

## Estimates and performance reporting

Do not present unmeasured agent time estimates as facts. The Scrum Master should show:
- planned estimate and who supplied it;
- actual start/end timestamps from work events;
- PR review and CI duration from GitHub/CI events;
- tests executed and outcomes from test reports;
- blockers and dependencies with age;
- work distribution normalized by complexity and available capacity.

Avoid simplistic agent rankings. Use transparent, reviewable metrics and include context.


## M4 — Solution architecture and technical-design gate (implemented in 0.4.0)

- Persist versioned architecture packages, ten mandatory artifacts, ADRs, story mappings, reviews and events.
- Require independent review and prevent self-approval.
- Enforce package ID linkage before architecture approval and developer start.
- Add architecture templates, beginner tutorial and automated checks.

## M5 — Identity and GitHub workflow integration (implemented locally in 0.5.0)

- Add credential-backed identities, role scopes, credential expiry/revocation and append-only audit events.
- Derive actor and role from authenticated credentials for feature workflow transitions.
- Add mock and GitHub CLI provider adapters, branch policy, isolated worktrees, PR traceability, independent review and CI merge gates.
- Live repository authorization, external OIDC, managed secrets and hosted deployment remain explicit follow-up work.
