from __future__ import annotations

import sqlite3

import pytest

from ai_sdlc.domain.workflow import (
    Action,
    FeatureRequest,
    InvalidTransitionError,
    Role,
    WorkflowState,
    WorkflowValidationError,
)
from ai_sdlc.infrastructure.sqlite_repository import SQLiteRepository
from ai_sdlc.services.workflow_service import WorkflowService
from ai_sdlc.services.requirements_service import RequirementsService
from ai_sdlc.services.architecture_service import ArchitectureService


@pytest.fixture
def repository(tmp_path):
    repo = SQLiteRepository(tmp_path / "orchestrator.db")
    repo.initialize()
    return repo


@pytest.fixture
def service(repository):
    return WorkflowService(repository)


def sample_request(feature_id: str = "AUTH-001") -> FeatureRequest:
    return FeatureRequest(
        feature_id=feature_id,
        title="User login",
        problem_statement="Registered users can sign in securely.",
        acceptance_criteria=(
            "AC-01: Valid credentials allow access.",
            "AC-02: Invalid credentials are rejected.",
        ),
    )


def progress_to_architecture(service, feature_id="AUTH-001"):
    service.apply(
        feature_id, Action.SUBMIT_FOR_BA_REVIEW, Role.BUSINESS_ANALYST,
        actor_id="BA-01", note="Requirements are ready for review.",
    )
    service.apply(
        feature_id, Action.APPROVE_BA, Role.BUSINESS_ANALYST,
        actor_id="BA-01", note="BA review completed.",
    )
    service.apply(
        feature_id, Action.APPROVE_SCOPE, Role.PRODUCT_OWNER,
        actor_id="PO-01", note="Scope approved.",
    )


def prepare_approved_architecture(repository, feature_id="AUTH-001"):
    requirements = RequirementsService(repository)
    requirements.create_requirement(
        requirement_id="REQ-AUTH-001", title="Secure user login",
        description="Registered users need secure authentication.",
        business_value="Protect private account data.", priority="high", created_by="REQUESTER-01",
    )
    requirements.create_story(
        story_id="US-AUTH-001", requirement_id="REQ-AUTH-001", title="Sign in",
        user_role="registered user", goal="authenticate with credentials",
        benefit="access my account safely", created_by="BA-01", actor_role="business_analyst",
    )
    requirements.add_acceptance_criterion(
        criterion_id="AC-AUTH-001", story_id="US-AUTH-001",
        description="Valid active credentials authenticate the user.", created_by="BA-01",
        actor_role="business_analyst",
    )
    requirements.create_test_case(
        test_case_id="TC-AUTH-001", title="Valid login succeeds",
        description="Submit active user credentials through the login endpoint.",
        test_level="api", created_by="QA-01", actor_role="qa_engineer",
    )
    requirements.submit_for_ba_review(
        "REQ-AUTH-001", actor_id="BA-01", note="Requirement package is complete.",
        actor_role="business_analyst",
    )
    requirements.approve_ba(
        "REQ-AUTH-001", actor_id="BA-01", note="BA review completed.",
        actor_role="business_analyst",
    )
    requirements.map_test_case(
        criterion_id="AC-AUTH-001", test_case_id="TC-AUTH-001", mapped_by="QA-01",
        actor_role="qa_engineer",
    )
    requirements.approve_po(
        "REQ-AUTH-001", actor_id="PO-01", note="Business scope and traceability accepted.",
        actor_role="product_owner",
    )

    architecture = ArchitectureService(repository)
    architecture.create_package(
        package_id="ARCH-AUTH-001", feature_id=feature_id,
        requirement_id="REQ-AUTH-001", created_by="ARCH-01", actor_role="architect",
    )
    for artifact_type in (
        "solution_overview", "component_design", "technical_design", "database_design",
        "api_contracts",
        "security_threat_model", "coding_standards", "test_driven_development_plan", "test_strategy",
        "deployment_rollback",
    ):
        architecture.add_artifact(
            package_id="ARCH-AUTH-001", artifact_type=artifact_type,
            title=artifact_type.replace("_", " ").title(),
            content=(f"The {artifact_type.replace('_', ' ')} defines the approved design, "
                     "implementation boundaries, validation evidence, and operational controls."),
            created_by="ARCH-01", actor_role="architect",
        )
    architecture.add_decision(
        package_id="ARCH-AUTH-001", decision_id="ADR-AUTH-001",
        title="Use a relational database", context="Authentication needs transactional identity data.",
        decision="Use PostgreSQL with normalized user and session tables.",
        consequences="Migrations and backups are required; transactions preserve consistency.",
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
        note="Independent architecture review passed.", evidence_uri="reviews/ARCH-AUTH-001.md",
        actor_role="architecture_reviewer",
    )


