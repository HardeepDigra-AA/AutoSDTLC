from __future__ import annotations

import sqlite3

import pytest

from ai_sdlc.domain.requirements import (
    RequirementPermissionError,
)
from ai_sdlc.infrastructure.sqlite_repository import SQLiteRepository
from ai_sdlc.services.requirements_service import RequirementsService


@pytest.fixture

def repository(tmp_path):
    repo = SQLiteRepository(tmp_path / "requirements.db")
    repo.initialize()
    return repo


@pytest.fixture

def service(repository):
    return RequirementsService(repository)


def create_requirement(service, requirement_id="REQ-AUTH-001"):
    return service.create_requirement(
        requirement_id=requirement_id,
        title="Secure user login",
        description="Registered users must sign in using valid credentials.",
        business_value="Protect user data and provide authenticated access.",
        priority="high",
        created_by="REQUESTER-01",
    )


def add_story_and_criteria(service, requirement_id="REQ-AUTH-001"):
    service.create_story(
        story_id="US-AUTH-001",
        requirement_id=requirement_id,
        title="Sign in with credentials",
        user_role="registered user",
        goal="sign in with my email and password",
        benefit="I can securely access my account",
        created_by="BA-01",
        actor_role="business_analyst",
    )
    service.add_acceptance_criterion(
        criterion_id="AC-AUTH-001",
        story_id="US-AUTH-001",
        description="Valid email and password authenticate the user.",
        created_by="BA-01",
        actor_role="business_analyst",
    )
    service.add_acceptance_criterion(
        criterion_id="AC-AUTH-002",
        story_id="US-AUTH-001",
        description="Invalid credentials are rejected without creating a session.",
        created_by="BA-01",
        actor_role="business_analyst",
    )


def submit_and_approve_ba(service, requirement_id="REQ-AUTH-001"):
    service.submit_for_ba_review(
        requirement_id, actor_id="BA-01", note="Requirement pack is complete.",
        actor_role="business_analyst",
    )
    service.approve_ba(
        requirement_id, actor_id="BA-01", note="BA reviewed the story and criteria.",
        actor_role="business_analyst",
    )


def add_test_case(service, test_case_id, title):
    return service.create_test_case(
        test_case_id=test_case_id,
        title=title,
        description=f"Verify {title.lower()}.",
        test_level="api",
        created_by="QA-02",
        actor_role="qa_engineer",
        automation_reference=f"tests/api/test_{test_case_id.lower()}.py",
    )


def test_requirement_create_persists_initial_immutable_version(repository, service):
    record = create_requirement(service)

    assert record["requirement_id"] == "REQ-AUTH-001"
    assert record["status"] == "draft"
    assert record["version"] == 1
    assert len(record["versions"]) == 1
    assert record["versions"][0]["change_note"] == "Initial requirement intake"


def test_requirement_updates_create_a_new_version(repository, service):
    create_requirement(service)
    updated = service.update_requirement(
        "REQ-AUTH-001",
        changed_by="REQUESTER-01",
        change_note="Clarified business outcome.",
        actor_role="requester",
        business_value="Reduce account compromise and support authenticated account access.",
        expected_version=1,
    )

    assert updated["version"] == 2
    assert len(updated["versions"]) == 2
    assert updated["versions"][0]["business_value"] != updated["versions"][1]["business_value"]
    assert updated["versions"][1]["change_note"] == "Clarified business outcome."


def test_stale_requirement_version_cannot_overwrite_newer_change(service):
    create_requirement(service)
    service.update_requirement(
        "REQ-AUTH-001", changed_by="REQUESTER-01", change_note="First update.",
        actor_role="requester", title="Login with email", expected_version=1,
    )

    with pytest.raises(ValueError, match="version changed"):
        service.update_requirement(
            "REQ-AUTH-001", changed_by="REQUESTER-02", change_note="Stale update.",
            actor_role="requester", title="Stale title", expected_version=1,
        )


def test_only_requester_or_ba_can_edit_draft(service):
    create_requirement(service)
    with pytest.raises(RequirementPermissionError):
        service.update_requirement(
            "REQ-AUTH-001", changed_by="DEV-01", change_note="Dev edit.",
            actor_role="developer", title="Developer changed title",
        )


def test_open_clarification_blocks_ba_submission(service):
    create_requirement(service)
    add_story_and_criteria(service)
    service.add_clarification(
        "REQ-AUTH-001", clarification_id="CLAR-AUTH-001",
        question="Should locked accounts be allowed to sign in?", asked_by="BA-01",
        actor_role="business_analyst",
    )

    with pytest.raises(ValueError, match=r"clarification\(s\) remain open"):
        service.submit_for_ba_review(
            "REQ-AUTH-001", actor_id="BA-01", note="Submitting despite open question.",
            actor_role="business_analyst",
        )


