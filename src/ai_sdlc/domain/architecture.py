"""Solution-architecture domain vocabulary and deterministic completeness rules."""

from __future__ import annotations

from enum import StrEnum


class ArchitectureError(Exception):
    """Base exception for architecture lifecycle violations."""


class ArchitecturePermissionError(ArchitectureError):
    """Raised when an actor does not hold the required architecture role."""


class ArchitectureValidationError(ArchitectureError):
    """Raised when an architecture package is incomplete or invalid."""


class ArchitectureConflictError(ArchitectureError):
    """Raised when an architecture package has changed since it was read."""


class ArchitectureStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class ArchitectureReviewOutcome(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"


class ArchitectureArtifactType(StrEnum):
    SOLUTION_OVERVIEW = "solution_overview"
    COMPONENT_DESIGN = "component_design"
    TECHNICAL_DESIGN = "technical_design"
    DATABASE_DESIGN = "database_design"
    API_CONTRACTS = "api_contracts"
    SECURITY_THREAT_MODEL = "security_threat_model"
    CODING_STANDARDS = "coding_standards"
    TDD_PLAN = "test_driven_development_plan"
    TEST_STRATEGY = "test_strategy"
    DEPLOYMENT_ROLLBACK = "deployment_rollback"


REQUIRED_ARTIFACT_TYPES = tuple(item.value for item in ArchitectureArtifactType)


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ArchitectureValidationError(f"'{field_name}' is required.")
    return normalized


def require_architect_role(actor_role: str) -> None:
    if actor_role != "architect":
        raise ArchitecturePermissionError(
            f"This action requires role 'architect', not '{actor_role}'."
        )


def require_reviewer_role(actor_role: str) -> None:
    if actor_role != "architecture_reviewer":
        raise ArchitecturePermissionError(
            f"Architecture approval requires role 'architecture_reviewer', not '{actor_role}'."
        )
