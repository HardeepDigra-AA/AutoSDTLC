# Architecture overview

## 1. Architectural style

Use a modular monolith for the initial orchestrator. It is easier for a beginner to understand,
test, run locally, and deploy than a collection of microservices. Keep clear module boundaries
so high-load components can be separated later if evidence justifies it.

## 2. Logical components

```text
User / Project Owner
        |
        v
Orchestrator API + CLI  ---- Approval Manager
        |                         |
        v                         v
Workflow Engine <---------- Policy / Role Rules
        |
        +---- Agent Dispatcher ---- BA / PO / Architect / Dev / QA / Scrum profiles
        |
        +---- Work Item Service ---- Stories / Tasks / Defects / Test Runs
        |
        +---- Integration Adapters - Python GitHub/Git adapters / Python CI clients / Playwright Python / pytest / Python RAG evals
        |
        +---- Reporting Service ---- Status / Traceability / Release reports
        |
        v
Persistence + Audit Log + Artifact References
```

The implementation language is Python only. Streamlit provides the Python-authored UI, FastAPI provides the Python API, Playwright is used through its Python package, and pytest owns test execution. No JavaScript or TypeScript source is permitted.

The workflow engine is authoritative for lifecycle state. Agents propose actions and create
artifacts; they do not bypass the engine or grant themselves approvals.

## 3. Layers and responsibilities

| Layer | Responsibility | Initial implementation |
|---|---|---|
| Interfaces | Human interaction and automation entry points | Python CLI; Streamlit UI; FastAPI HTTP API |
| Application | Use cases, orchestration, assignment and approvals | Planned |
| Domain | Workflow rules, roles, entities and policies | Implemented; deterministic workflow state machine |
| Infrastructure | Database, GitHub, model providers, CI and artifact adapters | SQLite implemented; external adapters planned |
| Observability | Audit events, run logs, metrics and reports | Feature transitions and work-item activity persist in SQLite; external telemetry planned |

## 4. Persistence decision

- Local development: begin with SQLite for simple setup.
- Shared/team deployment: PostgreSQL for transactional work items, workflow state, approvals,
  assignments, and audit events.
- Vector retrieval: pgvector only when the framework itself needs semantic retrieval over project
  documents. It is not required for the deterministic workflow engine.
- Evidence: store a durable reference to CI artifacts, PRs, test reports, traces, and screenshots;
  do not place large binary artifacts directly in workflow rows.

## 5. Agent execution model

Start with sequential, bounded agent dispatch. Add parallel execution only after tasks have explicit
file ownership, dependencies, contracts, isolated branches/worktrees, and merge gates. A role
profile defines responsibilities and permitted actions; it does not imply that a separate model
must run continuously for every resource.

## 6. Security and governance

- Use least-privilege repository and environment permissions.
- Keep secrets in a secret manager or CI secret store, never in Git.
- Require human approval for protected-branch merges and production deployment.
- Log the actor, role, action, timestamp, workflow state change, and evidence reference.
- Separate the authority to propose code from the authority to approve and release it.

## 7. Current implementation boundary (M0–M5)

Implemented: deterministic feature lifecycle, SQLite persistence, requirements and acceptance-criteria traceability, architecture approval gates, local credential-backed identities, role/scope authorization, authenticated feature transitions, GitHub provider interfaces, mock/GitHub CLI adapters, branch policies, isolated Git worktrees, PR review/CI merge gates, local CLI, and automated tests.

Not implemented yet: external SSO/OIDC, hosted API deployment, PostgreSQL deployment adapter, autonomous LLM agents, connected live GitHub repository operations, the Streamlit administration UI, the sample business application, real Playwright-for-Python test execution, and Python RAG evaluations.

## 8. Prototype limitations and security boundary

The current implementation is a local authenticated control-plane prototype, not yet an enterprise-hosted multi-user service:

- Feature workflow transitions can authenticate local bearer credentials and derive actor/role from stored identity records. The requirement and architecture demonstration commands still accept local actor IDs for controlled learning only.
- Shared production deployment must add an external identity provider/OIDC, authenticated API boundary, TLS, and a managed secret store.
- Evidence references are required as strings but are not yet checked for existence, ownership,
  integrity, or expiry.
- Defects currently use the generic work-item model; a later increment adds severity, SLA, retest
  links, root-cause analysis, and defect lifecycle rules.
- SQLite is appropriate for local learning. A shared deployment needs PostgreSQL, tested migrations,
  backup/restore, access controls, and monitoring.
- Resource workload metrics are assignment and completion counts only. Time and performance reports
  require measured events from agents, PRs, CI, and test runners.

These limits are intentional and are exit criteria for the persistence, identity, and integration
milestones. Do not connect the prototype directly to a production repository or release environment.


## M4 architecture approval boundary

Solution architecture is stored as a versioned package linked to an approved requirement and feature.
The package contains required design artifacts, ADRs, user-story mappings, independent review
records and an audit trail. The workflow service verifies that the approved package ID matches the
feature's architecture approval event before allowing development. See
[the detailed M4 gate design](solution-architecture-and-tdd-gate.md).