def test_answered_clarification_allows_ba_submission(service):
    create_requirement(service)
    add_story_and_criteria(service)
    service.add_clarification(
        "REQ-AUTH-001", clarification_id="CLAR-AUTH-002",
        question="Should locked accounts be allowed to sign in?", asked_by="BA-01",
        actor_role="business_analyst",
    )
    service.answer_clarification(
        "CLAR-AUTH-002", answer="No. Locked accounts must be denied access.",
        answered_by="REQUESTER-01", actor_role="requester",
    )

    result = service.submit_for_ba_review(
        "REQ-AUTH-001", actor_id="BA-01", note="All questions answered.",
        actor_role="business_analyst",
    )
    assert result["status"] == "ba_review"
    assert result["clarifications"][0]["status"] == "answered"


def test_ba_submission_requires_at_least_one_story(service):
    create_requirement(service)
    with pytest.raises(ValueError, match="at least one BA-owned user story"):
        service.submit_for_ba_review(
            "REQ-AUTH-001", actor_id="BA-01", note="Submit incomplete requirement.",
            actor_role="business_analyst",
        )


def test_ba_submission_requires_acceptance_criteria_for_each_story(service):
    create_requirement(service)
    service.create_story(
        story_id="US-AUTH-001", requirement_id="REQ-AUTH-001", title="Login",
        user_role="registered user", goal="sign in", benefit="access my account",
        created_by="BA-01", actor_role="business_analyst",
    )
    with pytest.raises(ValueError, match="without acceptance criteria"):
        service.submit_for_ba_review(
            "REQ-AUTH-001", actor_id="BA-01", note="Submit story without AC.",
            actor_role="business_analyst",
        )


def test_wrong_role_cannot_approve_ba(service):
    create_requirement(service)
    add_story_and_criteria(service)
    service.submit_for_ba_review(
        "REQ-AUTH-001", actor_id="BA-01", note="Ready for review.",
        actor_role="business_analyst",
    )
    with pytest.raises(RequirementPermissionError):
        service.approve_ba(
            "REQ-AUTH-001", actor_id="PO-01", note="Wrong approver.",
            actor_role="product_owner",
        )


def test_cannot_skip_ba_approval_and_go_directly_to_po(service):
    create_requirement(service)
    with pytest.raises(ValueError, match="Cannot move requirement"):
        service.approve_po(
            "REQ-AUTH-001", actor_id="PO-01", note="Skip all gates.",
            actor_role="product_owner",
        )


def test_test_case_mapping_is_restricted_to_qa_role(service):
    create_requirement(service)
    add_story_and_criteria(service)
    submit_and_approve_ba(service)
    add_test_case(service, "TC-AUTH-001", "Valid credentials succeed")

    with pytest.raises(RequirementPermissionError):
        service.map_test_case(
            criterion_id="AC-AUTH-001", test_case_id="TC-AUTH-001",
            mapped_by="DEV-01", actor_role="developer",
        )


def test_po_approval_is_blocked_until_every_ac_has_test_coverage(service):
    create_requirement(service)
    add_story_and_criteria(service)
    submit_and_approve_ba(service)
    add_test_case(service, "TC-AUTH-001", "Valid credentials succeed")
    service.map_test_case(
        criterion_id="AC-AUTH-001", test_case_id="TC-AUTH-001",
        mapped_by="QA-02", actor_role="qa_engineer",
    )

    with pytest.raises(ValueError, match="every acceptance criterion needs at least one"):
        service.approve_po(
            "REQ-AUTH-001", actor_id="PO-01", note="Attempt PO approval with gap.",
            actor_role="product_owner",
        )


def test_full_requirement_approval_requires_and_records_complete_traceability(service, repository):
    create_requirement(service)
    add_story_and_criteria(service)
    submit_and_approve_ba(service)
    add_test_case(service, "TC-AUTH-001", "Valid credentials succeed")
    add_test_case(service, "TC-AUTH-002", "Invalid credentials are rejected")
    service.map_test_case(
        criterion_id="AC-AUTH-001", test_case_id="TC-AUTH-001",
        mapped_by="QA-02", actor_role="qa_engineer",
    )
    service.map_test_case(
        criterion_id="AC-AUTH-002", test_case_id="TC-AUTH-002",
        mapped_by="QA-03", actor_role="qa_engineer",
    )
    result = service.approve_po(
        "REQ-AUTH-001", actor_id="PO-01", note="All ACs mapped and approved.",
        actor_role="product_owner",
    )

    trace = service.get_traceability("REQ-AUTH-001")
    assert result["status"] == "approved"
    assert trace["coverage_percent"] == 100
    assert trace["uncovered_criteria"] == []
    assert trace["stories"][0]["story"]["status"] == "approved"
    assert len(result["events"]) >= 5


