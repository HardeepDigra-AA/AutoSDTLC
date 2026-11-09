from __future__ import annotations

import pytest

from ai_sdlc.domain.architecture import (
    ArchitecturePermissionError,
    ArchitectureValidationError,
)
from ai_sdlc.domain.workflow import (
    Action,
    FeatureRequest,
    Role,
    WorkflowState,
    WorkflowValidationError,
)
from ai_sdlc.infrastructure.sqlite_repository import SQLiteRepository
from ai_sdlc.services.architecture_service import ArchitectureService
from ai_sdlc.services.requirements_service import RequirementsService
from ai_sdlc.services.workflow_service import WorkflowService

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


def prepare_feature_and_requirement(repository: SQLiteRepository) -> None:
    repository.create_feature(
        FeatureRequest(
            feature_id="AUTH-001",
            title="User login",
            problem_statement="Registered users need secure access to their account.",
            acceptance_criteria=("Valid credentials authenticate the user.",),
        )
    )
    workflow = WorkflowService(repository)
    workflow.apply(
        "AUTH-001", Action.SUBMIT_FOR_BA_REVIEW, Role.BUSINESS_ANALYST,
        actor_id="BA-01", note="Feature request submitted.",
    )
    workflow.apply(
        "AUTH-001", Action.APPROVE_BA, Role.BUSINESS_ANALYST,
        actor_id="BA-01", note="BA review complete.",
    )
    workflow.apply(
        "AUTH-001", Action.APPROVE_SCOPE, Role.PRODUCT_OWNER,
        actor_id="PO-01", note="Business scope approved.",
    )

    requirements = RequirementsService(repository)
    requirements.create_requirement(
        requirement_id="REQ-AUTH-001", title="Secure user login",
        description="Registered users authenticate with valid credentials.",
        business_value="Protect private account information.", priority="high",
        created_by="REQUESTER-01",
    )
    requirements.create_story(
        story_id="US-AUTH-001", requirement_id="REQ-AUTH-001", title="Sign in",
        user_role="registered user", goal="sign in with valid credentials",
        benefit="access my private account", created_by="BA-01", actor_role="business_analyst",
    )
    requirements.add_acceptance_criterion(
        criterion_id="AC-AUTH-001", story_id="US-AUTH-001",
        description="Valid active credentials authenticate the user.", created_by="BA-01",
        actor_role="business_analyst",
    )
    requirements.create_test_case(
        test_case_id="TC-AUTH-001", title="Valid login succeeds",
        description="Submit valid active user credentials to the login API.",
        test_level="api", created_by="QA-01", actor_role="qa_engineer",
    )
    requirements.submit_for_ba_review(
        "REQ-AUTH-001", actor_id="BA-01", note="Requirement is ready.",
        actor_role="business_analyst",
    )
    requirements.approve_ba(
        "REQ-AUTH-001", actor_id="BA-01", note="BA approved.",
        actor_role="business_analyst",
    )
    requirements.map_test_case(
        criterion_id="AC-AUTH-001", test_case_id="TC-AUTH-001", mapped_by="QA-01",
        actor_role="qa_engineer",
    )
    requirements.approve_po(
        "REQ-AUTH-001", actor_id="PO-01", note="PO accepted scope and coverage.",
        actor_role="product_owner",
    )


def create_package(
    repository: SQLiteRepository, package_id: str = "ARCH-AUTH-001",
) -> ArchitectureService:
    service = ArchitectureService(repository)
    service.create_package(
        package_id=package_id, feature_id="AUTH-001", requirement_id="REQ-AUTH-001",
        created_by="ARCH-01", actor_role="architect",
    )
    return service


def add_complete_design(service: ArchitectureService, package_id: str = "ARCH-AUTH-001") -> None:
    for artifact_type in ARTIFACTS:
        service.add_artifact(
            package_id=package_id,
            artifact_type=artifact_type,
            title=artifact_type.replace("_", " ").title(),
            content=(
                f"The {artifact_type.replace('_', ' ')} defines the system boundary, "
                "approved implementation approach, validation controls, dependencies, "
                "operational ownership, and acceptance evidence."
            ),
            created_by="ARCH-01",
            actor_role="architect",
        )
    service.add_decision(
        package_id=package_id,
        decision_id=f"ADR-{package_id}",
        title="Use PostgreSQL for transactional identity data",
        context="Login and session state require consistent transactional persistence.",
        decision="Use PostgreSQL with normalized user, credential metadata and session tables.",
        consequences=(
            "Schema migrations, backup verification and least-privilege roles are required."
        ),
        created_by="ARCH-01",
        actor_role="architect",
    )
    service.map_story(
        package_id=package_id,
        story_id="US-AUTH-001",
        mapped_by="ARCH-01",
        actor_role="architect",
    )


