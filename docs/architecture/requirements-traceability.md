# M3 requirements and traceability architecture

## Lifecycle

```mermaid
flowchart TD
    A[Requester captures requirement] --> B[BA clarification and analysis]
    B -->|Questions open| C[Requester answers]
    C --> B
    B -->|Complete BRD, stories and AC| D[BA review]
    D -->|BA approves| E[Product Owner review]
    E --> F[QA authors test cases and maps each AC]
    F --> G{Every AC has one or more tests?}
    G -->|No| F
    G -->|Yes| H[PO approves scope]
    H --> I[Architecture gate — M4]
```

## Data relationships

```mermaid
erDiagram
    BUSINESS_REQUIREMENTS ||--o{ REQUIREMENT_VERSIONS : snapshots
    BUSINESS_REQUIREMENTS ||--o{ REQUIREMENT_CLARIFICATIONS : clarifies
    BUSINESS_REQUIREMENTS ||--o{ USER_STORIES : decomposes
    BUSINESS_REQUIREMENTS ||--o{ REQUIREMENT_EVENTS : audits
    USER_STORIES ||--|{ STORY_ACCEPTANCE_CRITERIA : defines
    STORY_ACCEPTANCE_CRITERIA ||--o{ CRITERION_TEST_CASE_MAP : verified_by
    TRACEABILITY_TEST_CASES ||--o{ CRITERION_TEST_CASE_MAP : covers
```

## Deterministic approval rules

1. A requirement must have a non-empty title, description, business value, and supported priority.
2. BA cannot submit while any clarification is open.
3. BA cannot submit a requirement without at least one story.
4. Every story must have at least one acceptance criterion.
5. Only BA can submit or approve BA review; only PO can approve scope or request changes.
6. QA Engineer role is required to create a traceability test case and map it to an AC.
7. QA mappings are editable during PO review only.
8. PO approval is rejected when any AC has zero mapped test cases.
9. PO approval marks the stories approved and locks the approved requirement against direct edits.
10. Requirement edits require a change note, create a complete version snapshot, and can require an expected version.

## Important separation of concerns

The M3 traceability module records planned verification coverage. It does not run the tests or infer
that a test passed. Later QA orchestration will attach test-execution records and defect/evidence IDs.
Similarly, PO approval is not the solution-architecture approval; M4 adds the TDD and architecture
approval gate before development can begin.

## Migration

`migrations/0002_requirements_traceability.sql` adds M3 tables and indexes without changing M2 tables.
The SQLite adapter applies the migration when it detects schema version 1. Re-running initialization
is safe. A PostgreSQL adapter and production-grade migration management are future work.
