# Definition of Done (initial baseline)

A feature is eligible for PO acceptance only when all applicable items are true:

- [ ] All BA-approved acceptance criteria are implemented or have an explicitly approved change.
- [ ] Architecture and database/API decisions are reviewed before implementation.
- [ ] Unit and integration tests pass.
- [ ] UI/API automation required by the test plan passes.
- [ ] RAG evaluations pass when the feature changes retrieval or chatbot behavior.
- [ ] Failed defects are fixed and verified; impacted regression and sanity tests pass.
- [ ] Security and privacy checks appropriate to the change are complete.
- [ ] Code review is approved and merge conflicts are resolved.
- [ ] Test evidence and traceability are linked to the story and PR.
- [ ] Rollback or recovery approach is documented for deployable changes.
- [ ] No mandatory test is silently skipped or represented as passed without execution.

Any exception must identify the reason, risk, approver, expiry/review date, and affected tests.