def approve_package(service: ArchitectureService, package_id: str = "ARCH-AUTH-001") -> None:
    service.submit(
        package_id, actor_id="ARCH-01", note="All required design evidence is complete.",
        actor_role="architect",
    )
    service.review(
        package_id,
        outcome="approved",
        reviewer_id="ARCH-REVIEWER-01",
        note="Independent architecture review passed.",
        evidence_uri=f"reviews/{package_id}.md",
        actor_role="architecture_reviewer",
    )


@pytest.fixture
def repository(tmp_path):
    repo = SQLiteRepository(tmp_path / "architecture.db")
    repo.initialize()
    prepare_feature_and_requirement(repo)
    return repo


def test_architecture_package_requires_po_approved_requirement(tmp_path):
    repository = SQLiteRepository(tmp_path / "draft-requirement.db")
    repository.initialize()
    repository.create_feature(
        FeatureRequest("AUTH-001", "Login", "Secure login", ("Valid login succeeds.",))
    )
    workflow = WorkflowService(repository)
    workflow.apply(
        "AUTH-001", Action.SUBMIT_FOR_BA_REVIEW, Role.BUSINESS_ANALYST,
        actor_id="BA-01", note="Submit.",
    )
    workflow.apply(
        "AUTH-001", Action.APPROVE_BA, Role.BUSINESS_ANALYST,
        actor_id="BA-01", note="Approve BA.",
    )
    workflow.apply(
        "AUTH-001", Action.APPROVE_SCOPE, Role.PRODUCT_OWNER,
        actor_id="PO-01", note="Approve scope.",
    )
    RequirementsService(repository).create_requirement(
        requirement_id="REQ-001", title="Login", description="User login requirement.",
        business_value="Secure access.", priority="high", created_by="REQUESTER-01",
    )

    with pytest.raises(ValueError, match="must be Product Owner approved"):
        ArchitectureService(repository).create_package(
            package_id="ARCH-001", feature_id="AUTH-001", requirement_id="REQ-001",
            created_by="ARCH-01", actor_role="architect",
        )


def test_architecture_package_rejects_wrong_author_role(repository):
    with pytest.raises(ArchitecturePermissionError, match="requires role 'architect'"):
        ArchitectureService(repository).create_package(
            package_id="ARCH-001", feature_id="AUTH-001", requirement_id="REQ-AUTH-001",
            created_by="DEV-01", actor_role="developer",
        )


def test_submission_blocked_when_sections_adr_or_story_mapping_are_missing(repository):
    service = create_package(repository)
    service.add_artifact(
        package_id="ARCH-AUTH-001", artifact_type="solution_overview", title="Overview",
        content="The solution overview defines the system boundary and key components.",
        created_by="ARCH-01", actor_role="architect",
    )
    checklist = service.checklist("ARCH-AUTH-001")
    assert checklist["complete"] is False
    assert len(checklist["missing_artifacts"]) == len(ARTIFACTS) - 1
    with pytest.raises(ValueError, match="missing design sections"):
        service.submit(
            "ARCH-AUTH-001", actor_id="ARCH-01", note="Try incomplete package.",
            actor_role="architect",
        )


