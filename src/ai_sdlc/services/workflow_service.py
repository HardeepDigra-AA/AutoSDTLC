"""Application service joining the deterministic workflow engine to persistence."""

from __future__ import annotations

from ai_sdlc.domain.workflow import (
    Action,
    Role,
    WorkflowEngine,
    WorkflowEvent,
    WorkflowValidationError,
)
from ai_sdlc.infrastructure.sqlite_repository import SQLiteRepository


class WorkflowService:
    """Load, validate, and atomically persist an individual feature transition."""

    def __init__(self, repository: SQLiteRepository, engine: WorkflowEngine | None = None) -> None:
        self.repository = repository
        self.engine = engine or WorkflowEngine()

    def apply(
        self,
        feature_id: str,
        action: Action,
        actor_role: Role,
        *,
        actor_id: str,
        note: str,
        evidence_uri: str | None = None,
    ) -> WorkflowEvent:
        workflow = self.repository.get_workflow(feature_id)
        if workflow is None:
            raise WorkflowValidationError(f"Feature '{feature_id}' does not exist.")

        # The domain state machine validates sequence and role. The application service
        # additionally verifies that a persisted, independently reviewed architecture
        # package exists before architecture approval or development can proceed.
        gate_state = {
            Action.APPROVE_ARCHITECTURE: "architecture_review",
            Action.START_DEVELOPMENT: "ready_for_development",
        }.get(action)
        if gate_state is not None and workflow.state.value == gate_state:
            architecture = self.repository.get_approved_architecture_for_feature(feature_id)
            if architecture is None:
                raise WorkflowValidationError(
                    f"Feature '{feature_id}' cannot proceed without an independently reviewed, "
                    "approved solution-architecture package."
                )
            if not architecture["requirement_is_approved"]:
                raise WorkflowValidationError(
                    "The business requirement linked to the approved architecture is no longer "
                    "Product Owner approved."
                )
            if action == Action.APPROVE_ARCHITECTURE and evidence_uri != architecture["package_id"]:
                raise WorkflowValidationError(
                    "Architecture approval evidence must identify the approved package "
                    f"'{architecture['package_id']}'."
                )
            if action == Action.START_DEVELOPMENT:
                latest_architecture_approval = next(
                    (
                        item
                        for item in reversed(workflow.history)
                        if item.action == Action.APPROVE_ARCHITECTURE
                    ),
                    None,
                )
                if (
                    latest_architecture_approval is None
                    or latest_architecture_approval.evidence_uri != architecture["package_id"]
                ):
                    raise WorkflowValidationError(
                        "The architecture package currently approved for this feature does not "
                        "match the package recorded in the feature's architecture approval event."
                    )

        event = self.engine.apply(
            workflow,
            action,
            actor_role,
            actor_id=actor_id,
            note=note,
            evidence_uri=evidence_uri,
        )
        self.repository.save_transition(event)
        return event