def test_feature_and_acceptance_criteria_survive_repository_restart(tmp_path):
    db_path = tmp_path / "durable.db"
    first_process = SQLiteRepository(db_path)
    first_process.initialize()
    first_process.create_feature(sample_request())

    second_process = SQLiteRepository(db_path)
    record = second_process.get_feature("AUTH-001")

    assert record is not None
    assert record.request.title == "User login"
    assert record.request.acceptance_criteria == sample_request().acceptance_criteria
    assert record.state == WorkflowState.INTAKE


def test_database_initialization_is_idempotent(repository):
    repository.initialize()
    repository.initialize()

    assert repository.get_feature("missing") is None


def test_workflow_transition_is_persisted_and_reloaded(service, repository):
    repository.create_feature(sample_request())

    event = service.apply(
        "AUTH-001", Action.SUBMIT_FOR_BA_REVIEW, Role.BUSINESS_ANALYST,
        actor_id="BA-01", note="Submitted for BA review.",
    )

    reloaded = repository.get_workflow("AUTH-001")
    assert reloaded is not None
    assert reloaded.state == WorkflowState.BA_REVIEW
    assert len(reloaded.history) == 1
    assert reloaded.history[0].event_id == event.event_id
    assert reloaded.history[0].actor_id == "BA-01"


def test_full_workflow_history_is_chronological_after_reload(service, repository):
    repository.create_feature(sample_request())
    progress_to_architecture(service)
    prepare_approved_architecture(repository)
    service.apply(
        "AUTH-001", Action.APPROVE_ARCHITECTURE, Role.ARCHITECT,
        actor_id="ARCH-01", note="Design approved.", evidence_uri="ARCH-AUTH-001",
    )

    workflow = repository.get_workflow("AUTH-001")
    assert workflow is not None
    assert workflow.state == WorkflowState.READY_FOR_DEVELOPMENT
    assert [event.event_id for event in workflow.history] == [1, 2, 3, 4]
    assert [event.to_state for event in workflow.history][-1] == WorkflowState.READY_FOR_DEVELOPMENT


def test_invalid_transition_is_not_written_to_database(service, repository):
    repository.create_feature(sample_request())

    with pytest.raises(InvalidTransitionError):
        service.apply(
            "AUTH-001", Action.START_DEVELOPMENT, Role.DEVELOPER,
            actor_id="DEV-01", note="Trying to skip required approvals.",
        )

    workflow = repository.get_workflow("AUTH-001")
    assert workflow is not None
    assert workflow.state == WorkflowState.INTAKE
    assert workflow.history == ()


def test_duplicate_feature_id_is_rejected(repository):
    repository.create_feature(sample_request())

    with pytest.raises(sqlite3.IntegrityError):
        repository.create_feature(sample_request())


def test_stale_workflow_cannot_overwrite_newer_database_state(repository):
    repository.create_feature(sample_request())
    stale_a = repository.get_workflow("AUTH-001")
    stale_b = repository.get_workflow("AUTH-001")
    assert stale_a is not None and stale_b is not None

    # First writer moves the feature from intake to BA review.
    service_a = WorkflowService(repository)
    service_a.apply(
        "AUTH-001", Action.SUBMIT_FOR_BA_REVIEW, Role.BUSINESS_ANALYST,
        actor_id="BA-01", note="First accepted update.",
    )

    # A second update based on the old state must fail instead of losing the first update.
    from ai_sdlc.domain.workflow import WorkflowEngine

    stale_event = WorkflowEngine().apply(
        stale_b, Action.SUBMIT_FOR_BA_REVIEW, Role.BUSINESS_ANALYST,
        actor_id="BA-02", note="Stale update.",
    )
    with pytest.raises(WorkflowValidationError, match="changed"):
        repository.save_transition(stale_event)

    latest = repository.get_workflow("AUTH-001")
    assert latest is not None
    assert latest.state == WorkflowState.BA_REVIEW
    assert len(latest.history) == 1