def test_architecture_decision_and_story_mapping_are_mandatory(repository):
    service = create_package(repository)
    for artifact_type in ARTIFACTS:
        service.add_artifact(
            package_id="ARCH-AUTH-001", artifact_type=artifact_type,
            title=artifact_type, content=(
                f"The {artifact_type} documents decisions, constraints, design details, "
                "security controls, implementation rules and verification evidence."
            ), created_by="ARCH-01", actor_role="architect",
        )
    with pytest.raises(ValueError, match="at least one Architecture Decision Record"):
        service.submit(
            "ARCH-AUTH-001", actor_id="ARCH-01", note="Missing ADR and story mapping.",
            actor_role="architect",
        )
    service.add_decision(
        package_id="ARCH-AUTH-001", decision_id="ADR-001", title="Database choice",
        context="The login data is transactional.", decision="Use PostgreSQL.",
        consequences="Use controlled schema migrations and backups.", created_by="ARCH-01",
        actor_role="architect",
    )
    with pytest.raises(ValueError, match="unmapped user stories"):
        service.submit(
            "ARCH-AUTH-001", actor_id="ARCH-01", note="Story mapping missing.",
            actor_role="architect",
        )


def test_story_from_another_requirement_cannot_be_mapped(repository):
    requirements = RequirementsService(repository)
    requirements.create_requirement(
        requirement_id="REQ-OTHER", title="Other", description="Another requirement.",
        business_value="Other value.", priority="low", created_by="REQUESTER-01",
    )
    requirements.create_story(
        story_id="US-OTHER", requirement_id="REQ-OTHER", title="Other story",
        user_role="user", goal="do another thing", benefit="get another benefit",
        created_by="BA-01", actor_role="business_analyst",
    )
    service = create_package(repository)
    with pytest.raises(ValueError, match="does not belong to requirement"):
        service.map_story(
            package_id="ARCH-AUTH-001", story_id="US-OTHER", mapped_by="ARCH-01",
            actor_role="architect",
        )


def test_architecture_review_requires_reviewer_role(repository):
    service = create_package(repository)
    add_complete_design(service)
    service.submit(
        "ARCH-AUTH-001", actor_id="ARCH-01", note="Ready for review.",
        actor_role="architect",
    )
    with pytest.raises(ArchitecturePermissionError, match="architecture_reviewer"):
        service.review(
            "ARCH-AUTH-001", outcome="approved", reviewer_id="PO-01",
            note="Wrong role review attempt.", evidence_uri="reviews/wrong-role.md",
            actor_role="product_owner",
        )


def test_author_cannot_approve_own_architecture_package(repository):
    service = create_package(repository)
    add_complete_design(service)
    service.submit(
        "ARCH-AUTH-001", actor_id="ARCH-01", note="Ready for review.",
        actor_role="architect",
    )
    with pytest.raises(ValueError, match="cannot approve their own"):
        service.review(
            "ARCH-AUTH-001", outcome="approved", reviewer_id="ARCH-01",
            note="Self approval attempt.", evidence_uri="reviews/self.md",
            actor_role="architecture_reviewer",
        )


def test_changes_requested_can_be_updated_and_resubmitted(repository):
    service = create_package(repository)
    add_complete_design(service)
    service.submit(
        "ARCH-AUTH-001", actor_id="ARCH-01", note="First submission.",
        actor_role="architect",
    )
    service.review(
        "ARCH-AUTH-001", outcome="changes_requested", reviewer_id="ARCH-REVIEWER-01",
        note="Add a more explicit rollback procedure.", evidence_uri="reviews/first.md",
        actor_role="architecture_reviewer",
    )
    assert service.get("ARCH-AUTH-001")["status"] == "changes_requested"
    service.add_artifact(
        package_id="ARCH-AUTH-001", artifact_type="deployment_rollback",
        title="Updated deployment and rollback", content=(
            "The deployment plan uses staged rollout, health checks, backward-compatible "
            "database migrations, rollback triggers and a verified recovery procedure."
        ), created_by="ARCH-01", actor_role="architect",
    )
    approve_package(service)
    result = service.get("ARCH-AUTH-001")
    assert result["status"] == "approved"
    assert len(result["reviews"]) == 2
    rollback_artifact = next(
        item for item in result["artifacts"]
        if item["artifact_type"] == "deployment_rollback"
    )
    assert rollback_artifact["revision_no"] == 2
    rollback_history = [
        item for item in result["artifact_history"]
        if item["artifact_type"] == "deployment_rollback"
    ]
    assert len(rollback_history) == 1
    assert "system boundary" in rollback_history[0]["content"]
    assert "staged rollout" in rollback_artifact["content"]


