# Beginner lesson: database persistence and command-line operations

## What changed in M2?

M1 kept workflow objects in Python memory. When the program stopped, those objects disappeared.
M2 stores feature requests, acceptance criteria, workflow events, team resources, tasks, assignments,
and task activity in a local SQLite database file.

SQLite is a relational database that stores data in a file. You do not need to install a database
server for this learning stage.

## Important concepts

- **Table:** a structured collection of records, similar to a sheet in a spreadsheet.
- **Primary key:** a value that uniquely identifies a record, such as `AUTH-001`.
- **Foreign key:** a database rule that prevents a child record from referring to a missing parent.
- **Transaction:** a group of database changes that either all succeed or all roll back.
- **Audit event:** a dated record of who performed an action and what changed.
- **Repository:** Python code that reads and writes database records without exposing SQL to the workflow rules.

## 1. Initialize the database

From the project root:

```powershell
python -m ai_sdlc --db data/demo.db init-db
```

This creates `data/demo.db`. The database file is local runtime data and should not be committed to Git.

## 2. Create a feature

```powershell
python -m ai_sdlc --db data/demo.db feature create `
  --id AUTH-001 `
  --title "User login" `
  --problem "Registered users need to sign in securely." `
  --ac "Valid credentials allow access." `
  --ac "Invalid credentials are rejected." `
  --ac "Disabled accounts cannot sign in."
```

Acceptance criteria receive stable sequence IDs such as `AC-001`, `AC-002`, and `AC-003` inside
the feature.

## 3. Inspect the feature

```powershell
python -m ai_sdlc --db data/demo.db feature list
python -m ai_sdlc --db data/demo.db feature show AUTH-001
```

## 4. Submit it for BA review

```powershell
python -m ai_sdlc --db data/demo.db feature transition AUTH-001 submit_for_ba_review `
  --unsafe-local-demo --unsafe-local-demo-role business_analyst `
  --unsafe-local-demo-actor-id BA-01 --note "Requirements submitted for BA review."
```

Try to start development at this point. The workflow should reject it because PO and architecture
approvals have not happened. A rejected action must not create an audit event or change the state.

## 5. Register resources and tasks

```powershell
python -m ai_sdlc --db data/demo.db resource add `
  --id DEV-01 --name "Developer One" --role developer --capacity 8

python -m ai_sdlc --db data/demo.db work-item create `
  --id TASK-001 --feature AUTH-001 --title "Implement login API" --estimate 3

python -m ai_sdlc --db data/demo.db work-item assign `
  --id TASK-001 --resource DEV-01 --assigned-by SCRUM-01 --allocation 100

python -m ai_sdlc --db data/demo.db work-item status `
  --id TASK-001 --status in_progress --actor-id DEV-01 --note "Started implementation."
```

When the task is complete, update it to `done` and attach a test-evidence reference:

```powershell
python -m ai_sdlc --db data/demo.db work-item status `
  --id TASK-001 --status done --actor-id DEV-01 `
  --note "Implementation and unit tests completed." `
  --evidence "artifacts/TASK-001-tests.xml"
```

## 6. Ask for a Scrum summary

```powershell
python -m ai_sdlc --db data/demo.db scrum summary
python -m ai_sdlc --db data/demo.db work-item history TASK-001
```

The summary reports counts stored in the local database. It does not estimate how long a resource
will take; measured durations will require explicit start/stop telemetry or CI/PR timestamps.

## Useful safety note

The role and actor values in these commands are caller-supplied demonstration values. Do not use this
local CLI as a security boundary for a shared team or production repository. Authentication,
authorization, and verified artifact links are planned before remote integrations are enabled.