def test_resource_and_work_item_assignment_are_persisted(repository):
    repository.create_feature(sample_request())
    repository.create_resource("DEV-01", "Developer One", Role.DEVELOPER, capacity_points=8)
    repository.create_work_item(
        work_item_id="TASK-001",
        feature_id="AUTH-001",
        title="Implement login endpoint",
        item_type="task",
        priority="high",
        estimate_points=3,
    )
    repository.assign_work_item(
        work_item_id="TASK-001", resource_id="DEV-01", assigned_by="SCRUM-01"
    )

    resources = repository.list_resources()
    items = repository.list_work_items(feature_id="AUTH-001")
    assert resources[0].resource_id == "DEV-01"
    assert resources[0].capacity_points == 8
    assert items[0].work_item_id == "TASK-001"
    assert items[0].assignees == ("DEV-01",)


def test_work_item_cannot_reference_unknown_feature(repository):
    with pytest.raises(sqlite3.IntegrityError):
        repository.create_work_item(
            work_item_id="TASK-404",
            feature_id="UNKNOWN",
            title="Orphan task",
        )


def test_invalid_resource_role_is_rejected(repository):
    with pytest.raises(ValueError, match="role"):
        repository.create_resource("X-01", "Unknown role", "superuser")


def test_work_item_status_changes_are_audited_and_visible_in_workload(repository):
    repository.create_feature(sample_request())
    repository.create_resource("DEV-01", "Developer One", Role.DEVELOPER, capacity_points=8)
    repository.create_work_item(
        work_item_id="TASK-002", feature_id="AUTH-001", title="Implement login API",
        estimate_points=5,
    )
    repository.assign_work_item(
        work_item_id="TASK-002", resource_id="DEV-01", assigned_by="SCRUM-01"
    )
    repository.update_work_item_status(
        work_item_id="TASK-002", status="in_progress", actor_id="DEV-01",
        note="Started implementation.",
    )
    repository.update_work_item_status(
        work_item_id="TASK-002", status="done", actor_id="DEV-01",
        note="Implementation and unit tests completed.", evidence_uri="artifacts/unit-tests.xml",
    )

    history = repository.get_work_item_activity("TASK-002")
    workload = repository.resource_workload_summary()[0]
    assert [event["event_type"] for event in history] == [
        "created", "assigned", "status_changed", "status_changed"
    ]
    assert history[-1]["from_status"] == "in_progress"
    assert history[-1]["to_status"] == "done"
    assert history[-1]["evidence_uri"] == "artifacts/unit-tests.xml"
    assert workload["assigned_items"] == 1
    assert workload["completed_items"] == 1
    assert workload["open_items"] == 0


def test_work_item_status_update_requires_registered_active_actor(repository):
    repository.create_feature(sample_request())
    repository.create_work_item(work_item_id="TASK-003", feature_id="AUTH-001", title="Task")

    with pytest.raises(ValueError, match="not registered"):
        repository.update_work_item_status(
            work_item_id="TASK-003", status="in_progress", actor_id="DEV-404",
            note="Attempted update.",
        )


def test_work_item_status_update_rejects_missing_audit_note(repository):
    repository.create_feature(sample_request())
    repository.create_resource("DEV-01", "Developer One", Role.DEVELOPER)
    repository.create_work_item(work_item_id="TASK-004", feature_id="AUTH-001", title="Task")

    with pytest.raises(ValueError, match="audit note"):
        repository.update_work_item_status(
            work_item_id="TASK-004", status="in_progress", actor_id="DEV-01", note="  "
        )


def test_scrum_summary_counts_features_resources_and_open_defects(repository):
    repository.create_feature(sample_request())
    repository.create_resource("QA-01", "QA One", Role.QA_ENGINEER)
    repository.create_work_item(
        work_item_id="BUG-001", feature_id="AUTH-001", title="Incorrect password accepted",
        item_type="defect", priority="critical",
    )

    summary = repository.scrum_summary()
    assert summary["features"] == 1
    assert summary["active_resources"] == 1
    assert summary["open_defects"] == 1
    assert summary["todo"] == 1


def test_in_memory_sqlite_database_is_shared_across_repository_operations():
    repository = SQLiteRepository(":memory:")
    try:
        repository.initialize()
        repository.create_feature(sample_request("MEM-001"))
        record = repository.get_feature("MEM-001")
        assert record is not None
        assert record.request.title == "User login"
    finally:
        repository.close()
