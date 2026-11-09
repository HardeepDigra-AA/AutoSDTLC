from __future__ import annotations

from ai_sdlc.cli import main
from ai_sdlc.infrastructure.sqlite_repository import SQLiteRepository


def test_cli_bootstrap_create_agent_and_secure_transition(tmp_path, monkeypatch, capsys):
    db = str(tmp_path / "secure-cli.db")
    assert main([
        "--db", db, "agent", "bootstrap-admin",
        "--id", "ORCH-CLI", "--name", "CLI Administrator",
    ]) == 0
    bootstrap_output = capsys.readouterr().out
    admin_token = bootstrap_output.strip().splitlines()[-1]
    assert admin_token.startswith("aisdlc.")
    monkeypatch.setenv("AI_SDLC_ADMIN_TOKEN", admin_token)

    assert main([
        "--db", db, "agent", "create", "--id", "BA-CLI-01",
        "--name", "Business Analyst One", "--role", "business_analyst",
    ]) == 0
    create_output = capsys.readouterr().out
    ba_token = create_output.strip().splitlines()[-1]
    assert ba_token.startswith("aisdlc.")
    monkeypatch.setenv("AI_SDLC_AGENT_TOKEN", ba_token)

    assert main([
        "--db", db, "feature", "create", "--id", "AUTH-SEC-CLI-001",
        "--title", "Secure login", "--problem", "Users need secure login.",
        "--ac", "Valid users can sign in.",
    ]) == 0
    capsys.readouterr()

    assert main([
        "--db", db, "feature", "transition", "AUTH-SEC-CLI-001",
        "submit_for_ba_review", "--note", "Submitted with authenticated BA identity.",
    ]) == 0
    assert "Accepted event #1" in capsys.readouterr().out

    repo = SQLiteRepository(db)
    repo.initialize()
    workflow = repo.get_workflow("AUTH-SEC-CLI-001")
    assert workflow is not None
    assert workflow.history[0].actor_id == "BA-CLI-01"
    assert workflow.history[0].actor_role.value == "business_analyst"

    assert main([
        "--db", db, "auth", "verify", "--require-scope", "requirements.write",
    ]) == 0
    assert "Authenticated: BA-CLI-01" in capsys.readouterr().out


def test_cli_feature_transition_requires_token_or_explicit_unsafe_local_demo(tmp_path, capsys):
    db = str(tmp_path / "transition-cli.db")
    assert main([
        "--db", db, "feature", "create", "--id", "AUTH-SEC-CLI-002",
        "--title", "Secure login", "--problem", "Users need secure login.",
        "--ac", "Valid users can sign in.",
    ]) == 0
    capsys.readouterr()

    result = main([
        "--db", db, "feature", "transition", "AUTH-SEC-CLI-002",
        "submit_for_ba_review", "--note", "No token.",
    ])
    assert result == 1
    assert "No token found" in capsys.readouterr().err


def test_cli_agent_create_requires_authenticated_admin(tmp_path, monkeypatch, capsys):
    db = str(tmp_path / "admin-cli.db")
    assert main([
        "--db", db, "agent", "bootstrap-admin", "--id", "ORCH-CLI-2",
        "--name", "CLI Admin",
    ]) == 0
    admin_token = capsys.readouterr().out.strip().splitlines()[-1]
    monkeypatch.setenv("AI_SDLC_ADMIN_TOKEN", admin_token)

    # A developer token is not allowed to register more identities.
    assert main([
        "--db", db, "agent", "create", "--id", "DEV-CLI-01",
        "--name", "Developer One", "--role", "developer",
    ]) == 0
    developer_token = capsys.readouterr().out.strip().splitlines()[-1]
    monkeypatch.setenv("AI_SDLC_ADMIN_TOKEN", developer_token)

    result = main([
        "--db", db, "agent", "create", "--id", "DEV-CLI-02",
        "--name", "Developer Two", "--role", "developer",
    ])
    assert result == 1
    assert "identity.manage" in capsys.readouterr().err


def test_m4_database_upgrades_to_m5_identity_and_github_schema(tmp_path):
    db = SQLiteRepository(tmp_path / "m4-upgrade.db")
    db.initialize()
    with db._connection() as connection:
        for table in (
            "github_ci_checks", "github_pr_reviews", "github_pull_requests",
            "github_workspaces", "github_repositories",
        ):
            connection.execute(f"DROP TABLE {table}")
        connection.execute("DROP TRIGGER trg_identity_events_no_update")
        connection.execute("DROP TRIGGER trg_identity_events_no_delete")
        connection.execute("DROP TABLE identity_events")
        connection.execute("DROP TABLE control_plane_bootstrap")
        connection.execute("DROP TABLE agent_credentials")
        connection.execute("DROP TABLE agent_identities")
        connection.execute("DELETE FROM schema_migrations WHERE version = 4")

    db.initialize()
    with db._connection() as connection:
        versions = [row[0] for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()]
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert versions == [1, 2, 3, 4]
    assert "agent_credentials" in tables
    assert "github_pull_requests" in tables
