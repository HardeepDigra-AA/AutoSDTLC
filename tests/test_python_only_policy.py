"""Repository guard enforcing the user's Python-only implementation requirement."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SOURCE_SUFFIXES = {
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".ps1",
    ".sh",
    ".bat",
    ".cmd",
}
FORBIDDEN_MANIFEST_NAMES = {
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "tsconfig.json",
}
IGNORED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}


def repository_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in IGNORED_DIRECTORIES for part in path.parts)
    ]


def test_repository_contains_no_non_python_implementation_scripts() -> None:
    forbidden = [
        str(path.relative_to(ROOT))
        for path in repository_files()
        if path.suffix.lower() in FORBIDDEN_SOURCE_SUFFIXES
    ]
    assert forbidden == [], f"Non-Python implementation scripts are prohibited: {forbidden}"


def test_executable_project_directories_contain_python_files_only() -> None:
    code_directories = ("src", "tests", "examples", "scripts")
    non_python: list[str] = []
    ignored_parts = {"__pycache__", ".egg-info"}
    for directory in code_directories:
        for path in (ROOT / directory).rglob("*"):
            if not path.is_file() or any(part in ignored_parts or part.endswith(".egg-info") for part in path.parts):
                continue
            if path.suffix.lower() != ".py":
                non_python.append(str(path.relative_to(ROOT)))
    assert non_python == [], f"Executable project code must be Python: {non_python}"


def test_repository_contains_no_node_or_typescript_manifests() -> None:
    forbidden = [
        str(path.relative_to(ROOT))
        for path in repository_files()
        if path.name.lower() in FORBIDDEN_MANIFEST_NAMES
    ]
    assert forbidden == [], f"Node/TypeScript manifests are prohibited: {forbidden}"


def test_example_application_stack_is_python_only() -> None:
    target_config = (ROOT / "config" / "target-project.example.yaml").read_text(
        encoding="utf-8"
    )
    assert "language: python" in target_config
    assert "frontend: streamlit" in target_config
    assert "backend: fastapi" in target_config
    assert "browser: playwright-python" in target_config
    assert "react-typescript" not in target_config.lower()


def test_playwright_references_use_python_test_modules() -> None:
    text_files = [
        path
        for path in repository_files()
        if path.suffix.lower() in {".md", ".py", ".yaml", ".yml", ".toml"}
    ]
    invalid_refs: list[str] = []
    for path in text_files:
        content = path.read_text(encoding="utf-8", errors="replace")
        if (".spec" + ".ts") in content or (".spec" + ".js") in content:
            invalid_refs.append(str(path.relative_to(ROOT)))
    assert invalid_refs == [], f"Playwright references must use Python pytest modules: {invalid_refs}"
