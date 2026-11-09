# Agent operating rules

These rules apply to every AI or human contributor working in this repository.

## Before changing code

1. Read the relevant requirement, architecture decision, and acceptance criteria.
2. Confirm the assigned task, owner, scope, dependencies, and files permitted to change.
3. Do not invent missing business rules. Ask the BA/PO for clarification and record the answer.
4. Do not start implementation while the feature is waiting for BA, PO, or architecture approval.
5. Follow test-driven development: add or update a failing test before implementing the behavior.

## While changing code

1. Work only on the assigned branch/worktree and owned files.
2. Keep changes small and focused; do not reformat unrelated files.
3. Never commit secrets, credentials, personal data, or production data.
4. Never weaken or delete a test merely to make a pipeline pass.
5. Record assumptions, design decisions, test commands, and outcomes.

## Before opening a pull request

1. Run the relevant automated tests and quality checks locally.
2. Confirm every acceptance criterion maps to one or more tests or documented manual checks.
3. Include the requirement/story ID, summary, implementation notes, test evidence, risks, and rollback notes.
4. Resolve conflicts by understanding both changes; do not blindly choose one side.
5. Request the required code-owner review. Do not self-approve a protected-branch merge.

## QA rules

1. Use stable selectors such as accessible roles, labels, and test IDs; avoid brittle CSS/XPath selectors.
2. Keep tests independent, deterministic, and isolated from shared mutable test data.
3. Do not duplicate coverage without a documented reason; consolidate only when all requirement links remain covered.
4. Capture useful failure evidence (report, trace, screenshot, request/response details) without exposing secrets.
5. After a fix, rerun the failed test, impacted regression, and agreed sanity suite.
6. A defect is not fixed until QA verifies it. A test is not passed until it has actually executed successfully.

## Governance rules

- No direct pushes to protected branches.
- No unreviewed merge or automatic production deployment.
- No release while a mandatory test is failed, blocked, not run, or missing evidence unless an authorized exception is documented.
- Agent estimates are planning inputs, not promises. Scrum reports must distinguish estimates from measured actuals.

## Requirements and traceability rules

1. Do not translate vague business requests directly into implementation tasks. Record the requirement
   and open a clarification whenever a business rule, actor, exception, or expected outcome is unclear.
2. Keep requirement IDs, story IDs, AC IDs, and test-case IDs stable and unique. Never reuse retired IDs.
3. Each user story must have one or more individually identified, observable acceptance criteria.
4. BA submission is blocked by open clarifications, missing stories, or stories without AC.
5. PO approval requires every AC to map to at least one QA-owned test case. A mapping is planned
   coverage only; never report it as an executed or passed test.
6. Requirement updates require a change note and should use the expected-version check. Approved scope
   must be changed through a new controlled change request, not by editing the approved record.
7. Keep BA approval, PO approval, architecture approval, QA signoff, and release approval distinct.


## Solution architecture and technical-design rules

1. Do not start development until the linked business requirement is PO-approved and the feature is in `architecture_review`.
2. The architecture package must contain all ten required artifact types: solution overview, component design, Technical Design Document, database design, API contracts, security threat model, coding standards, test-driven development plan, test strategy, and deployment/rollback plan.
3. Record at least one ADR with context, decision and consequences. Record the alternatives and trade-offs in the ADR content.
4. Map every user story under the linked requirement to the architecture package. An architecture-to-story mapping is not implementation or test evidence.
5. The architect submits the package; a separate architecture reviewer must approve or request changes. Never self-approve.
6. Approved packages are immutable. A change requires a new version and a new independent review. Keep prior versions and review events for auditability.
7. Record the exact approved package ID in the feature workflow. The development gate must verify that the workflow approval and current approved package refer to the same package.
8. Do not treat artifact presence as proof of technical correctness. Review data integrity, API semantics, security threats, failure handling, operational support, testability and rollback in detail.
9. Distinguish the Technical Design Document from Test-Driven Development. Both are mandatory, separately reviewed deliverables.


## Python-only language policy

1. All authored application, UI, backend, orchestration, integration, agent, QA automation and evaluation code must be Python.
2. Do not add JavaScript, TypeScript, PowerShell, shell, batch or command implementation files; do not add React components, Node.js projects, npm manifests, package managers, or TypeScript configuration.
3. The approved user interface is Streamlit (Python); the approved HTTP API is FastAPI (Python).
4. Browser automation must use Playwright for Python and pytest modules named `test_*.py`.
5. YAML, TOML, SQL migrations and Markdown are allowed as declarative configuration, schema and documentation assets. Do not embed JavaScript or TypeScript in them.
6. Run `python -m pytest tests/test_python_only_policy.py -q` before every PR.
