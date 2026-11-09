from __future__ import annotations

from ai_sdlc.cli import main


def test_cli_can_create_and_show_a_feature(tmp_path, capsys):
    database = str(tmp_path / "cli.db")
    assert main(["--db", database, "init-db"]) == 0
    assert main([
        "--db", database, "feature", "create",
        "--id", "AUTH-CLI-001",
        "--title", "Login",
        "--problem", "Users need to sign in.",
        "--ac", "AC-01: Valid login succeeds.",
        "--ac", "AC-02: Invalid login fails.",
    ]) == 0
    create_output = capsys.readouterr().out
    assert "Created AUTH-CLI-001" in create_output

    assert main(["--db", database, "feature", "show", "AUTH-CLI-001"]) == 0
    output = capsys.readouterr().out
    assert "Feature: AUTH-CLI-001" in output
    assert "AC-001" in output
    assert "No transitions recorded" in output


def test_cli_enforces_workflow_gate_and_persists_accepted_transition(tmp_path, capsys):
    database = str(tmp_path / "cli-workflow.db")
    main(["--db", database, "feature", "create", "--id", "AUTH-CLI-002",
          "--title", "Login", "--problem", "Users sign in.", "--ac", "Valid login works."])

    rejected = main([
        "--db", database, "feature", "transition", "AUTH-CLI-002", "start_development",
        "--unsafe-local-demo", "--unsafe-local-demo-role", "developer",
        "--unsafe-local-demo-actor-id", "DEV-01", "--note", "Skip gates.",
    ])
    assert rejected == 1
    assert "requires state" in capsys.readouterr().err

    accepted = main([
        "--db", database, "feature", "transition", "AUTH-CLI-002", "submit_for_ba_review",
        "--unsafe-local-demo", "--unsafe-local-demo-role", "business_analyst",
        "--unsafe-local-demo-actor-id", "BA-01", "--note", "BA submitted.",
    ])
    assert accepted == 0
    assert "Accepted event #1" in capsys.readouterr().out


def test_cli_tracks_resource_assignment_status_and_scrum_report(tmp_path, capsys):
    database = str(tmp_path / "cli-scrum.db")
    assert main([
        "--db", database, "feature", "create", "--id", "AUTH-CLI-003",
        "--title", "Login", "--problem", "Users sign in.", "--ac", "Login works.",
    ]) == 0
    assert main([
        "--db", database, "resource", "add", "--id", "DEV-01", "--name", "Developer One",
        "--role", "developer", "--capacity", "8",
    ]) == 0
    assert main([
        "--db", database, "work-item", "create", "--id", "TASK-CLI-001",
        "--feature", "AUTH-CLI-003", "--title", "Build login endpoint", "--estimate", "3",
    ]) == 0
    assert main([
        "--db", database, "work-item", "assign", "--id", "TASK-CLI-001",
        "--resource", "DEV-01", "--assigned-by", "SCRUM-01",
    ]) == 0
    assert main([
        "--db", database, "work-item", "status", "--id", "TASK-CLI-001",
        "--status", "in_progress", "--actor-id", "DEV-01", "--note", "Started work.",
    ]) == 0
    assert main([
        "--db", database, "work-item", "status", "--id", "TASK-CLI-001",
        "--status", "done", "--actor-id", "DEV-01", "--note", "Completed work.",
        "--evidence", "artifacts/task-001-tests.xml",
    ]) == 0
    assert main(["--db", database, "scrum", "summary"]) == 0
    report = capsys.readouterr().out
    assert "Features: 1" in report
    assert "DEV-01 (developer): 1 assigned, 1 completed, 0 open" in report


def test_cli_prints_work_item_audit_history(tmp_path, capsys):
    database = str(tmp_path / "cli-history.db")
    main(["--db", database, "feature", "create", "--id", "AUTH-CLI-004",
          "--title", "Login", "--problem", "Users sign in.", "--ac", "Login works."])
    main(["--db", database, "resource", "add", "--id", "DEV-01", "--name", "Developer One",
          "--role", "developer"])
    main(["--db", database, "work-item", "create", "--id", "TASK-CLI-002",
          "--feature", "AUTH-CLI-004", "--title", "Build form"])
    main(["--db", database, "work-item", "status", "--id", "TASK-CLI-002",
          "--status", "in_progress", "--actor-id", "DEV-01", "--note", "Started."])

    assert main(["--db", database, "work-item", "history", "TASK-CLI-002"]) == 0
    output = capsys.readouterr().out
    assert "created" in output
    assert "status_changed todo -> in_progress" in output
