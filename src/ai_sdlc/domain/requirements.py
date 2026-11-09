"""Domain types and validation rules for business requirements and traceability."""

from __future__ import annotations

from enum import StrEnum


class RequirementStatus(StrEnum):
    DRAFT = "draft"
    CLARIFICATION_REQUIRED = "clarification_required"
    BA_REVIEW = "ba_review"
    PO_REVIEW = "po_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    REJECTED = "rejected"


class RequirementError(Exception):
    """Base error for requirement lifecycle rule violations."""


class RequirementNotFoundError(RequirementError):
    """Raised when a requirement, story, criterion, or test case is missing."""


class RequirementPermissionError(RequirementError):
    """Raised when an actor lacks the role needed for an action."""


class RequirementValidationError(RequirementError):
    """Raised when a requirement package is incomplete or invalid."""


class RequirementConflictError(RequirementError):
    """Raised when an update conflicts with the latest requirement version."""


def require_role(actual_role: str, expected_role: str) -> None:
    if actual_role != expected_role:
        raise RequirementPermissionError(
            f"This action requires role '{expected_role}', not '{actual_role}'."
        )


def require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise RequirementValidationError(f"'{field_name}' is required.")
    return normalized
