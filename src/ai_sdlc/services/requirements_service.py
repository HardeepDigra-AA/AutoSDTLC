"""Use cases and role gates for the business requirements lifecycle."""

from __future__ import annotations

from typing import Any

from ai_sdlc.domain.requirements import (
    RequirementPermissionError,
    RequirementStatus,
    RequirementValidationError,
    require_non_empty,
    require_role,
)
from ai_sdlc.infrastructure.sqlite_repository import SQLiteRepository


class RequirementsService:
    """Coordinates BA, PO, and QA actions using deterministic role gates."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    def create_requirement(
        self,
        *,
        requirement_id: str,
        title: str,
        description: str,
        business_value: str,
        priority: str,
        created_by: str,
        actor_role: str = "requester",
    ) -> dict[str, Any]:
        require_role(actor_role, "requester")
        require_non_empty(created_by, "created_by")
        return self.repository.create_requirement(
            requirement_id=require_non_empty(requirement_id, "requirement_id"),
            title=require_non_empty(title, "title"),
            description=require_non_empty(description, "description"),
            business_value=require_non_empty(business_value, "business_value"),
            priority=priority,
            created_by=created_by,
        )

    def update_requirement(
        self,
        requirement_id: str,
        *,
        changed_by: str,
        change_note: str,
        actor_role: str,
        title: str | None = None,
        description: str | None = None,
        business_value: str | None = None,
        priority: str | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        if actor_role not in {"requester", "business_analyst"}:
            raise RequirementPermissionError(
                "Only the requester or Business Analyst may edit a draft."
            )
        require_non_empty(changed_by, "changed_by")
        require_non_empty(change_note, "change_note")
        changes = {
            key: value
            for key, value in {
                "title": title,
                "description": description,
                "business_value": business_value,
                "priority": priority,
            }.items()
            if value is not None
        }
        if not changes:
            raise RequirementValidationError("Provide at least one field to update.")
        for field_name, value in changes.items():
            if isinstance(value, str):
                changes[field_name] = require_non_empty(value, field_name)
        return self.repository.update_requirement(
            requirement_id,
            changes=changes,
            changed_by=changed_by,
            actor_role=actor_role,
            change_note=change_note,
            expected_version=expected_version,
        )

    def add_clarification(
        self, requirement_id: str, *, clarification_id: str, question: str, asked_by: str,
        actor_role: str,
    ) -> dict[str, Any]:
        require_role(actor_role, "business_analyst")
        return self.repository.add_requirement_clarification(
            requirement_id=requirement_id,
            clarification_id=require_non_empty(clarification_id, "clarification_id"),
            question=require_non_empty(question, "question"),
            asked_by=require_non_empty(asked_by, "asked_by"),
        )

    def answer_clarification(
        self, clarification_id: str, *, answer: str, answered_by: str, actor_role: str,
    ) -> dict[str, Any]:
        require_role(actor_role, "requester")
        return self.repository.answer_requirement_clarification(
            clarification_id=clarification_id,
            answer=require_non_empty(answer, "answer"),
            answered_by=require_non_empty(answered_by, "answered_by"),
        )

    def create_story(
        self,
        *, story_id: str, requirement_id: str, title: str, user_role: str,
        goal: str, benefit: str, created_by: str, actor_role: str,
    ) -> dict[str, Any]:
        require_role(actor_role, "business_analyst")
        return self.repository.create_user_story(
            story_id=require_non_empty(story_id, "story_id"),
            requirement_id=requirement_id,
            title=require_non_empty(title, "title"),
            user_role=require_non_empty(user_role, "user_role"),
            goal=require_non_empty(goal, "goal"),
            benefit=require_non_empty(benefit, "benefit"),
            created_by=require_non_empty(created_by, "created_by"),
        )

    def add_acceptance_criterion(
        self, *, criterion_id: str, story_id: str, description: str, created_by: str,
        actor_role: str,
    ) -> dict[str, Any]:
        require_role(actor_role, "business_analyst")
        return self.repository.create_story_acceptance_criterion(
            criterion_id=require_non_empty(criterion_id, "criterion_id"),
            story_id=story_id,
            description=require_non_empty(description, "description"),
            created_by=require_non_empty(created_by, "created_by"),
        )

    def create_test_case(
        self, *, test_case_id: str, title: str, description: str, test_level: str,
        created_by: str, actor_role: str, automation_reference: str | None = None,
    ) -> dict[str, Any]:
        require_role(actor_role, "qa_engineer")
        return self.repository.create_traceability_test_case(
            test_case_id=require_non_empty(test_case_id, "test_case_id"),
            title=require_non_empty(title, "title"),
            description=require_non_empty(description, "description"),
            test_level=test_level,
            created_by=require_non_empty(created_by, "created_by"),
            automation_reference=automation_reference,
        )

    def map_test_case(
        self, *, criterion_id: str, test_case_id: str, mapped_by: str, actor_role: str,
    ) -> dict[str, Any]:
        require_role(actor_role, "qa_engineer")
        return self.repository.map_test_case_to_criterion(
            criterion_id=criterion_id,
            test_case_id=test_case_id,
            mapped_by=require_non_empty(mapped_by, "mapped_by"),
        )

    def submit_for_ba_review(
        self, requirement_id: str, *, actor_id: str, note: str, actor_role: str,
    ) -> dict[str, Any]:
        require_role(actor_role, "business_analyst")
        return self.repository.transition_requirement(
            requirement_id,
            to_status=RequirementStatus.BA_REVIEW,
            actor_id=require_non_empty(actor_id, "actor_id"),
            actor_role=actor_role,
            note=require_non_empty(note, "note"),
            allowed_from={RequirementStatus.DRAFT, RequirementStatus.CHANGES_REQUESTED,
                         RequirementStatus.CLARIFICATION_REQUIRED},
            event_type="submitted_for_ba_review",
            validate_submission=True,
        )

    def approve_ba(
        self, requirement_id: str, *, actor_id: str, note: str, actor_role: str,
    ) -> dict[str, Any]:
        require_role(actor_role, "business_analyst")
        return self.repository.transition_requirement(
            requirement_id,
            to_status=RequirementStatus.PO_REVIEW,
            actor_id=require_non_empty(actor_id, "actor_id"),
            actor_role=actor_role,
            note=require_non_empty(note, "note"),
            allowed_from={RequirementStatus.BA_REVIEW},
            event_type="ba_approved",
        )

    def approve_po(
        self, requirement_id: str, *, actor_id: str, note: str, actor_role: str,
    ) -> dict[str, Any]:
        require_role(actor_role, "product_owner")
        return self.repository.transition_requirement(
            requirement_id,
            to_status=RequirementStatus.APPROVED,
            actor_id=require_non_empty(actor_id, "actor_id"),
            actor_role=actor_role,
            note=require_non_empty(note, "note"),
            allowed_from={RequirementStatus.PO_REVIEW},
            event_type="po_approved",
            validate_traceability=True,
            approve_stories=True,
        )

    def request_changes(
        self, requirement_id: str, *, actor_id: str, note: str, actor_role: str,
    ) -> dict[str, Any]:
        require_role(actor_role, "product_owner")
        return self.repository.transition_requirement(
            requirement_id,
            to_status=RequirementStatus.CHANGES_REQUESTED,
            actor_id=require_non_empty(actor_id, "actor_id"),
            actor_role=actor_role,
            note=require_non_empty(note, "note"),
            allowed_from={RequirementStatus.PO_REVIEW},
            event_type="po_requested_changes",
        )

    def get_traceability(self, requirement_id: str) -> dict[str, Any]:
        return self.repository.get_requirement_traceability(requirement_id)
