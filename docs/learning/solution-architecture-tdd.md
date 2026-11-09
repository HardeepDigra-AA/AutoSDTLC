# Beginner guide — solution architecture and TDD gate

## What problem does this milestone solve?

A developer should not have to guess the database structure, API behavior, security model or test expectations. The architect prepares a common plan before developers work in parallel. The framework stores that plan and prevents development from starting until it has been independently reviewed.

## Two meanings that must not be mixed up

- **Technical Design Document:** explains how the solution is structured and how the requirements will be implemented.
- **Test-Driven Development:** developers write a failing test first, implement the smallest change to make it pass, then refactor while keeping tests green.

M4 stores both as separate sections.

## Learn the commands

Initialize or upgrade the database:

```powershell
python -m ai_sdlc --db data/demo.db init-db
```

See available architecture commands:

```powershell
python -m ai_sdlc --db data/demo.db architecture --help
python -m ai_sdlc --db data/demo.db architecture artifact --help
```

Create a design package after the feature is in `architecture_review` and the linked requirement is PO approved:

```powershell
python -m ai_sdlc --db data/demo.db architecture create `
  --id ARCH-AUTH-001 `
  --feature AUTH-001 `
  --requirement REQ-AUTH-001 `
  --created-by ARCH-01
```

For each artifact, keep the content in a Markdown file. This is easier to review than pasting a large document into the terminal:

```powershell
python -m ai_sdlc --db data/demo.db architecture artifact `
  --package ARCH-AUTH-001 `
  --type technical_design `
  --title "Login Technical Design" `
  --file docs/design/AUTH-001-technical-design.md `
  --created-by ARCH-01
```

Supported artifact keys:

```text
solution_overview
component_design
technical_design
database_design
api_contracts
security_threat_model
coding_standards
test_driven_development_plan
test_strategy
deployment_rollback
```

Record a decision:

```powershell
python -m ai_sdlc --db data/demo.db architecture adr `
  --id ADR-AUTH-001 `
  --package ARCH-AUTH-001 `
  --title "Use PostgreSQL for identity data" `
  --context "Login and session state need transactional persistence." `
  --decision "Use PostgreSQL with normalized identity and session tables." `
  --consequences "Use reviewed migrations, backups and least-privilege roles." `
  --created-by ARCH-01
```

Map every user story under the requirement:

```powershell
python -m ai_sdlc --db data/demo.db architecture map-story `
  --package ARCH-AUTH-001 `
  --story US-AUTH-001 `
  --mapped-by ARCH-01
```

Review the checklist before submitting:

```powershell
python -m ai_sdlc --db data/demo.db architecture checklist ARCH-AUTH-001
```

Submit and obtain a separate review:

```powershell
python -m ai_sdlc --db data/demo.db architecture submit ARCH-AUTH-001 `
  --actor-id ARCH-01 `
  --note "All design sections, ADRs and story mappings are complete."

python -m ai_sdlc --db data/demo.db architecture review ARCH-AUTH-001 `
  --outcome approved `
  --reviewer-id ARCH-REVIEWER-01 `
  --note "Independent architecture review passed." `
  --evidence reviews/ARCH-AUTH-001.md
```

Only after the independent review, record the approval in the feature workflow:

```powershell
python -m ai_sdlc --db data/demo.db feature transition AUTH-001 approve_architecture `
  --unsafe-local-demo --unsafe-local-demo-role architect `
  --unsafe-local-demo-actor-id ARCH-01 `
  --note "Approved architecture package attached." `
  --evidence ARCH-AUTH-001

python -m ai_sdlc --db data/demo.db feature transition AUTH-001 start_development `
  --unsafe-local-demo --unsafe-local-demo-role developer `
  --unsafe-local-demo-actor-id DEV-01 `
  --note "Starting implementation against approved design."
```

If an artifact is incomplete, a story is unmapped or the reviewer requests changes, the feature must not be moved into development.

## What to understand before approving

Ask whether the design covers each acceptance criterion, data state and transition, API success and error response, authorization boundary, logging/audit requirement, test data needs, deployment order and rollback. Check that every important technology choice has a reason and trade-off. Do not approve only because all sections contain text.

## What is not automated yet?

The starter checks required section presence, simple placeholder rules, requirement state, story mappings, package status, independent reviewer identity string and workflow linkage. It does not use an LLM or human expert to prove that a database schema is normalized, APIs are secure, the threat model is complete or the chosen architecture is scalable. Those remain review responsibilities until deeper static and policy checks are added.
