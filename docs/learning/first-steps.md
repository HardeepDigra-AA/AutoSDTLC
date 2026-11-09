# Beginner guide: your first implementation

## What is this repository?

Think of it as a traffic controller for software work. It does not build the business application
by itself yet. It records where a feature is in its lifecycle and blocks actions that are not
allowed at that point.

## Five ideas to understand

1. **Repository:** the project folder plus its version history.
2. **Feature request:** a business change that needs to be delivered.
3. **Workflow state:** the current stage, such as BA review or QA execution.
4. **Role:** the responsibility allowed to perform an action, such as BA or QA Lead.
5. **Audit event:** a timestamped record of who performed an action, what changed, and what evidence
   was attached.

## Why start with a deterministic workflow?

An LLM can produce a convincing but incorrect answer. The workflow engine is ordinary Python code
with explicit rules. An AI agent may suggest `approve_architecture`, but the engine still checks
that the feature is in architecture review, the actor is an architect, a note is present, and a
design-evidence reference is attached.

## Run the tests

```powershell
python -m pip install -e ".[dev]"
python -m pytest -v
```

A passing test means that the tested rule behaved as expected in that test run. It does not mean
the future business application is already tested or bug-free.

## Run the workflow demonstration

```powershell
python examples\run_workflow.py
```

Read the output from top to bottom. Each line is one approved transition. The final state should
be `released` and the audit event count should be 12.

## Suggested learning order

1. Open `src/ai_sdlc/domain/workflow.py` and read the enums (`WorkflowState`, `Role`, `Action`).
2. Read `RULES`; it declares which role can perform each action and from which state.
3. Read `WorkflowEngine.apply`; this is the enforcement point.
4. Open `tests/test_workflow.py`; each test proves one behavior or protection.
5. Change a rule only after adding a test that explains the intended business behavior.

## Next lesson: persistence and the CLI

After the in-memory workflow lesson, continue with
[Persistence and CLI](persistence-and-cli.md). It explains the SQLite database, feature records,
resources, tasks, assignments, task history, and the Scrum summary commands step by step.

## What is intentionally not automated yet?

M5 now includes local credential-backed identities, RBAC, a GitHub provider boundary, safe branch rules, isolated worktrees, PR review and CI merge gates. It has not been connected to your live GitHub repository, and independent LLM agents, the Streamlit UI, the sample business application, Playwright execution and RAG evaluation remain future increments. All future implementation and test automation will be authored in Python.

## Easy setup on Windows

From the repository root in the VS Code terminal, run:

```powershell
python scripts/bootstrap_environment.py
python scripts/run_tests.py
```

The setup script creates `.venv` and installs the project with its development tools. You do not
need to write Python code to run these steps.

## Who is the Scrum Master?

The Scrum Master monitors work and prepares evidence-based status reports. This role does not
approve architecture, QA signoff, protected-branch merges or production releases. The role cannot
change a task to "done" without evidence from the relevant system.
