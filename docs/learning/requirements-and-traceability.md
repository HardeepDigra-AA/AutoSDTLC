# M3 learning guide — Business requirements and traceability

This guide explains the first controlled stage of the product lifecycle. You do not need to write
Python to use the commands; the goal is to understand what each command is asking the framework to do.

## 1. The important terms

| Term | Meaning | Example |
|---|---|---|
| Business requirement | The business problem or capability the organization needs | Registered users need secure access to their accounts. |
| BRD | Business Requirements Document; the organized record of the need, value, scope and related stories | `REQ-AUTH-001` |
| User story | A small user-centred description of the capability | As a registered user, I want to sign in with my credentials, so that I can access my account. |
| Acceptance criterion (AC) | A specific condition that must be satisfied for the story to be accepted | Valid credentials authenticate the user. |
| Test case | A repeatable verification that proves one or more criteria | Submit valid credentials and verify a successful authenticated response. |
| Traceability | The links showing which test verifies which acceptance criterion and requirement | `REQ-AUTH-001 → US-AUTH-001 → AC-AUTH-001 → TC-AUTH-001` |

The requirement is the parent record. One requirement can contain multiple user stories. Each story
must contain one or more acceptance criteria. QA creates test cases and maps each criterion to at
least one test case. A test-case mapping is planned coverage; it does not mean the test has run or
passed.

## 2. Why the IDs matter

Stable IDs let us discuss work without relying on titles that may change. This project uses IDs such as:

- `REQ-AUTH-001`: business requirement
- `US-AUTH-001`: user story
- `AC-AUTH-001`: acceptance criterion
- `TC-AUTH-001`: test case
- Later: `BUG-AUTH-001`: defect linked to a failed execution

IDs must be unique within their table. Do not reuse an old ID for unrelated work.

## 3. Capture a requirement

```powershell
python -m ai_sdlc --db data/demo.db requirement create `
  --id REQ-AUTH-001 `
  --title "Secure user login" `
  --description "Registered users must sign in using valid credentials." `
  --business-value "Protect user data and provide authenticated access." `
  --priority high `
  --created-by REQUESTER-01
```

What each field means:

- `--id`: stable identifier; it must be unique.
- `--title`: short name that can appear in reports.
- `--description`: what the business is asking for.
- `--business-value`: why the organization needs the capability.
- `--priority`: business priority, not a technical severity.
- `--created-by`: source actor reference. In this local prototype it is not authenticated.

Every new requirement starts as `draft` and gets version 1. Version 1 is saved to the version-history
table so the initial intake can be inspected later.

## 4. Clarify ambiguity before approval

A BA should not invent missing business rules. Record a question:

```powershell
python -m ai_sdlc --db data/demo.db requirement clarification add `
  --requirement REQ-AUTH-001 `
  --id CLAR-AUTH-001 `
  --question "Should locked accounts be allowed to sign in?" `
  --asked-by BA-01
```

The requirement moves to `clarification_required`. The requester records the answer:

```powershell
python -m ai_sdlc --db data/demo.db requirement clarification answer `
  --id CLAR-AUTH-001 `
  --answer "No. Locked accounts must be denied access." `
  --answered-by REQUESTER-01
```

BA submission is blocked until all clarification records are answered. The answer and the actors are
stored in the database. A new requirement version is not created just by answering a question; use
`requirement update` with a change note when the actual requirement wording or business value changes.

## 5. Maintain requirement versions

An edit requires a change note:

```powershell
python -m ai_sdlc --db data/demo.db requirement update REQ-AUTH-001 `
  --business-value "Protect accounts and reduce unauthorized access." `
  --changed-by REQUESTER-01 `
  --change-note "PO clarification 1: business value made more specific." `
  --expected-version 1
```

The expected version is an optimistic concurrency check. Imagine two people open version 1. Person A
saves version 2. If person B then tries to save using expected version 1, the update is rejected instead
of silently overwriting Person A's change. Direct changes after PO approval are blocked; use a new
change-control process for approved scope.

## 6. BA creates a user story and acceptance criteria

```powershell
python -m ai_sdlc --db data/demo.db requirement story `
  --id US-AUTH-001 --requirement REQ-AUTH-001 `
  --title "Sign in with credentials" `
  --as-a "registered user" `
  --i-want "to sign in with my email and password" `
  --so-that "I can securely access my account" `
  --created-by BA-01

python -m ai_sdlc --db data/demo.db requirement criterion `
  --id AC-AUTH-001 --story US-AUTH-001 `
  --description "Valid credentials authenticate the user." `
  --created-by BA-01
```

Acceptance criteria should be atomic, observable, testable and unambiguous. Avoid phrases like
"works correctly", "fast enough" or "user-friendly" unless they are made measurable. For example,
replace "login is fast" with a measurable response-time target agreed by the business and architect.

The framework checks for at least one story per requirement and at least one AC per story before BA
submission. It cannot yet determine whether natural-language criteria are genuinely testable; BA,
PO and architect review remains necessary.

## 7. BA review and approval

```powershell
python -m ai_sdlc --db data/demo.db requirement submit-ba REQ-AUTH-001 `
  --actor-id BA-01 --note "BRD, stories and AC are ready for BA review."

python -m ai_sdlc --db data/demo.db requirement approve-ba REQ-AUTH-001 `
  --actor-id BA-01 --note "BA review completed; criteria are clear and testable."
```

The first command submits the package for BA review. The second moves it into `po_review`. The
current prototype records the approver role supplied by the CLI. It does not prove that the person
actually belongs to that role; verified identity is a future security milestone.

## 8. QA creates test cases and maps coverage

After BA approval, QA prepares test cases:

```powershell
python -m ai_sdlc --db data/demo.db requirement test-case `
  --id TC-AUTH-001 `
  --title "Valid credentials succeed" `
  --description "Submit an active user's valid credentials and verify an authenticated response." `
  --level api --created-by QA-02 `
  --automation-reference "tests/api/test_auth_login.py"

python -m ai_sdlc --db data/demo.db requirement map-test `
  --criterion AC-AUTH-001 --test-case TC-AUTH-001 --mapped-by QA-02
```

Allowed test levels are `unit`, `api`, `ui`, `integration`, `security`, `accessibility`, and `rag`.
One criterion may map to multiple test cases; one test case can cover multiple criteria. The mapping
records who created the relationship and when.

## 9. PO approves only with complete traceability

```powershell
python -m ai_sdlc --db data/demo.db requirement show REQ-AUTH-001
python -m ai_sdlc --db data/demo.db requirement brd REQ-AUTH-001
python -m ai_sdlc --db data/demo.db requirement approve-po REQ-AUTH-001 `
  --actor-id PO-01 --note "Business scope and AC-to-test mapping reviewed."
```

PO approval is rejected if even one AC has no mapped test case. The traceability view reports covered
and uncovered criteria. Once PO approves, the requirement becomes read-only and its user stories are
marked approved.

## 10. What this milestone does not claim

- A mapped test case has not necessarily been automated or executed.
- A 100% mapping percentage does not mean the product has 100% test coverage or is defect-free.
- Requirement approval is not architecture approval, code review, QA signoff or release approval.
- CLI actor IDs and role arguments are not secure authentication.
- No LLM agents are making these decisions yet. The current behavior is deterministic Python code.

These boundaries are intentional. Later milestones will connect approved requirement IDs to
architecture documents, Git branches, PRs, executed test reports, defects and deployment evidence.
