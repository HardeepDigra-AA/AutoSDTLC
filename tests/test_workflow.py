from __future__ import annotations

import pytest

from ai_sdlc.domain.workflow import (
    Action,
    FeatureRequest,
    FeatureWorkflow,
    InvalidTransitionError,
    PermissionDeniedError,
    Role,
    WorkflowEngine,
    WorkflowState,
    WorkflowValidationError,
)


@pytest.fixture
def engine() -> WorkflowEngine:
    return WorkflowEngine()


@pytest.fixture
def workflow() -> FeatureWorkflow:
    request = FeatureRequest(
        feature_id="AUTH-001",
        title="User login",
        problem_statement="A registered user must be able to sign in securely.",
        acceptance_criteria=(
            "AC-01: A valid user can sign in.",
            "AC-02: An invalid password is rejected.",
            "AC-03: A disabled account cannot sign in.",
        ),
    )
    return FeatureWorkflow(request=request)


def apply(engine, workflow, action, role, note="Approved after review", evidence=None):
    actor_ids = {
        Role.BUSINESS_ANALYST: "BA-01",
        Role.PRODUCT_OWNER: "PO-01",
        Role.ARCHITECT: "ARCH-01",
        Role.DEVELOPER: "DEV-01",
        Role.QA_ENGINEER: "QA-01",
        Role.QA_LEAD: "QA-LEAD-01",
        Role.RELEASE_MANAGER: "RELEASE-01",
        Role.SCRUM_MASTER: "SCRUM-01",
    }
    return engine.apply(
        workflow,
        action,
        role,
        actor_id=actor_ids[role],
        note=note,
        evidence_uri=evidence,
    )


def reach_qa_execution(engine, workflow):
    apply(engine, workflow, Action.SUBMIT_FOR_BA_REVIEW, Role.BUSINESS_ANALYST)
    apply(engine, workflow, Action.APPROVE_BA, Role.BUSINESS_ANALYST)
    apply(engine, workflow, Action.APPROVE_SCOPE, Role.PRODUCT_OWNER)
    apply(
        engine,
        workflow,
        Action.APPROVE_ARCHITECTURE,
        Role.ARCHITECT,
        evidence="docs/architecture/auth-001-design.md",
    )
    apply(engine, workflow, Action.START_DEVELOPMENT, Role.DEVELOPER)
    apply(
        engine,
        workflow,
        Action.SUBMIT_TO_QA,
        Role.DEVELOPER,
        evidence="https://example.invalid/pull/12",
    )
    apply(engine, workflow, Action.START_QA, Role.QA_ENGINEER)


def complete_release(engine, workflow):
    apply(
        engine,
        workflow,
        Action.PASS_REGRESSION,
        Role.QA_ENGINEER,
        evidence="artifacts/regression-report.html",
    )
    apply(
        engine,
        workflow,
        Action.APPROVE_QA_SIGNOFF,
        Role.QA_LEAD,
        evidence="artifacts/qa-signoff.md",
    )
    apply(
        engine,
        workflow,
        Action.APPROVE_PRODUCT_ACCEPTANCE,
        Role.PRODUCT_OWNER,
        evidence="artifacts/po-acceptance.md",
    )
    apply(
        engine,
        workflow,
        Action.RELEASE,
        Role.RELEASE_MANAGER,
        evidence="https://example.invalid/deployments/42",
    )


def test_happy_path_reaches_released(engine, workflow):
    reach_qa_execution(engine, workflow)
    apply(
        engine,
        workflow,
        Action.PASS_FEATURE_TESTS,
        Role.QA_ENGINEER,
        evidence="artifacts/feature-test-report.html",
    )
    complete_release(engine, workflow)

    assert workflow.state == WorkflowState.RELEASED
    assert len(workflow.history) == 12


def test_defect_is_fixed_retested_and_regression_passes(engine, workflow):
    reach_qa_execution(engine, workflow)
    apply(
        engine,
        workflow,
        Action.REPORT_DEFECT,
        Role.QA_ENGINEER,
        note="AUTH-001 accepts an incorrect password.",
        evidence="artifacts/AUTH-001-failure.png",
    )
    apply(
        engine,
        workflow,
        Action.SUBMIT_FIX_FOR_RETEST,
        Role.DEVELOPER,
        note="Added server-side password verification.",
        evidence="https://example.invalid/pull/13",
    )
    apply(
        engine,
        workflow,
        Action.REOPEN_DEFECT,
        Role.QA_ENGINEER,
        note="Retest still reproduces the issue.",
        evidence="artifacts/AUTH-001-retest-failure.png",
    )
    apply(
        engine,
        workflow,
        Action.SUBMIT_FIX_FOR_RETEST,
        Role.DEVELOPER,
        note="Corrected the credential comparison and added a unit test.",
        evidence="https://example.invalid/pull/14",
    )
    apply(
        engine,
        workflow,
        Action.CONFIRM_FIX,
        Role.QA_ENGINEER,
        note="Original defect no longer reproduces.",
        evidence="artifacts/AUTH-001-retest-pass.html",
    )
    complete_release(engine, workflow)

    actions = [event.action for event in workflow.history]
    assert actions.count(Action.SUBMIT_FIX_FOR_RETEST) == 2
    assert workflow.state == WorkflowState.RELEASED


