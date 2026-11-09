"""Deterministic, role-aware feature workflow state machine.

This first increment deliberately uses only the Python standard library. Persistence,
GitHub operations, and LLM agent execution will be added behind separate adapters later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Final


class WorkflowState(StrEnum):
    INTAKE = "intake"
    BA_REVIEW = "ba_review"
    PO_REVIEW = "po_review"
    ARCHITECTURE_REVIEW = "architecture_review"
    READY_FOR_DEVELOPMENT = "ready_for_development"
    DEVELOPMENT = "development"
    QA_READY = "qa_ready"
    QA_EXECUTION = "qa_execution"
    DEFECT_FIX = "defect_fix"
    QA_RETEST = "qa_retest"
    REGRESSION = "regression"
    QA_SIGNOFF = "qa_signoff"
    PO_ACCEPTANCE = "po_acceptance"
    READY_FOR_RELEASE = "ready_for_release"
    RELEASED = "released"


class Role(StrEnum):
    BUSINESS_ANALYST = "business_analyst"
    PRODUCT_OWNER = "product_owner"
    ARCHITECT = "architect"
    ARCHITECTURE_REVIEWER = "architecture_reviewer"  # Independent human/peer approval.
    DEVELOPER = "developer"
    QA_ENGINEER = "qa_engineer"
    QA_LEAD = "qa_lead"
    RELEASE_MANAGER = "release_manager"
    SCRUM_MASTER = "scrum_master"  # Reporting and coordination; no approval authority.
    IDENTITY_ADMIN = "identity_admin"  # Control-plane operator; not a delivery-team seat.


class Action(StrEnum):
    SUBMIT_FOR_BA_REVIEW = "submit_for_ba_review"
    APPROVE_BA = "approve_ba"
    APPROVE_SCOPE = "approve_scope"
    APPROVE_ARCHITECTURE = "approve_architecture"
    START_DEVELOPMENT = "start_development"
    SUBMIT_TO_QA = "submit_to_qa"
    START_QA = "start_qa"
    REPORT_DEFECT = "report_defect"
    PASS_FEATURE_TESTS = "pass_feature_tests"
    SUBMIT_FIX_FOR_RETEST = "submit_fix_for_retest"
    REOPEN_DEFECT = "reopen_defect"
    CONFIRM_FIX = "confirm_fix"
    FAIL_REGRESSION = "fail_regression"
    PASS_REGRESSION = "pass_regression"
    APPROVE_QA_SIGNOFF = "approve_qa_signoff"
    APPROVE_PRODUCT_ACCEPTANCE = "approve_product_acceptance"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class FeatureRequest:
    """Business-facing request that starts a feature workflow."""

    feature_id: str
    title: str
    problem_statement: str
    acceptance_criteria: tuple[str, ...]

    def validate_for_ba_review(self) -> None:
        """Check the minimum information BA needs before formal review."""
        missing: list[str] = []
        if not self.feature_id.strip():
            missing.append("feature_id")
        if not self.title.strip():
            missing.append("title")
        if not self.problem_statement.strip():
            missing.append("problem_statement")
        if not self.acceptance_criteria:
            missing.append("acceptance_criteria")
        elif any(not criterion.strip() for criterion in self.acceptance_criteria):
            missing.append("non-empty acceptance criteria")

        if missing:
            raise WorkflowValidationError(
                "Cannot submit for BA review. Missing or invalid fields: " + ", ".join(missing)
            )


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    """Immutable audit record for one accepted workflow transition."""

    event_id: int
    feature_id: str
    action: Action
    actor_id: str
    actor_role: Role
    from_state: WorkflowState
    to_state: WorkflowState
    note: str
    evidence_uri: str | None
    occurred_at: datetime


@dataclass(slots=True)
class FeatureWorkflow:
    """Current state and read-only view of accepted audit events for one feature."""

    request: FeatureRequest
    _state: WorkflowState = field(default=WorkflowState.INTAKE, repr=False)
    _history: list[WorkflowEvent] = field(default_factory=list, repr=False)

    @property
    def state(self) -> WorkflowState:
        """Expose the state as read-only; only the workflow engine should change it."""
        return self._state

    @property
    def history(self) -> tuple[WorkflowEvent, ...]:
        """Return an immutable snapshot so callers cannot edit the event collection."""
        return tuple(self._history)


class WorkflowError(Exception):
    """Base exception for expected workflow rule violations."""


class InvalidTransitionError(WorkflowError):
    """Raised when an action is not allowed from the current workflow state."""


class PermissionDeniedError(WorkflowError):
    """Raised when the actor does not have the role required for an action."""


class WorkflowValidationError(WorkflowError):
    """Raised when required business data, notes, or evidence are missing."""


@dataclass(frozen=True, slots=True)
class TransitionRule:
    from_state: WorkflowState
    to_state: WorkflowState
    allowed_roles: frozenset[Role]
    requires_evidence: bool = False
    validates_feature_request: bool = False


RULES: Final[dict[Action, TransitionRule]] = {
    Action.SUBMIT_FOR_BA_REVIEW: TransitionRule(
        WorkflowState.INTAKE,
        WorkflowState.BA_REVIEW,
        frozenset({Role.BUSINESS_ANALYST}),
        validates_feature_request=True,
    ),
    Action.APPROVE_BA: TransitionRule(
        WorkflowState.BA_REVIEW,
        WorkflowState.PO_REVIEW,
        frozenset({Role.BUSINESS_ANALYST}),
    ),
    Action.APPROVE_SCOPE: TransitionRule(
        WorkflowState.PO_REVIEW,
        WorkflowState.ARCHITECTURE_REVIEW,
        frozenset({Role.PRODUCT_OWNER}),
    ),
    Action.APPROVE_ARCHITECTURE: TransitionRule(
        WorkflowState.ARCHITECTURE_REVIEW,
        WorkflowState.READY_FOR_DEVELOPMENT,
        frozenset({Role.ARCHITECT}),
        requires_evidence=True,
    ),
    Action.START_DEVELOPMENT: TransitionRule(
        WorkflowState.READY_FOR_DEVELOPMENT,
        WorkflowState.DEVELOPMENT,
        frozenset({Role.DEVELOPER}),
    ),
    Action.SUBMIT_TO_QA: TransitionRule(
        WorkflowState.DEVELOPMENT,
        WorkflowState.QA_READY,
        frozenset({Role.DEVELOPER}),
        requires_evidence=True,
    ),
    Action.START_QA: TransitionRule(
        WorkflowState.QA_READY,
        WorkflowState.QA_EXECUTION,
        frozenset({Role.QA_ENGINEER}),
    ),
    Action.REPORT_DEFECT: TransitionRule(
        WorkflowState.QA_EXECUTION,
        WorkflowState.DEFECT_FIX,
        frozenset({Role.QA_ENGINEER}),
        requires_evidence=True,
    ),
    Action.PASS_FEATURE_TESTS: TransitionRule(
        WorkflowState.QA_EXECUTION,
        WorkflowState.REGRESSION,
        frozenset({Role.QA_ENGINEER}),
        requires_evidence=True,
    ),
    Action.SUBMIT_FIX_FOR_RETEST: TransitionRule(
        WorkflowState.DEFECT_FIX,
        WorkflowState.QA_RETEST,
        frozenset({Role.DEVELOPER}),
        requires_evidence=True,
    ),
    Action.REOPEN_DEFECT: TransitionRule(
        WorkflowState.QA_RETEST,
        WorkflowState.DEFECT_FIX,
        frozenset({Role.QA_ENGINEER}),
        requires_evidence=True,
    ),
    Action.CONFIRM_FIX: TransitionRule(
        WorkflowState.QA_RETEST,
        WorkflowState.REGRESSION,
        frozenset({Role.QA_ENGINEER}),
        requires_evidence=True,
    ),
    Action.FAIL_REGRESSION: TransitionRule(
        WorkflowState.REGRESSION,
        WorkflowState.DEFECT_FIX,
        frozenset({Role.QA_ENGINEER}),
        requires_evidence=True,
    ),
    Action.PASS_REGRESSION: TransitionRule(
        WorkflowState.REGRESSION,
        WorkflowState.QA_SIGNOFF,
        frozenset({Role.QA_ENGINEER}),
        requires_evidence=True,
    ),
    Action.APPROVE_QA_SIGNOFF: TransitionRule(
        WorkflowState.QA_SIGNOFF,
        WorkflowState.PO_ACCEPTANCE,
        frozenset({Role.QA_LEAD}),
        requires_evidence=True,
    ),
    Action.APPROVE_PRODUCT_ACCEPTANCE: TransitionRule(
        WorkflowState.PO_ACCEPTANCE,
        WorkflowState.READY_FOR_RELEASE,
        frozenset({Role.PRODUCT_OWNER}),
        requires_evidence=True,
    ),
    Action.RELEASE: TransitionRule(
        WorkflowState.READY_FOR_RELEASE,
        WorkflowState.RELEASED,
        frozenset({Role.RELEASE_MANAGER}),
        requires_evidence=True,
    ),
}


class WorkflowEngine:
    """Validates and applies workflow actions; does not execute code or call an LLM."""

    def apply(
        self,
        workflow: FeatureWorkflow,
        action: Action,
        actor_role: Role,
        *,
        actor_id: str,
        note: str,
        evidence_uri: str | None = None,
    ) -> WorkflowEvent:
        rule = RULES[action]

        if workflow.state != rule.from_state:
            raise InvalidTransitionError(
                f"Action '{action.value}' requires state '{rule.from_state.value}', "
                f"but feature '{workflow.request.feature_id}' is in '{workflow.state.value}'."
            )

        if actor_role not in rule.allowed_roles:
            allowed = ", ".join(sorted(role.value for role in rule.allowed_roles))
            raise PermissionDeniedError(
                f"Role '{actor_role.value}' cannot perform '{action.value}'. "
                f"Allowed role(s): {allowed}."
            )

        if not actor_id.strip():
            raise WorkflowValidationError(
                "An actor_id is required to identify the responsible resource."
            )

        if not note.strip():
            raise WorkflowValidationError("An audit note is required for every workflow action.")

        if rule.validates_feature_request:
            workflow.request.validate_for_ba_review()

        if rule.requires_evidence and not (evidence_uri and evidence_uri.strip()):
            raise WorkflowValidationError(
                f"Action '{action.value}' requires an evidence link or artifact reference."
            )

        event = WorkflowEvent(
            event_id=len(workflow._history) + 1,
            feature_id=workflow.request.feature_id,
            action=action,
            actor_id=actor_id.strip(),
            actor_role=actor_role,
            from_state=workflow.state,
            to_state=rule.to_state,
            note=note.strip(),
            evidence_uri=evidence_uri.strip() if evidence_uri else None,
            occurred_at=datetime.now(timezone.utc),
        )

        workflow._state = rule.to_state
        workflow._history.append(event)
        return event
