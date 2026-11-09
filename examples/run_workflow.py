"""Run a complete local workflow, including M3 traceability and the M4 design gate.

The evidence references in this learning example are illustrative strings. This script
exercises the workflow services and SQLite rules; it does not execute real builds, tests,
GitHub pull requests, deployments or authenticated identity checks.
"""

from ai_sdlc.domain.workflow import Action, FeatureRequest, Role
from ai_sdlc.infrastructure.sqlite_repository import SQLiteRepository
from ai_sdlc.services.architecture_service import ArchitectureService
from ai_sdlc.services.requirements_service import RequirementsService
from ai_sdlc.services.workflow_service import WorkflowService


def main() -> None:
    repository = SQLiteRepository(":memory:")
    repository.initialize()
    workflow_service = WorkflowService(repository)
    requirements = RequirementsService(repository)
    architecture = ArchitectureService(repository)

    try:
        repository.create_feature(
            FeatureRequest(
                feature_id="AUTH-001",
                title="User login",
                problem_statement="Registered users must authenticate securely.",
                acceptance_criteria=(
                    "Valid active credentials authenticate the user.",
                    "Invalid credentials are rejected.",
                ),
            )
        )

        def transition(
            action: Action,
            role: Role,
            actor: str,
            note: str,
            evidence: str | None = None,
        ):
            event = workflow_service.apply(
                "AUTH-001", action, role, actor_id=actor, note=note, evidence_uri=evidence,
            )
            print(
                f"{event.event_id:02d}. {event.actor_id:18s} {action.value:30s} "
                f"-> {event.to_state.value}"
            )

        transition(
            Action.SUBMIT_FOR_BA_REVIEW, Role.BUSINESS_ANALYST, "BA-01",
            "BA prepared the user story and acceptance criteria.",
        )
        transition(
            Action.APPROVE_BA, Role.BUSINESS_ANALYST, "BA-01", "BA review completed.",
        )
        transition(
            Action.APPROVE_SCOPE, Role.PRODUCT_OWNER, "PO-01", "PO approved business scope.",
        )

        requirements.create_requirement(
            requirement_id="REQ-AUTH-001",
            title="Secure user login",
            description="Registered users authenticate with valid credentials.",
            business_value="Protect private account information.",
            priority="high",
            created_by="REQUESTER-01",
        )
        requirements.create_story(
            story_id="US-AUTH-001", requirement_id="REQ-AUTH-001", title="Sign in",
            user_role="registered user", goal="sign in with credentials",
            benefit="access my account", created_by="BA-01", actor_role="business_analyst",
        )
        requirements.add_acceptance_criterion(
            criterion_id="AC-AUTH-001", story_id="US-AUTH-001",
            description="Valid active credentials authenticate the user.",
            created_by="BA-01", actor_role="business_analyst",
        )
        requirements.create_test_case(
            test_case_id="TC-AUTH-001", title="Valid login succeeds",
            description="Submit valid credentials to the login API.", test_level="api",
            created_by="QA-01", actor_role="qa_engineer",
        )
        requirements.submit_for_ba_review(
            "REQ-AUTH-001", actor_id="BA-01", note="Requirement is complete.",
            actor_role="business_analyst",
        )
        requirements.approve_ba(
            "REQ-AUTH-001", actor_id="BA-01", note="BA approved requirement.",
            actor_role="business_analyst",
        )
        requirements.map_test_case(
            criterion_id="AC-AUTH-001", test_case_id="TC-AUTH-001", mapped_by="QA-01",
            actor_role="qa_engineer",
        )
        requirements.approve_po(
            "REQ-AUTH-001", actor_id="PO-01", note="PO approved with complete AC mapping.",
            actor_role="product_owner",
        )

        architecture.create_package(
            package_id="ARCH-AUTH-001", feature_id="AUTH-001",
            requirement_id="REQ-AUTH-001", created_by="ARCH-01", actor_role="architect",
        )
        artifact_types = (
            "solution_overview", "component_design", "technical_design", "database_design",
            "api_contracts", "security_threat_model", "coding_standards",
            "test_driven_development_plan", "test_strategy", "deployment_rollback",
        )
        for artifact_type in artifact_types:
            architecture.add_artifact(
                package_id="ARCH-AUTH-001", artifact_type=artifact_type,
                title=artifact_type.replace("_", " ").title(),
                content=(
                    f"The {artifact_type.replace('_', ' ')} records the approved architecture, "
                    "implementation controls, risks, dependencies and verification evidence."
                ),
                created_by="ARCH-01", actor_role="architect",
            )
        architecture.add_decision(
            package_id="ARCH-AUTH-001", decision_id="ADR-AUTH-001",
            title="Use PostgreSQL for identity data",
            context="Login and session data require transactional persistence.",
            decision="Use PostgreSQL with normalized identity and session tables.",
            consequences="Use reviewed migrations, backups and least-privilege database roles.",
            created_by="ARCH-01", actor_role="architect",
        )
        architecture.map_story(
            package_id="ARCH-AUTH-001", story_id="US-AUTH-001", mapped_by="ARCH-01",
            actor_role="architect",
        )
        architecture.submit(
            "ARCH-AUTH-001", actor_id="ARCH-01", note="All design sections are complete.",
            actor_role="architect",
        )
        architecture.review(
            "ARCH-AUTH-001", outcome="approved", reviewer_id="ARCH-REVIEWER-01",
            note="Independent architecture review passed.",
            evidence_uri="reviews/ARCH-AUTH-001.md", actor_role="architecture_reviewer",
        )

        transition(
            Action.APPROVE_ARCHITECTURE, Role.ARCHITECT, "ARCH-01",
            "Approved architecture package is linked.", "ARCH-AUTH-001",
        )
        transition(
            Action.START_DEVELOPMENT, Role.DEVELOPER, "DEV-01",
            "Development starts from the approved Technical Design and test-first plan.",
        )
        transition(
            Action.SUBMIT_TO_QA, Role.DEVELOPER, "DEV-01",
            "Feature branch is ready for QA review.", "https://example.invalid/pull/1",
        )
        transition(
            Action.START_QA, Role.QA_ENGINEER, "QA-01", "QA execution started.",
        )
        transition(
            Action.REPORT_DEFECT, Role.QA_ENGINEER, "QA-01",
            "Invalid password was accepted; developer fix required.",
            "artifacts/AUTH-001-failure.png",
        )
        transition(
            Action.SUBMIT_FIX_FOR_RETEST, Role.DEVELOPER, "DEV-01",
            "Credential verification was corrected and unit test added.",
            "https://example.invalid/pull/2",
        )
        transition(
            Action.CONFIRM_FIX, Role.QA_ENGINEER, "QA-01",
            "Original failed test now passes on retest.", "artifacts/AUTH-001-retest-pass.html",
        )
        transition(
            Action.PASS_REGRESSION, Role.QA_ENGINEER, "QA-01",
            "Impacted regression and sanity tests passed.", "artifacts/AUTH-001-regression.html",
        )
        transition(
            Action.APPROVE_QA_SIGNOFF, Role.QA_LEAD, "QA-LEAD-01",
            "QA Lead reviewed the execution evidence.", "artifacts/AUTH-001-qa-signoff.md",
        )
        transition(
            Action.APPROVE_PRODUCT_ACCEPTANCE, Role.PRODUCT_OWNER, "PO-01",
            "PO confirmed the approved acceptance criteria.", "artifacts/AUTH-001-po-acceptance.md",
        )
        transition(
            Action.RELEASE, Role.RELEASE_MANAGER, "RELEASE-01",
            "Authorized staging release completed.", "https://example.invalid/deployments/1",
        )

        current = repository.get_workflow("AUTH-001")
        assert current is not None
        print(f"\nFeature AUTH-001 finished in state: {current.state.value}")
        print(f"Feature workflow events recorded: {len(current.history)}")
        print("Note: evidence references are illustrative; no real tests or deployment were run.")
    finally:
        repository.close()


if __name__ == "__main__":
    main()
