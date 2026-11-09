# Python-only development standard

## Mandatory language policy

All authored application and framework implementation code must be Python. This applies to:

- Orchestrator services, domain rules, agent adapters and integrations.
- Business application backend and user interface.
- Database access, migration orchestration and background workers.
- Unit, API, UI, security, regression and RAG evaluation automation.
- CI helper scripts, report generation and developer tools.

JavaScript and TypeScript are not permitted. Do not add `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`, `.ps1`, `.sh`, `.bat`, `.cmd`,
`package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml` or `tsconfig.json`.
Do not introduce React, Node.js, npm, Yarn or pnpm into the project toolchain.

## Approved Python stack

| Concern | Approved implementation |
|---|---|
| Language/runtime | Python 3.11+ |
| Admin/user interface | Streamlit (Python source only) |
| HTTP API | FastAPI + Pydantic |
| Database | SQLite for local learning; PostgreSQL for shared deployment |
| Database access | SQLAlchemy + Alembic when the ORM milestone is implemented |
| Unit and API tests | pytest + Python HTTPX test client |
| Browser automation | Playwright for Python, authored as pytest `test_*.py` files |
| RAG evaluation | DeepEval and/or RAGAS Python packages |
| Agent orchestration | Python modules and provider-neutral Python protocols |
| Git/GitHub | Python adapters; Git CLI / GitHub CLI may be invoked as external tools |
| Formatting and static checks | Ruff and Python type checking |

Configuration files such as YAML/TOML, SQL schema migrations, Markdown documentation and GitHub
workflow YAML are allowed. They are declarative project assets, not a reason to introduce a second
application programming language. Local setup and test helpers must also be Python files. GitHub-hosted actions must run Python commands; do not add custom
JavaScript/TypeScript actions.

## UI and browser testing rules

The sample web application UI will be built with Streamlit, not React. UI behavior must be expressed
in Python. Browser automation will use the Python Playwright package through pytest. Test modules
must use names such as `tests/ui/test_login.py`; do not use TypeScript Playwright spec files.

A browser engine may execute its own internal scripts to render pages, but contributors must not
write, add, or maintain JavaScript or TypeScript source in this repository or in generated target
application code.

## Pull request enforcement

Every pull request must run the Python-only repository policy test. A PR must be rejected if it adds
any forbidden JavaScript/TypeScript source file or Node package manifest. The policy test also checks
the example target-project configuration and Playwright reference convention.
