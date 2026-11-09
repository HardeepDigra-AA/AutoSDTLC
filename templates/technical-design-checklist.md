# Solution Architecture / TDD Checklist: <STORY-ID>

## Architecture
- [ ] Context, components, dependencies and sequence are documented.
- [ ] Existing patterns and compatibility impact are reviewed.
- [ ] Non-functional requirements (performance, availability, accessibility) are considered.

## Data design
- [ ] Entities, attributes, keys, constraints and relationships are documented.
- [ ] Migration and rollback strategy are documented.
- [ ] Privacy, retention and access-control requirements are addressed.

## API and integration design
- [ ] Endpoint/event contracts, validation, errors and idempotency are defined.
- [ ] Authentication and authorization are specified.
- [ ] External dependency failure behavior is defined.

## Security
- [ ] Threats and trust boundaries are reviewed.
- [ ] Secrets and sensitive data handling are defined.
- [ ] Audit logging and least privilege are covered.

## Test design
- [ ] Unit, integration, API, UI, security and performance tests are selected as applicable.
- [ ] Acceptance criteria map to test conditions.
- [ ] Test data, isolation, cleanup and evidence strategy are defined.

## Coding and delivery
- [ ] Language/framework standards and file ownership are stated.
- [ ] Branch/PR plan and code owners are assigned.
- [ ] CI gates and deployment/rollback approach are defined.

## Decision
- Architect: <name/agent ID>
- Status: <Draft / In Review / Approved / Rejected>
- Evidence: <link>
- Approval date: <date>
