from __future__ import annotations

from ai_sdlc.cli import main


def test_requirement_cli_full_ba_po_traceability_flow(tmp_path, capsys):
    db = str(tmp_path / "requirement-cli.db")

    assert main([
        "--db", db, "requirement", "create", "--id", "REQ-CLI-001",
        "--title", "Login requirement", "--description", "Users need secure login.",
        "--business-value", "Protect user accounts.", "--priority", "high",
        "--created-by", "REQUESTER-01",
    ]) == 0
    assert "Created requirement REQ-CLI-001" in capsys.readouterr().out

    assert main([
        "--db", db, "requirement", "story", "--id", "US-CLI-001",
        "--requirement", "REQ-CLI-001", "--title", "Sign in", "--as-a", "user",
        "--i-want", "to sign in", "--so-that", "I can access my data",
        "--created-by", "BA-01",
    ]) == 0
    assert main([
        "--db", db, "requirement", "criterion", "--id", "AC-CLI-001",
        "--story", "US-CLI-001", "--description", "Valid credentials grant access.",
        "--created-by", "BA-01",
    ]) == 0
    assert main([
        "--db", db, "requirement", "submit-ba", "REQ-CLI-001",
        "--actor-id", "BA-01", "--note", "Story and criteria are complete.",
    ]) == 0
    assert main([
        "--db", db, "requirement", "approve-ba", "REQ-CLI-001",
        "--actor-id", "BA-01", "--note", "BA reviewed.",
    ]) == 0
    assert main([
        "--db", db, "requirement", "test-case", "--id", "TC-CLI-001",
        "--title", "Valid login works", "--description", "Submit correct credentials.",
        "--level", "api", "--created-by", "QA-02",
    ]) == 0
    assert main([
        "--db", db, "requirement", "map-test", "--criterion", "AC-CLI-001",
        "--test-case", "TC-CLI-001", "--mapped-by", "QA-02",
    ]) == 0
    assert main([
        "--db", db, "requirement", "approve-po", "REQ-CLI-001",
        "--actor-id", "PO-01", "--note", "Traceability verified.",
    ]) == 0

    assert main(["--db", db, "requirement", "show", "REQ-CLI-001"]) == 0
    output = capsys.readouterr().out
    assert "Status: approved" in output
    assert "Coverage: 1/1 (100.0%)" in output
    assert "TC-CLI-001" in output

    assert main(["--db", db, "requirement", "brd", "REQ-CLI-001"]) == 0
    brd = capsys.readouterr().out
    assert "# REQ-CLI-001" in brd
    assert "AC-CLI-001" in brd
    assert "TC-CLI-001" in brd
    assert "Requirement version history" in brd
    assert "Clarification log" in brd


def test_requirement_cli_rejects_po_approval_without_traceability(tmp_path, capsys):
    db = str(tmp_path / "requirement-cli-gate.db")
    main([
        "--db", db, "requirement", "create", "--id", "REQ-CLI-002",
        "--title", "Password reset", "--description", "Users reset passwords.",
        "--business-value", "Recover account access.", "--created-by", "REQUESTER-01",
    ])
    main([
        "--db", db, "requirement", "story", "--id", "US-CLI-002",
        "--requirement", "REQ-CLI-002", "--title", "Reset password", "--as-a", "user",
        "--i-want", "to reset my password", "--so-that", "I can recover access",
        "--created-by", "BA-01",
    ])
    main([
        "--db", db, "requirement", "criterion", "--id", "AC-CLI-002",
        "--story", "US-CLI-002", "--description", "A reset link is sent.",
        "--created-by", "BA-01",
    ])
    main([
        "--db", db, "requirement", "submit-ba", "REQ-CLI-002",
        "--actor-id", "BA-01", "--note", "Ready.",
    ])
    main([
        "--db", db, "requirement", "approve-ba", "REQ-CLI-002",
        "--actor-id", "BA-01", "--note", "Approved by BA.",
    ])

    result = main([
        "--db", db, "requirement", "approve-po", "REQ-CLI-002",
        "--actor-id", "PO-01", "--note", "Attempt without test mapping.",
    ])
    assert result == 1
    error_output = capsys.readouterr().err
    assert "every acceptance criterion needs at least one mapped test case" in error_output