def test_approved_requirement_is_read_only(service):
    create_requirement(service)
    add_story_and_criteria(service)
    submit_and_approve_ba(service)
    for criterion_id, tc_id in (
        ("AC-AUTH-001", "TC-AUTH-001"),
        ("AC-AUTH-002", "TC-AUTH-002"),
    ):
        add_test_case(service, tc_id, f"Verify {criterion_id}")
        service.map_test_case(
            criterion_id=criterion_id, test_case_id=tc_id, mapped_by="QA-02",
            actor_role="qa_engineer",
        )
    service.approve_po(
        "REQ-AUTH-001", actor_id="PO-01", note="Approved.", actor_role="product_owner",
    )

    with pytest.raises(ValueError, match="Only draft or changes-requested"):
        service.update_requirement(
            "REQ-AUTH-001", changed_by="REQUESTER-01", change_note="Late change.",
            actor_role="requester", title="Changed after approval",
        )


def test_traceability_brd_contains_story_ac_test_and_coverage(service, repository):
    create_requirement(service)
    add_story_and_criteria(service)
    submit_and_approve_ba(service)
    add_test_case(service, "TC-AUTH-001", "Valid credentials succeed")
    service.map_test_case(
        criterion_id="AC-AUTH-001", test_case_id="TC-AUTH-001",
        mapped_by="QA-02", actor_role="qa_engineer",
    )

    trace = service.get_traceability("REQ-AUTH-001")
    brd = repository.get_requirement_brd("REQ-AUTH-001")
    assert trace["coverage_percent"] == 50
    assert "US-AUTH-001" in brd
    assert "AC-AUTH-001" in brd
    assert "TC-AUTH-001" in brd
    assert "AC-AUTH-002" in brd
    assert "NOT MAPPED" in brd


def test_duplicate_requirement_and_duplicate_criterion_ids_are_rejected(repository, service):
    create_requirement(service)
    with pytest.raises(sqlite3.IntegrityError):
        create_requirement(service)
    add_story_and_criteria(service)
    with pytest.raises(sqlite3.IntegrityError):
        service.add_acceptance_criterion(
            criterion_id="AC-AUTH-001", story_id="US-AUTH-001",
            description="Duplicate ID.", created_by="BA-01", actor_role="business_analyst",
        )


def test_wrong_role_cannot_create_test_case(service):
    with pytest.raises(RequirementPermissionError):
        service.create_test_case(
            test_case_id="TC-001", title="Test", description="Test description.",
            test_level="api", created_by="DEV-01", actor_role="developer",
        )


def test_requirement_schema_migration_is_idempotent(repository):
    repository.initialize()
    repository.initialize()
    with repository._connection() as connection:
        versions = [row[0] for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()]
    assert versions == [1, 2, 3, 4]


def test_duplicate_traceability_mapping_is_idempotent(service):
    create_requirement(service)
    add_story_and_criteria(service)
    submit_and_approve_ba(service)
    add_test_case(service, "TC-AUTH-001", "Valid credentials succeed")
    first = service.map_test_case(
        criterion_id="AC-AUTH-001", test_case_id="TC-AUTH-001",
        mapped_by="QA-02", actor_role="qa_engineer",
    )
    events_after_first_map = len(service.get_traceability("REQ-AUTH-001")["requirement"]["events"])
    second = service.map_test_case(
        criterion_id="AC-AUTH-001", test_case_id="TC-AUTH-001",
        mapped_by="QA-03", actor_role="qa_engineer",
    )
    events_after_second_map = len(service.get_traceability("REQ-AUTH-001")["requirement"]["events"])

    assert first["mapped_by"] == second["mapped_by"] == "QA-02"
    assert events_after_first_map == events_after_second_map


