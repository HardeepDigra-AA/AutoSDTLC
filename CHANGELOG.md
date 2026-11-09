# Changelog

## 0.5.0 — M5 authenticated identities and GitHub governance

- Added first-run identity-admin bootstrap and per-resource identities for agent, human and service actors.
- Added opaque one-time bearer credentials stored as salted PBKDF2-HMAC-SHA256 hashes; raw tokens are never persisted.
- Added credential expiration, revocation, identity disablement, reactivation and append-only identity audit events.
- Added explicit role-to-scope authorization policies and an authenticated workflow gateway that derives actor ID and role from verified credentials.
- Added GitHub CLI provider and deterministic mock provider behind a common adapter interface.
- Added safe branch naming, isolated Git worktree management, PR traceability requirements, independent review enforcement and CI/review merge gates.
- Added protected-default-branch merge restriction for release managers and GitHub repository/PR/workspace audit records.
- Added CLI commands for bootstrap, agent registration, authentication verification, repository registration, worktree operations and PR lifecycle.
- Added additive SQLite migration 0004 and tests for M2/M4 upgrades.
- Updated PR template, CODEOWNERS examples and read-only GitHub Actions CI permissions.


## 0.4.0 — M4 solution architecture and TDD approval gate

- Added a versioned architecture package linked to a feature and PO-approved business requirement.
- Added ten required architecture artifacts, ADRs and user-story-to-architecture mappings.
- Added independent four-eyes review; package authors cannot approve their own submissions.
- Added `changes_requested` remediation/resubmission, immutable approved packages and superseding versions.
- Added completeness checklist and architecture CLI commands.
- Enforced exact approved-package evidence for architecture approval and developer start.
- Added additive SQLite schema migration 0003 and beginner architecture/TDD templates and guides.
- Added service, persistence, migration and end-to-end CLI tests for M4.


## 0.3.0 — M3 requirements and traceability

- Added versioned business requirement intake with optimistic version checks and change notes.
- Added BA clarification questions and requester answers; open clarifications block BA submission.
- Added BA-owned user stories and stable acceptance-criteria IDs.
- Added QA test-case records and many-to-many AC-to-test-case mappings.
- Added BA and PO review transitions, role checks, audit events and a strict PO traceability gate.
- Added Markdown BRD/traceability output and beginner CLI documentation.
- Added additive SQLite schema migration 0002.
- Added automated tests for lifecycle gates, traceability coverage, permissions, migration upgrades and CLI walkthroughs.

## 0.2.0 — M2 persistence and CLI

- Added SQLite persistence for feature workflows, team resources, work items, assignments and activity.
- Added optimistic feature transition writes and a local Scrum summary.

## 0.1.0 — Bootstrap and workflow core

- Added initial repository structure, workflow state machine, standards and starter tests.