def test_approved_architecture_package_is_immutable(repository):
    service = create_package(repository)
    add_complete_design(service)
    approve_package(service)
    with pytest.raises(ValueError, match="is not editable"):
        service.add_artifact(
            package_id="ARCH-AUTH-001",
            artifact_type="test_driven_development_plan",
            title="Late change",
            content="A late change must be made through a new version and review.",
            created_by="ARCH-01", actor_role="architect",
        )


def test_feature_cannot_approve_architecture_without_package(repository):
    with pytest.raises(WorkflowValidationError, match="independently reviewed"):
        WorkflowService(repository).apply(
            "AUTH-001", Action.APPROVE_ARCHITECTURE, Role.ARCHITECT,
            actor_id="ARCH-01", note="No package exists.", evidence_uri="missing-package",
        )
    assert repository.get_workflow("AUTH-001").state == WorkflowState.ARCHITECTURE_REVIEW


def test_development_requires_approved_package_and_exact_package_reference(repository):
    architecture = create_package(repository)
    add_complete_design(architecture)
    approve_package(architecture)
    workflow = WorkflowService(repository)

    with pytest.raises(WorkflowValidationError, match="must identify the approved package"):
        workflow.apply(
            "AUTH-001", Action.APPROVE_ARCHITECTURE, Role.ARCHITECT,
            actor_id="ARCH-01", note="Wrong evidence link.", evidence_uri="docs/architecture.md",
        )
    event = workflow.apply(
        "AUTH-001", Action.APPROVE_ARCHITECTURE, Role.ARCHITECT,
        actor_id="ARCH-01", note="Approved package is attached.", evidence_uri="ARCH-AUTH-001",
    )
    assert event.to_state == WorkflowState.READY_FOR_DEVELOPMENT
    start = workflow.apply(
        "AUTH-001", Action.START_DEVELOPMENT, Role.DEVELOPER,
        actor_id="DEV-01", note="Begin implementation from approved TDD.",
    )
    assert start.to_state == WorkflowState.DEVELOPMENT


def test_replacing_approved_architecture_supersedes_the_old_version(repository):
    first = create_package(repository)
    add_complete_design(first)
    approve_package(first)

    second = create_package(repository, "ARCH-AUTH-002")
    add_complete_design(second, "ARCH-AUTH-002")
    approve_package(second, "ARCH-AUTH-002")

    assert first.get("ARCH-AUTH-001")["status"] == "superseded"
    assert second.get("ARCH-AUTH-002")["status"] == "approved"


def test_artifact_can_be_imported_from_markdown_file(repository, tmp_path):
    content_file = tmp_path / "database-design.md"
    content_file.write_text(
        "# Database design\n\nUse normalized user and session tables with reviewed migrations, "
        "foreign keys, indexes and backup verification.",
        encoding="utf-8",
    )
    service = create_package(repository)
    artifact = service.add_artifact_from_file(
        package_id="ARCH-AUTH-001", artifact_type="database_design",
        title="Database design", content_file=str(content_file), created_by="ARCH-01",
        actor_role="architect",
    )
    assert artifact["source_uri"] == str(content_file.resolve())
    assert "normalized user and session tables" in artifact["content"]


def test_artifact_placeholder_is_rejected(repository):
    service = create_package(repository)
    with pytest.raises(ArchitectureValidationError, match="Placeholder content"):
        service.add_artifact(
            package_id="ARCH-AUTH-001", artifact_type="test_driven_development_plan", title="TDD",
            content="TBD", created_by="ARCH-01", actor_role="architect",
        )


def test_architecture_package_and_audit_history_survive_database_restart(tmp_path):
    database = tmp_path / "durable-architecture.db"
    first = SQLiteRepository(database)
    first.initialize()
    prepare_feature_and_requirement(first)
    service = create_package(first)
    add_complete_design(service)
    approve_package(service)

    second = SQLiteRepository(database)
    second.initialize()
    reloaded = ArchitectureService(second).get("ARCH-AUTH-001")
    assert reloaded["status"] == "approved"
    assert len(reloaded["artifacts"]) == len(ARTIFACTS)
    assert len(reloaded["decisions"]) == 1
    assert len(reloaded["reviews"]) == 1
    assert len(reloaded["events"]) >= 13
