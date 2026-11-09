# Agent team and operating model

## Roster

The intended virtual team contains 12 role instances:

| Team | Count | Primary responsibility |
|---|---:|---|
| Business Analyst | 1 | Clarify business need; author requirements, stories and acceptance criteria |
| Product Owner | 1 | Prioritize, approve scope and verify business acceptance |
| Solution Architect | 1 | Approve solution, database/API design, TDD plan, security and coding standards |
| Developers | 4 | Implement assigned tasks, add unit tests, fix defects and respond to review |
| QA Lead | 1 | Own automation standards, review test code, resolve conflicts, remove redundant coverage safely, sign off QA |
| QA Engineers | 3 | Design and execute UI, API, integration, regression and RAG evaluation tests |
| Scrum Master | 1 | Track commitments, work in progress, blockers, delivery evidence and resource load |

The release approver and independent architecture reviewer are separately authorized governance
roles by default; neither is an extra autonomous agent in the 12-person roster. The architecture
reviewer performs a four-eyes check because the initial roster has one solution architect. The count
is a role allocation, not a promise that twelve independent model sessions run at once.
Agent execution is initially sequential. Parallel workers will be enabled only after isolated worktrees,
explicit file ownership, dependency contracts, test-data isolation and merge gates are working.

## Assignment principles

- Balance work by estimated complexity, risk, dependencies and each worker's available capacity—not
  by assigning the same number of tickets to everyone.
- Give each task one accountable owner and a clear definition of done.
- Assign independent files or folders to parallel contributors. Shared files have a designated owner.
- All application and automation implementation is Python. The target UI is Streamlit; the API is FastAPI; browser automation uses Playwright for Python with pytest. Developers and QA engineers use separate branches/worktrees. Shared test fixtures are owned by QA Lead.
- The Scrum Master tracks observable events (task transitions, commits, PRs, reviews, CI runs, test
  reports and blockers). The agent's self-reported progress is labelled as unverified until evidenced.
- Do not use raw commit count or lines of code as a performance score. Report throughput, review quality,
  defect escape/reopen trends, cycle time and workload with context.

## Separation of duties

- BA authors requirements; PO approves scope and business acceptance.
- Architect authors and submits the technical design; an independent architecture reviewer approves
  or requests changes; the architect then records the exact approved package in the feature workflow.
- Developer authors changes; designated reviewers approve them.
- QA engineers execute tests; QA Lead approves QA signoff.
- Release Manager (a separately authorized human or configured role) releases the change.
- Scrum Master reports progress but cannot bypass a quality gate or approve a release.

## Example task split for one feature

| Resource | Initial assignment | Isolation expectation |
|---|---|---|
| DEV-01 | Python UI implementation (Streamlit) | Feature branch/worktree; UI-owned Python files |
| DEV-02 | Python API implementation (FastAPI) | Feature branch/worktree; API-owned Python files |
| DEV-03 | Data model and migrations | Feature branch/worktree; migration-owned files |
| DEV-04 | Security hardening and integration | Feature branch/worktree; security/integration-owned files |
| QA-01 | Browser automation (Playwright Python) | QA branch/worktree; Python pytest UI tests |
| QA-02 | API and integration tests (pytest) | QA branch/worktree; Python API tests |
| QA-03 | Security, regression and RAG evaluation | QA branch/worktree; assigned suite files |
| QA Lead | Framework review and merge conflict resolution | Owns shared fixtures/configuration and final QA review |

The architect must first confirm interfaces and dependencies. This table is a sample allocation, not a fixed
mapping for every feature.
