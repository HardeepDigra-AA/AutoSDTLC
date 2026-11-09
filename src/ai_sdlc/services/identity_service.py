"""Authenticated identities, scoped authorization, and one-time API credentials.

The current local implementation uses opaque bearer tokens whose secrets are stored only
as salted PBKDF2 hashes. Production deployments should put the service behind TLS and a
trusted identity provider, rotate credentials, and protect the database and backups.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from ai_sdlc.domain.workflow import Action, Role
from ai_sdlc.infrastructure.sqlite_repository import SQLiteRepository

HASH_ITERATIONS: Final[int] = 310_000
TOKEN_PREFIX: Final[str] = "aisdlc"


class IdentityError(Exception):
    """Base error for identity and authorization failures."""


class AuthenticationError(IdentityError):
    """Raised for unknown, expired, revoked, or disabled credentials."""


class AuthorizationError(IdentityError):
    """Raised when an authenticated identity lacks a required permission."""


# Permissions are intentionally explicit. A role gains only the scopes listed here.
ROLE_SCOPES: Final[dict[Role, frozenset[str]]] = {
    Role.BUSINESS_ANALYST: frozenset({
        "requirements.read", "requirements.write", "requirements.ba_review", "scrum.read"
    }),
    Role.PRODUCT_OWNER: frozenset({
        "requirements.read", "requirements.po_approve", "product.accept", "scrum.read"
    }),
    Role.ARCHITECT: frozenset({
        "architecture.read", "architecture.write", "architecture.authorize", "scrum.read"
    }),
    Role.ARCHITECTURE_REVIEWER: frozenset({
        "architecture.read", "architecture.review", "github.pr.review", "scrum.read"
    }),
    Role.DEVELOPER: frozenset({
        "development.read", "development.start", "development.submit_to_qa", "developer.fix",
        "code.write", "github.read", "github.branch.create", "github.pr.create", "scrum.read"
    }),
    Role.QA_ENGINEER: frozenset({
        "qa.read", "qa.execute", "qa.defect.write", "qa.retest", "qa.test.write",
        "github.read", "github.branch.create", "github.pr.create", "scrum.read"
    }),
    Role.QA_LEAD: frozenset({
        "qa.read", "qa.execute", "qa.retest", "qa.signoff", "qa.review",
        "github.read", "github.branch.create", "github.pr.create", "github.pr.review",
        "github.pr.merge", "scrum.read"
    }),
    Role.RELEASE_MANAGER: frozenset({
        "release.read", "release.authorize", "release.deploy", "github.read",
        "github.pr.merge", "scrum.read"
    }),
    Role.SCRUM_MASTER: frozenset({"scrum.read", "activity.read", "github.read"}),
    Role.IDENTITY_ADMIN: frozenset({
        "identity.manage", "github.repository.register", "github.read", "scrum.read"
    }),
}

ACTION_SCOPES: Final[dict[Action, str]] = {
    Action.SUBMIT_FOR_BA_REVIEW: "requirements.write",
    Action.APPROVE_BA: "requirements.ba_review",
    Action.APPROVE_SCOPE: "requirements.po_approve",
    Action.APPROVE_ARCHITECTURE: "architecture.authorize",
    Action.START_DEVELOPMENT: "development.start",
    Action.SUBMIT_TO_QA: "development.submit_to_qa",
    Action.START_QA: "qa.execute",
    Action.REPORT_DEFECT: "qa.defect.write",
    Action.PASS_FEATURE_TESTS: "qa.execute",
    Action.SUBMIT_FIX_FOR_RETEST: "developer.fix",
    Action.REOPEN_DEFECT: "qa.retest",
    Action.CONFIRM_FIX: "qa.retest",
    Action.FAIL_REGRESSION: "qa.execute",
    Action.PASS_REGRESSION: "qa.execute",
    Action.APPROVE_QA_SIGNOFF: "qa.signoff",
    Action.APPROVE_PRODUCT_ACCEPTANCE: "product.accept",
    Action.RELEASE: "release.authorize",
}


@dataclass(frozen=True, slots=True)
class Principal:
    identity_id: str
    display_name: str
    role: Role
    identity_type: str
    scopes: frozenset[str]

    def require(self, scope: str) -> None:
        if scope not in self.scopes:
            raise AuthorizationError(
                f"Identity '{self.identity_id}' ({self.role.value}) lacks required scope '{scope}'."
            )


@dataclass(frozen=True, slots=True)
class IssuedCredential:
    credential_id: str
    identity_id: str
    token: str  # Returned once to the caller. Never persisted or logged.
    expires_at: datetime | None


class IdentityService:
    """Creates identities and authenticates bearer tokens against hashed credentials."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    def bootstrap_admin(
        self, *, identity_id: str, display_name: str, expires_in_days: int | None = 90
    ) -> IssuedCredential:
        if not identity_id.strip() or not display_name.strip():
            raise ValueError("identity_id and display_name are required")
        if expires_in_days is not None and expires_in_days < 1:
            raise ValueError("expires_in_days must be positive or None")
        credential_id = secrets.token_hex(12)
        secret = secrets.token_urlsafe(32)
        token = f"{TOKEN_PREFIX}.{credential_id}.{secret}"
        salt = secrets.token_bytes(16)
        token_hash = hashlib.pbkdf2_hmac(
            "sha256", secret.encode("utf-8"), salt, HASH_ITERATIONS
        )
        expiry = (
            datetime.now(UTC) + timedelta(days=expires_in_days)
            if expires_in_days is not None
            else None
        )
        try:
            self.repository.bootstrap_admin_identity(
                identity_id=identity_id.strip(), display_name=display_name.strip(),
                token_salt=salt, token_hash=token_hash, hash_iterations=HASH_ITERATIONS,
                expires_at=expiry.isoformat() if expiry else None,
                credential_id=credential_id,
            )
        except ValueError as error:
            raise AuthorizationError(str(error)) from error
        return IssuedCredential(credential_id, identity_id.strip(), token, expiry)

    def create_identity(
        self,
        *,
        identity_id: str,
        display_name: str,
        role: Role | str,
        identity_type: str = "agent",
        capacity_points: float = 0,
        expires_in_days: int | None = 90,
    ) -> IssuedCredential:
        normalized_role = Role(role)
        if expires_in_days is not None and expires_in_days < 1:
            raise ValueError("expires_in_days must be positive or None")
        self.repository.create_agent_identity(
            identity_id=identity_id,
            display_name=display_name,
            role=normalized_role.value,
            identity_type=identity_type,
            capacity_points=capacity_points,
        )
        return self.issue_credential(identity_id, expires_in_days=expires_in_days)

    def issue_credential(
        self, identity_id: str, *, expires_in_days: int | None = 90
    ) -> IssuedCredential:
        identity = self.repository.get_agent_identity(identity_id)
        if identity is None or identity["status"] != "active":
            raise AuthenticationError(f"Active identity '{identity_id}' was not found.")
        if expires_in_days is not None and expires_in_days < 1:
            raise ValueError("expires_in_days must be positive or None")

        credential_id = secrets.token_hex(12)
        secret = secrets.token_urlsafe(32)
        token = f"{TOKEN_PREFIX}.{credential_id}.{secret}"
        salt = secrets.token_bytes(16)
        token_hash = hashlib.pbkdf2_hmac(
            "sha256", secret.encode("utf-8"), salt, HASH_ITERATIONS
        )
        expiry = (
            datetime.now(UTC) + timedelta(days=expires_in_days)
            if expires_in_days is not None
            else None
        )
        self.repository.create_agent_credential(
            credential_id=credential_id,
            identity_id=identity_id,
            token_salt=salt,
            token_hash=token_hash,
            hash_iterations=HASH_ITERATIONS,
            expires_at=expiry.isoformat() if expiry else None,
        )
        return IssuedCredential(credential_id, identity_id, token, expiry)

    def authenticate(self, token: str, *, required_scope: str | None = None) -> Principal:
        parts = token.split(".") if isinstance(token, str) else []
        if len(parts) != 3 or parts[0] != TOKEN_PREFIX:
            raise AuthenticationError("Invalid bearer token format.")
        credential = self.repository.get_agent_credential(parts[1])
        if credential is None or credential["revoked_at"] is not None:
            raise AuthenticationError("Credential is unknown or has been revoked.")
        if credential["identity_status"] != "active":
            raise AuthenticationError("Identity is disabled.")
        if credential["expires_at"]:
            expiry = datetime.fromisoformat(str(credential["expires_at"]))
            if expiry <= datetime.now(UTC):
                raise AuthenticationError("Credential has expired.")

        candidate = hashlib.pbkdf2_hmac(
            "sha256", parts[2].encode("utf-8"), bytes(credential["token_salt"]),
            int(credential["hash_iterations"]),
        )
        if not hmac.compare_digest(candidate, bytes(credential["token_hash"])):
            raise AuthenticationError("Invalid bearer token.")

        role = Role(str(credential["role"]))
        principal = Principal(
            identity_id=str(credential["identity_id"]),
            display_name=str(credential["display_name"]),
            role=role,
            identity_type=str(credential["identity_type"]),
            scopes=ROLE_SCOPES[role],
        )
        if required_scope:
            principal.require(required_scope)
        self.repository.touch_agent_credential(str(credential["credential_id"]))
        self.repository.record_identity_event(
            principal.identity_id,
            event_type="authentication_succeeded",
            actor_id=principal.identity_id,
            note=f"Authenticated for scope '{required_scope or 'identity.read'}'.",
        )
        return principal

    def rotate_credential(
        self, identity_id: str, *, actor_id: str, note: str, expires_in_days: int | None = 90
    ) -> IssuedCredential:
        identity = self.repository.get_agent_identity(identity_id)
        if identity is None or identity["status"] != "active":
            raise AuthenticationError(f"Active identity '{identity_id}' was not found.")
        for credential in identity["credentials"]:
            if credential["revoked_at"] is None:
                self.repository.revoke_agent_credential(
                    str(credential["credential_id"]), actor_id=actor_id,
                    note=f"Rotated credential: {note}",
                )
        return self.issue_credential(identity_id, expires_in_days=expires_in_days)

    def revoke_credential(
        self, credential_id: str, *, actor_id: str, note: str
    ) -> bool:
        return self.repository.revoke_agent_credential(
            credential_id, actor_id=actor_id, note=note
        )

    def disable_identity(self, identity_id: str, *, actor_id: str, note: str) -> None:
        self.repository.set_agent_identity_status(
            identity_id, active=False, actor_id=actor_id, note=note
        )

    def enable_identity(self, identity_id: str, *, actor_id: str, note: str) -> None:
        self.repository.set_agent_identity_status(
            identity_id, active=True, actor_id=actor_id, note=note
        )


class AuthenticatedWorkflowGateway:
    """Secure service entry point that derives actor ID and role from a verified token."""

    def __init__(self, identity_service: IdentityService, workflow_service: object) -> None:
        self.identity_service = identity_service
        self.workflow_service = workflow_service

    def apply(
        self,
        token: str,
        feature_id: str,
        action: Action,
        *,
        note: str,
        evidence_uri: str | None = None,
    ) -> object:
        scope = ACTION_SCOPES[action]
        principal = self.identity_service.authenticate(token, required_scope=scope)
        return self.workflow_service.apply(
            feature_id,
            action,
            principal.role,
            actor_id=principal.identity_id,
            note=note,
            evidence_uri=evidence_uri,
        )