def test_wrong_role_cannot_submit_ba_review(engine, workflow):
    with pytest.raises(PermissionDeniedError):
        apply(engine, workflow, Action.SUBMIT_FOR_BA_REVIEW, Role.DEVELOPER)

    assert workflow.state == WorkflowState.INTAKE
    assert workflow.history == ()


def test_action_cannot_skip_required_workflow_stage(engine, workflow):
    with pytest.raises(InvalidTransitionError):
        apply(engine, workflow, Action.START_DEVELOPMENT, Role.DEVELOPER)

    assert workflow.state == WorkflowState.INTAKE


def test_ba_review_requires_acceptance_criteria(engine):
    incomplete = FeatureWorkflow(
        request=FeatureRequest(
            feature_id="AUTH-002",
            title="Password reset",
            problem_statement="A user can reset a forgotten password.",
            acceptance_criteria=(),
        )
    )

    with pytest.raises(WorkflowValidationError, match="acceptance_criteria"):
        apply(engine, incomplete, Action.SUBMIT_FOR_BA_REVIEW, Role.BUSINESS_ANALYST)

    assert incomplete.state == WorkflowState.INTAKE


def test_evidence_is_required_for_architecture_approval(engine, workflow):
    apply(engine, workflow, Action.SUBMIT_FOR_BA_REVIEW, Role.BUSINESS_ANALYST)
    apply(engine, workflow, Action.APPROVE_BA, Role.BUSINESS_ANALYST)
    apply(engine, workflow, Action.APPROVE_SCOPE, Role.PRODUCT_OWNER)

    with pytest.raises(WorkflowValidationError, match="evidence"):
        apply(engine, workflow, Action.APPROVE_ARCHITECTURE, Role.ARCHITECT)

    assert workflow.state == WorkflowState.ARCHITECTURE_REVIEW


def test_audit_note_is_required(engine, workflow):
    with pytest.raises(WorkflowValidationError, match="audit note"):
        apply(engine, workflow, Action.SUBMIT_FOR_BA_REVIEW, Role.BUSINESS_ANALYST, note=" ")

    assert workflow.state == WorkflowState.INTAKE


def test_every_accepted_transition_has_a_timestamped_audit_event(engine, workflow):
    event = apply(engine, workflow, Action.SUBMIT_FOR_BA_REVIEW, Role.BUSINESS_ANALYST)

    assert event.event_id == 1
    assert event.feature_id == "AUTH-001"
    assert event.from_state == WorkflowState.INTAKE
    assert event.to_state == WorkflowState.BA_REVIEW
    assert event.actor_id == "BA-01"
    assert event.actor_role == Role.BUSINESS_ANALYST
    assert event.occurred_at.tzinfo is not None
    assert workflow.history == (event,)


def test_qa_lead_must_approve_qa_signoff(engine, workflow):
    reach_qa_execution(engine, workflow)
    apply(
        engine,
        workflow,
        Action.PASS_FEATURE_TESTS,
        Role.QA_ENGINEER,
        evidence="artifacts/feature-tests.html",
    )
    apply(
        engine,
        workflow,
        Action.PASS_REGRESSION,
        Role.QA_ENGINEER,
        evidence="artifacts/regression.html",
    )

    with pytest.raises(PermissionDeniedError):
        apply(
            engine,
            workflow,
            Action.APPROVE_QA_SIGNOFF,
            Role.QA_ENGINEER,
            evidence="artifacts/signoff.md",
        )

    assert workflow.state == WorkflowState.QA_SIGNOFF


def test_audit_history_is_read_only(engine, workflow):
    apply(engine, workflow, Action.SUBMIT_FOR_BA_REVIEW, Role.BUSINESS_ANALYST)

    with pytest.raises(AttributeError):
        workflow.history.append("tampered")

    assert len(workflow.history) == 1


def test_workflow_state_is_read_only_to_callers(engine, workflow):
    with pytest.raises(AttributeError):
        workflow.state = WorkflowState.RELEASED

    assert workflow.state == WorkflowState.INTAKE


def test_actor_id_is_required_for_resource_level_tracking(engine, workflow):
    with pytest.raises(WorkflowValidationError, match="actor_id"):
        engine.apply(
            workflow,
            Action.SUBMIT_FOR_BA_REVIEW,
            Role.BUSINESS_ANALYST,
            actor_id=" ",
            note="BA prepared the initial story",
        )

    assert workflow.state == WorkflowState.INTAKE
