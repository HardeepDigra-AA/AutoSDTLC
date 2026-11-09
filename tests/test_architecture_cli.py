from __future__ import annotations

from ai_sdlc.cli import main

ARTIFACTS = (
    "solution_overview",
    "component_design",
    "technical_design",
    "database_design",
    "api_contracts",
    "security_threat_model",
    "coding_standards",
    "test_driven_development_plan",
    "test_strategy",
    "deployment_rollback",
)


def run(db: str, *args: str) -> int:
    return main(["--db", db, *args])


def test_cli_architecture_review_and_development_gate(tmp_path, capsys):
    db = str(tmp_path / "architecture-cli.db")
    assert run(
        db, "feature", "create", "--id", "AUTH-CLI-001", "--title", "Login",
        "--problem", "Users need secure access.", "--ac", "Valid active credentials work.",
    ) == 0
    for action, role, actor in (
        ("submit_for_ba_review", "business_analyst", "BA-01"),
        ("approve_ba", "business_analyst", "BA-01"),
        ("approve_scope", "product_owner", "PO-01"),
    ):
        assert run(
            db, "feature", "transition", "AUTH-CLI-001", action,
            "--unsafe-local-demo", "--unsafe-local-demo-role", role,
            "--unsafe-local-demo-actor-id", actor, "--note", f"Complete {action}.",
        ) == 0

    assert run(
        db, "requirement", "create", "--id", "REQ-CLI-AUTH-001",
        "--title", "Secure login", "--description", "Users authenticate with credentials.",
        "--business-value", "Protect account data.", "--created-by", "REQUESTER-01",
    ) == 0
    assert run(
        db, "requirement", "story", "--id", "US-CLI-AUTH-001",
        "--requirement", "REQ-CLI-AUTH-001", "--title", "Sign in", "--as-a", "user",
        "--i-want", "to sign in", "--so-that", "I can access my data", "--created-by", "BA-01",
    ) == 0
    assert run(
        db, "requirement", "criterion", "--id", "AC-CLI-AUTH-001",
        "--story", "US-CLI-AUTH-001", "--description", "Valid credentials grant access.",
        "--created-by", "BA-01",
    ) == 0
    assert run(
        db, "requirement", "submit-ba", "REQ-CLI-AUTH-001", "--actor-id", "BA-01",
        "--note", "BA submission.",
    ) == 0
    assert run(
        db, "requirement", "approve-ba", "REQ-CLI-AUTH-001", "--actor-id", "BA-01",
        "--note", "BA approval.",
    ) == 0
    assert run(
        db, "requirement", "test-case", "--id", "TC-CLI-AUTH-001",
        "--title", "Valid login", "--description", "Submit valid credentials to login API.",
        "--level", "api", "--created-by", "QA-01",
    ) == 0
    assert run(
        db, "requirement", "map-test", "--criterion", "AC-CLI-AUTH-001",
        "--test-case", "TC-CLI-AUTH-001", "--mapped-by", "QA-01",
    ) == 0
    assert run(
        db, "requirement", "approve-po", "REQ-CLI-AUTH-001", "--actor-id", "PO-01",
        "--note", "PO approval and AC coverage verified.",
    ) == 0

    assert run(
        db, "architecture", "create", "--id", "ARCH-CLI-AUTH-001",
        "--feature", "AUTH-CLI-001", "--requirement", "REQ-CLI-AUTH-001",
        "--created-by", "ARCH-01",
    ) == 0
    for artifact_type in ARTIFACTS:
        assert run(
            db, "architecture", "artifact", "--package", "ARCH-CLI-AUTH-001",
            "--type", artifact_type, "--title", artifact_type,
            "--content",
            (f"The {artifact_type} provides detailed design controls, risks, interfaces, "
             "implementation expectations and validation evidence."),
            "--created-by", "ARCH-01",
        ) == 0
    assert run(
        db, "architecture", "adr", "--id", "ADR-CLI-AUTH-001",
        "--package", "ARCH-CLI-AUTH-001", "--title", "Use PostgreSQL",
        "--context", "Login transactions need reliable persistence.",
        "--decision", "Use PostgreSQL for identity and session data.",
        "--consequences", "Use migrations, backups and least-privilege database roles.",
        "--created-by", "ARCH-01",
    ) == 0
    assert run(
        db, "architecture", "map-story", "--package", "ARCH-CLI-AUTH-001",
        "--story", "US-CLI-AUTH-001", "--mapped-by", "ARCH-01",
    ) == 0
    assert run(
        db, "architecture", "submit", "ARCH-CLI-AUTH-001", "--actor-id", "ARCH-01",
        "--note", "All mandatory architecture sections and story mappings are complete.",
    ) == 0
    assert run(
        db, "architecture", "review", "ARCH-CLI-AUTH-001", "--outcome", "approved",
        "--reviewer-id", "ARCH-REVIEWER-01", "--note", "Independent review passed.",
        "--evidence", "reviews/ARCH-CLI-AUTH-001.md",
    ) == 0
    assert run(
        db, "feature", "transition", "AUTH-CLI-001", "approve_architecture",
        "--unsafe-local-demo", "--unsafe-local-demo-role", "architect",
        "--unsafe-local-demo-actor-id", "ARCH-01", "--note", "Approve reviewed package.",
        "--evidence", "ARCH-CLI-AUTH-001",
    ) == 0
    assert run(
        db, "feature", "transition", "AUTH-CLI-001", "start_development",
        "--unsafe-local-demo", "--unsafe-local-demo-role", "developer",
        "--unsafe-local-demo-actor-id", "DEV-01", "--note", "Start from approved TDD.",
    ) == 0

    output = capsys.readouterr().out
    assert "Architecture package ARCH-CLI-AUTH-001 is now 'approved'." in output
    assert "ready_for_development -> development" in output
