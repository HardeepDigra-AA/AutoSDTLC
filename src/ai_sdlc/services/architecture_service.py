"""Use cases and approval gates for solution architecture and TDD packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_sdlc.domain.architecture import (
    REQUIRED_ARTIFACT_TYPES,
    ArchitectureArtifactType,
    ArchitectureReviewOutcome,
    ArchitectureValidationError,
    require_architect_role,
    require_reviewer_role,
    require_text,
)
from ai_sdlc.infrastructure.sqlite_repository import SQLiteRepository


class ArchitectureService:
    """Coordinates architect authoring and independent architecture review."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    def create_package(
        self,
        *,
        package_id: str,
        feature_id: str,
        requirement_id: str,
        created_by: str,
        actor_role: str,
    ) -> dict[str, Any]:
        require_architect_role(actor_role)
        return self.repository.create_architecture_package(
            package_id=require_text(package_id, "package_id"),
            feature_id=require_text(feature_id, "feature_id"),
            requirement_id=require_text(requirement_id, "requirement_id"),
            created_by=require_text(created_by, "created_by"),
        )

    def add_artifact(
        self,
        *,
        package_id: str,
        artifact_type: str,
        title: str,
        content: str,
        created_by: str,
        actor_role: str,
        source_uri: str | None = None,
    ) -> dict[str, Any]:
        require_architect_role(actor_role)
        try:
            normalized_type = ArchitectureArtifactType(artifact_type).value
        except ValueError as error:
            allowed = ", ".join(REQUIRED_ARTIFACT_TYPES)
            raise ArchitectureValidationError(
                f"Unsupported artifact type '{artifact_type}'. Allowed: {allowed}."
            ) from error
        normalized_content = require_text(content, "content")
        if normalized_content.lower().strip() in {"tbd", "todo", "to be decided"}:
            raise ArchitectureValidationError(
                "Placeholder content is not valid architecture evidence."
            )
        if len(normalized_content) < 30:
            raise ArchitectureValidationError(
                "Architecture artifact content must contain at least 30 characters "
                "of useful detail."
            )
        if (
            "n/a" in normalized_content.lower()
            and "rationale" not in normalized_content.lower()
        ):
            raise ArchitectureValidationError(
                "An N/A architecture decision must include its rationale."
            )
        return self.repository.add_architecture_artifact(
            package_id=require_text(package_id, "package_id"),
            artifact_type=normalized_type,
            title=require_text(title, "title"),
            content=normalized_content,
            created_by=require_text(created_by, "created_by"),
            source_uri=source_uri.strip() if source_uri else None,
        )

    def add_artifact_from_file(
        self,
        *,
        package_id: str,
        artifact_type: str,
        title: str,
        content_file: str,
        created_by: str,
        actor_role: str,
    ) -> dict[str, Any]:
        path = Path(content_file).expanduser()
        if not path.is_file():
            raise ArchitectureValidationError(f"Architecture content file does not exist: {path}")
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as error:
            raise ArchitectureValidationError(
                f"Cannot read architecture content file '{path}': {error}"
            ) from error
        return self.add_artifact(
            package_id=package_id,
            artifact_type=artifact_type,
            title=title,
            content=content,
            created_by=created_by,
            actor_role=actor_role,
            source_uri=str(path.resolve()),
        )

    def add_decision(
        self,
        *,
        package_id: str,
        decision_id: str,
        title: str,
        context: str,
        decision: str,
        consequences: str,
        created_by: str,
        actor_role: str,
    ) -> dict[str, Any]:
        require_architect_role(actor_role)
        return self.repository.add_architecture_decision(
            package_id=require_text(package_id, "package_id"),
            decision_id=require_text(decision_id, "decision_id"),
            title=require_text(title, "title"),
            context=require_text(context, "context"),
            decision=require_text(decision, "decision"),
            consequences=require_text(consequences, "consequences"),
            created_by=require_text(created_by, "created_by"),
        )

    def map_story(
        self,
        *,
        package_id: str,
        story_id: str,
        mapped_by: str,
        actor_role: str,
    ) -> None:
        require_architect_role(actor_role)
        self.repository.map_story_to_architecture(
            package_id=require_text(package_id, "package_id"),
            story_id=require_text(story_id, "story_id"),
            mapped_by=require_text(mapped_by, "mapped_by"),
        )

    def submit(
        self, package_id: str, *, actor_id: str, note: str, actor_role: str,
    ) -> dict[str, Any]:
        require_architect_role(actor_role)
        return self.repository.submit_architecture_package(
            package_id=require_text(package_id, "package_id"),
            actor_id=require_text(actor_id, "actor_id"),
            note=require_text(note, "note"),
        )

    def review(
        self,
        package_id: str,
        *,
        outcome: str,
        reviewer_id: str,
        note: str,
        evidence_uri: str,
        actor_role: str,
    ) -> dict[str, Any]:
        require_reviewer_role(actor_role)
        try:
            normalized_outcome = ArchitectureReviewOutcome(outcome).value
        except ValueError as error:
            raise ArchitectureValidationError(
                "Review outcome must be 'approved' or 'changes_requested'."
            ) from error
        return self.repository.review_architecture_package(
            package_id=require_text(package_id, "package_id"),
            outcome=normalized_outcome,
            reviewer_id=require_text(reviewer_id, "reviewer_id"),
            note=require_text(note, "note"),
            evidence_uri=require_text(evidence_uri, "evidence_uri"),
        )

    def checklist(self, package_id: str) -> dict[str, Any]:
        return self.repository.get_architecture_checklist(package_id)

    def get(self, package_id: str) -> dict[str, Any]:
        return self.repository.get_architecture_package(package_id)

    def for_feature(self, feature_id: str) -> dict[str, Any] | None:
        return self.repository.get_approved_architecture_for_feature(feature_id)