def test_m3_migration_upgrades_existing_m2_database(repository):
    with repository._connection() as connection:
        connection.execute("DROP TABLE github_ci_checks")
        connection.execute("DROP TABLE github_pr_reviews")
        connection.execute("DROP TABLE github_pull_requests")
        connection.execute("DROP TABLE github_workspaces")
        connection.execute("DROP TABLE github_repositories")
        connection.execute("DROP TRIGGER trg_identity_events_no_update")
        connection.execute("DROP TRIGGER trg_identity_events_no_delete")
        connection.execute("DROP TABLE identity_events")
        connection.execute("DROP TABLE control_plane_bootstrap")
        connection.execute("DROP TABLE agent_credentials")
        connection.execute("DROP TABLE agent_identities")
        connection.execute("DELETE FROM schema_migrations WHERE version = 4")
        connection.execute("DROP TABLE architecture_events")
        connection.execute("DROP TABLE architecture_reviews")
        connection.execute("DROP TABLE architecture_story_map")
        connection.execute("DROP TABLE architecture_decisions")
        connection.execute("DROP TABLE architecture_artifacts")
        connection.execute("DROP TABLE architecture_packages")
        connection.execute("DELETE FROM schema_migrations WHERE version = 3")
        connection.execute("DROP TABLE criterion_test_case_map")
        connection.execute("DROP TABLE requirement_events")
        connection.execute("DROP TABLE traceability_test_cases")
        connection.execute("DROP TABLE story_acceptance_criteria")
        connection.execute("DROP TABLE user_stories")
        connection.execute("DROP TABLE requirement_clarifications")
        connection.execute("DROP TABLE requirement_versions")
        connection.execute("DROP TABLE business_requirements")
        connection.execute("DELETE FROM schema_migrations WHERE version = 2")

    repository.initialize()

    with repository._connection() as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        versions = [row[0] for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()]
    assert "business_requirements" in tables
    assert "criterion_test_case_map" in tables
    assert versions == [1, 2, 3, 4]
    assert "agent_identities" in tables
    assert "github_pull_requests" in tables


def test_workflow_approvals_do_not_increment_business_content_version(service):
    create_requirement(service)
    add_story_and_criteria(service)
    submitted = service.submit_for_ba_review(
        "REQ-AUTH-001", actor_id="BA-01", note="Ready for review.",
        actor_role="business_analyst",
    )
    ba_approved = service.approve_ba(
        "REQ-AUTH-001", actor_id="BA-01", note="BA approved.",
        actor_role="business_analyst",
    )

    assert submitted["version"] == 1
    assert ba_approved["version"] == 1
    assert len(ba_approved["versions"]) == 1


def test_multiple_clarifications_must_all_be_answered_before_submission(service):
    create_requirement(service)
    add_story_and_criteria(service)
    for clarification_id, question in (
        ("CLAR-AUTH-010", "Should locked accounts be denied?"),
        ("CLAR-AUTH-011", "Should login be case sensitive?"),
    ):
        service.add_clarification(
            "REQ-AUTH-001", clarification_id=clarification_id, question=question,
            asked_by="BA-01", actor_role="business_analyst",
        )

    service.answer_clarification(
        "CLAR-AUTH-010", answer="Yes, deny locked accounts.",
        answered_by="REQUESTER-01", actor_role="requester",
    )
    with pytest.raises(ValueError, match=r"1 clarification\(s\) remain open"):
        service.submit_for_ba_review(
            "REQ-AUTH-001", actor_id="BA-01", note="One clarification is still open.",
            actor_role="business_analyst",
        )

    service.answer_clarification(
        "CLAR-AUTH-011", answer="Email addresses are normalized to lowercase.",
        answered_by="REQUESTER-01", actor_role="requester",
    )
    approved_for_review = service.submit_for_ba_review(
        "REQ-AUTH-001", actor_id="BA-01", note="All clarification answers recorded.",
        actor_role="business_analyst",
    )
    assert approved_for_review["status"] == "ba_review"


def test_po_change_request_allows_versioned_update_and_ba_resubmission(service):
    create_requirement(service)
    add_story_and_criteria(service)
    submit_and_approve_ba(service)
    returned = service.request_changes(
        "REQ-AUTH-001", actor_id="PO-01", note="Clarify the locked-account behaviour.",
        actor_role="product_owner",
    )
    assert returned["status"] == "changes_requested"

    updated = service.update_requirement(
        "REQ-AUTH-001", changed_by="REQUESTER-01", change_note="PO change request 1.",
        actor_role="requester", description=(
            "Registered users must sign in using valid credentials; locked accounts are denied."
        ), expected_version=1,
    )
    assert updated["version"] == 2

    resubmitted = service.submit_for_ba_review(
        "REQ-AUTH-001", actor_id="BA-01", note="PO change incorporated.",
        actor_role="business_analyst",
    )
    assert resubmitted["status"] == "ba_review"
    assert resubmitted["version"] == 2
