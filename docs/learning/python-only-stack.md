# Beginner guide — Python-only application stack

## The language rule

Every implementation file we author for the orchestrator, target business application, agents,
integrations and QA automation is Python. Do not add JavaScript or TypeScript source, React
components, Node projects or Node package manifests. Local setup and test-runner helpers are Python
as well.

The repository still contains declarative assets: YAML/TOML configuration, SQL schema migrations,
Markdown documentation and GitHub workflow YAML. These describe configuration, database structure
or CI steps; they are not a second application implementation language.

## Approved stack

| Layer | Technology | Why it fits the Python-only rule |
|---|---|---|
| User interface | Streamlit | UI screens and interactions are authored in Python |
| HTTP API | FastAPI + Pydantic | Routes, validation and API services are Python |
| Persistence | SQLite locally; PostgreSQL for shared use | Accessed through Python database libraries |
| Browser automation | Playwright for Python | Test files and browser interactions are Python |
| Unit/API tests | pytest + HTTPX | Test functions and API clients are Python |
| RAG evaluation | DeepEval / RAGAS | Evaluation datasets and metrics are defined in Python |
| Agent orchestration | Python services and provider adapters | Role prompts, dispatch and policy checks are Python |
| Git/GitHub | Python adapters | Repository operations are initiated by Python code |

## Why Streamlit instead of a separate JavaScript frontend?

The goal is to keep UI behavior, validation, state changes and application rules understandable in
one language. Streamlit lets us write the UI in Python. FastAPI remains available for stable API
contracts, service integrations and external automation. The browser still renders the UI, but we
will not write or maintain client-side JavaScript/TypeScript source.

## Why Playwright for Python?

Playwright provides a Python package, so UI tests can be ordinary pytest modules such as:

```text
tests/
  ui/
    test_login_page.py
  api/
    test_authentication_api.py
```

Install the optional Python QA dependencies with:

```powershell
python -m pip install -e ".[qa]"
python -m playwright install chromium
```

## Install optional project components

```powershell
# Python UI and API packages
python -m pip install -e ".[web]"

# Python browser and API test packages
python -m pip install -e ".[qa]"

# Python RAG evaluation packages
python -m pip install -e ".[rag]"
```

Do not install a Node package manager or add browser automation specs in another language.
