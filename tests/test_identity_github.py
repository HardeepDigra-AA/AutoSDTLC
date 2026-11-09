from __future__ import annotations

import hashlib
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ai_sdlc.domain.workflow import Action, FeatureRequest, Role
from ai_sdlc.infrastructure.sqlite_repository import SQLiteRepository
from ai_sdlc.integrations.github import (
    BranchPolicy,
    CheckResult,
    GitHubGovernanceService,
    GitHubIntegrationError,
    GitWorktreeManager,
    MockGitHubAdapter,
    PullRequestGate,
    RepositoryRef,
)
from ai_sdlc.services.identity_service import (
    AuthenticationError,
    AuthorizationError,
    AuthenticatedWorkflowGateway,
    AuthorizationError,
    IdentityService,
)
from ai_sdlc.services.workflow_service import WorkflowService


@pytest.fixture
def repository(tmp_path: Path) -> SQLiteRepository:
    repo = SQLiteRepository(tmp_path / "m5.db")
    repo.initialize()
    return repo


@pytest.fixture
def identities(repository: SQLiteRepository) -> IdentityService:
    return IdentityService(repository)


def create_identity(service: IdentityService, identity_id: str, role: Role):
    return service.create_identity(
        identity_id=identity_id,
        display_name=identity_id.replace("-", " "),
        role=role,
        expires_in_days=30,
    )


def valid_pr_body() -> str:
    return """## Requirements
REQ-LOGIN-001

## Acceptance criteria
AC-01 covered.

## Test evidence
pytest passed.

## Risk and rollback
Rollback to prior release.
"""


def test_bootstrap_admin_is_one_time_and_token_is_hashed(identities, repository):
    credential = identities.bootstrap_admin(
        identity_id="ORCH-ADMIN", display_name="Orchestrator Administrator"
    )
    principal = identities.authenticate(credential.token, required_scope="identity.manage")
    assert principal.role == Role.IDENTITY_ADMIN
    assert "github.repository.register" in principal.scopes

    saved = repository.get_agent_credential(credential.credential_id)
    assert saved is not None
    assert credential.token not in repr(saved)
    assert saved["token_hash"] != hashlib.sha256(credential.token.encode()).digest()
    with pytest.raises(AuthorizationError, match="Bootstrap is allowed only"):
        identities.bootstrap_admin(identity_id="ADMIN-2", display_name="Second admin")


def test_first_admin_bootstrap_is_atomic_under_concurrent_attempts(tmp_path: Path):
    database_path = tmp_path / "bootstrap-race.db"
    repository = SQLiteRepository(database_path)
    repository.initialize()

    def attempt(index: int):
        service = IdentityService(SQLiteRepository(database_path))
        try:
            return service.bootstrap_admin(
                identity_id=f"RACE-ADMIN-{index}",
                display_name=f"Concurrent Administrator {index}",
            )
        except AuthorizationError:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))

    successful = [result for result in results if result is not None]
    assert len(successful) == 1
    with repository._connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM agent_identities").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM control_plane_bootstrap").fetchone()[0] == 1


def test_identity_tokens_authenticate_and_enforce_least_privilege(identities):
    dev = create_identity(identities, "DEV-01", Role.DEVELOPER)
    principal = identities.authenticate(dev.token, required_scope="github.pr.create")
    assert principal.identity_id == "DEV-01"
    assert principal.role == Role.DEVELOPER
    with pytest.raises(AuthorizationError, match="github.pr.review"):
        identities.authenticate(dev.token, required_scope="github.pr.review")

    scrum = create_identity(identities, "SCRUM-01", Role.SCRUM_MASTER)
    identities.authenticate(scrum.token, required_scope="scrum.read")
    with pytest.raises(AuthorizationError):
        identities.authenticate(scrum.token, required_scope="github.branch.create")


def test_invalid_malformed_and_expired_tokens_are_rejected(identities, repository):
    credential = create_identity(identities, "QA-01", Role.QA_ENGINEER)
    with pytest.raises(AuthenticationError, match="format"):
        identities.authenticate("not-a-valid-token")
    with pytest.raises(AuthenticationError, match="Invalid bearer token"):
        identities.authenticate(credential.token + "wrong")

    with repository._connection() as connection:
        connection.execute(
            "UPDATE agent_credentials SET expires_at = '2000-01-01T00:00:00+00:00' "
            "WHERE credential_id = ?",
            (credential.credential_id,),
        )
    with pytest.raises(AuthenticationError, match="expired"):
        identities.authenticate(credential.token)


def test_revoked_and_disabled_identity_credentials_are_rejected(identities):
    credential = create_identity(identities, "DEV-02", Role.DEVELOPER)
    assert identities.revoke_credential(
        credential.credential_id, actor_id="ORCH-ADMIN", note="Rotate exposed credential"
    )
    with pytest.raises(AuthenticationError, match="revoked"):
        identities.authenticate(credential.token)

    second = create_identity(identities, "QA-02", Role.QA_ENGINEER)
    identities.disable_identity("QA-02", actor_id="ORCH-ADMIN", note="Resource offboarded")
    with pytest.raises(AuthenticationError, match="revoked"):
        identities.authenticate(second.token)


def test_disabled_identity_can_be_reenabled_but_requires_new_token(identities):
    credential = create_identity(identities, "DEV-03", Role.DEVELOPER)
    identities.disable_identity("DEV-03", actor_id="ORCH-ADMIN", note="Temporarily disabled")
    identities.enable_identity("DEV-03", actor_id="ORCH-ADMIN", note="Approved reactivation")
    with pytest.raises(AuthenticationError, match="revoked"):
        identities.authenticate(credential.token)
    replacement = identities.issue_credential("DEV-03")
    assert identities.authenticate(replacement.token).identity_id == "DEV-03"


def test_rotating_agent_token_revokes_old_credential_and_issues_new_one(identities):
    original = create_identity(identities, "DEV-ROTATE-01", Role.DEVELOPER)
    replacement = identities.rotate_credential(
        "DEV-ROTATE-01", actor_id="ORCH-ADMIN", note="Scheduled credential rotation"
    )
    with pytest.raises(AuthenticationError, match="revoked"):
        identities.authenticate(original.token)
    assert identities.authenticate(replacement.token).identity_id == "DEV-ROTATE-01"


def test_identity_audit_events_are_append_only(repository):
    service = IdentityService(repository)
    credential = create_identity(service, "QA-03", Role.QA_ENGINEER)
    with repository._connection() as connection:
        row = connection.execute(
            "SELECT event_id FROM identity_events WHERE identity_id = ? LIMIT 1",
            (credential.identity_id,),
        ).fetchone()
        with pytest.raises(Exception, match="append-only"):
            connection.execute(
                "UPDATE identity_events SET note = 'tampered' WHERE event_id = ?",
                (row["event_id"],),
            )


def test_authenticated_workflow_gateway_derives_actor_from_token(repository, identities):
    repository.create_feature(FeatureRequest(
        "AUTH-SEC-001", "Secure login", "User needs a secure login", ("Valid login succeeds",)
    ))
    ba = create_identity(identities, "BA-SEC-01", Role.BUSINESS_ANALYST)
    gateway = AuthenticatedWorkflowGateway(identities, WorkflowService(repository))
    event = gateway.apply(
        ba.token, "AUTH-SEC-001", Action.SUBMIT_FOR_BA_REVIEW, note="Submitted by BA"
    )
    assert event.actor_id == "BA-SEC-01"
    assert event.actor_role == Role.BUSINESS_ANALYST

    dev = create_identity(identities, "DEV-SEC-01", Role.DEVELOPER)
    with pytest.raises(AuthorizationError):
        gateway.apply(
            dev.token, "AUTH-SEC-001", Action.APPROVE_BA, note="Attempt to impersonate BA"
        )


def test_branch_policy_generates_safe_names_and_rejects_unsafe_names():
    assert BranchPolicy.build("feature", "US-AUTH-001", "Add Login UI") == (
        "feature/US-AUTH-001-add-login-ui"
    )
    assert BranchPolicy.build("bugfix", "BUG-001", "invalid credentials") == (
        "bugfix/BUG-001-invalid-credentials"
    )
    for unsafe in ("main", "feature/../main", "feature/foo/", "feature/name with spaces"):
        with pytest.raises(ValueError):
            BranchPolicy.validate(unsafe)
    with pytest.raises(ValueError):
        BranchPolicy.build("release", "REL-001", "release")


def test_developer_can_create_pr_with_complete_traceability_but_cannot_review_or_merge(identities):
    developer = create_identity(identities, "DEV-GH-01", Role.DEVELOPER)
    provider = MockGitHubAdapter()
    repo = RepositoryRef("demo-org", "sample-app", "main")
    provider.add_repository(repo)
    governance = GitHubGovernanceService(identities, provider)

    pr = governance.create_pull_request(
        developer.token, repository=repo, head="feature/US-AUTH-001-login",
        base="develop", title="[US-AUTH-001] Add login", body=valid_pr_body(),
    )
    assert pr.number == 1
    with pytest.raises(AuthorizationError):
        governance.review_pull_request(
            developer.token, repository=repo, number=pr.number,
            outcome="approved", note="Looks good", pull_request_author_id="DEV-GH-01",
        )
    with pytest.raises(AuthorizationError, match="github.pr.merge"):
        governance.merge_pull_request(developer.token, repository=repo, number=pr.number)


def test_pr_creation_requires_all_sections_and_safe_branch(identities):
    developer = create_identity(identities, "DEV-GH-02", Role.DEVELOPER)
    provider = MockGitHubAdapter()
    repo = RepositoryRef("demo-org", "sample-app", "main")
    provider.add_repository(repo)
    governance = GitHubGovernanceService(identities, provider)
    with pytest.raises(ValueError, match="missing mandatory sections"):
        governance.create_pull_request(
            developer.token, repository=repo, head="feature/US-001-login", base="develop",
            title="Login", body="Only a summary.",
        )
    with pytest.raises(ValueError, match="must use"):
        governance.create_pull_request(
            developer.token, repository=repo, head="main", base="develop",
            title="Login", body=valid_pr_body(),
        )


def test_independent_qa_lead_review_and_all_ci_checks_are_required_for_merge(identities):
    author = create_identity(identities, "QA-LEAD-AUTHOR", Role.QA_LEAD)
    reviewer = create_identity(identities, "QA-LEAD-REVIEWER", Role.QA_LEAD)
    provider = MockGitHubAdapter()
    repo = RepositoryRef("demo-org", "sample-app", "main")
    provider.add_repository(repo)
    governance = GitHubGovernanceService(identities, provider)
    pr = governance.create_pull_request(
        author.token, repository=repo, head="qa/US-002-login-api", base="develop",
        title="[US-002] Login API automation", body=valid_pr_body(),
    )

    with pytest.raises(GitHubIntegrationError, match="cannot.*own PR"):
        governance.review_pull_request(
            author.token, repository=repo, number=pr.number,
            outcome="approved", note="Self review", pull_request_author_id="QA-LEAD-AUTHOR",
        )

    governance.review_pull_request(
        reviewer.token, repository=repo, number=pr.number,
        outcome="approved", note="Independent review passed.",
        pull_request_author_id="QA-LEAD-AUTHOR",
    )
    with pytest.raises(GitHubIntegrationError, match="review decision"):
        governance.merge_pull_request(reviewer.token, repository=repo, number=pr.number)

    provider.set_pull_request_gate(repo, pr.number, PullRequestGate(
        "APPROVED", "CLEAN", False,
        (CheckResult("unit-tests", "success"), CheckResult("security-scan", "failure")),
    ))
    with pytest.raises(GitHubIntegrationError, match="security-scan"):
        governance.merge_pull_request(reviewer.token, repository=repo, number=pr.number)

    provider.set_pull_request_gate(repo, pr.number, PullRequestGate(
        "APPROVED", "CLEAN", False,
        (CheckResult("unit-tests", "success"), CheckResult("security-scan", "success")),
    ))
    governance.merge_pull_request(reviewer.token, repository=repo, number=pr.number)
    assert (repo.full_name, pr.number) in provider.merged


def test_qa_lead_cannot_merge_to_main_but_release_manager_can(identities):
    dev = create_identity(identities, "DEV-GH-04", Role.DEVELOPER)
    qa_lead = create_identity(identities, "QA-LEAD-04", Role.QA_LEAD)
    release = create_identity(identities, "REL-01", Role.RELEASE_MANAGER)
    provider = MockGitHubAdapter()
    repo = RepositoryRef("demo-org", "sample-app", "main")
    provider.add_repository(repo)
    governance = GitHubGovernanceService(identities, provider)
    pr = governance.create_pull_request(
        dev.token, repository=repo, head="feature/US-004-login-ui", base="main",
        title="[US-004] UI", body=valid_pr_body(),
    )
    provider.set_pull_request_gate(repo, pr.number, PullRequestGate(
        "APPROVED", "CLEAN", False, (CheckResult("all-required-checks", "success"),)
    ))
    with pytest.raises(GitHubIntegrationError, match="release_manager"):
        governance.merge_pull_request(qa_lead.token, repository=repo, number=pr.number)
    governance.merge_pull_request(release.token, repository=repo, number=pr.number)
    assert (repo.full_name, pr.number) in provider.merged


def test_worktree_manager_creates_and_removes_isolated_worktree(tmp_path: Path):
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    worktree = tmp_path / "agent-dev-01"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "M5 Tests"], cwd=repo, check=True)
    (repo / "README.md").write_text("M5 worktree test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo, check=True, capture_output=True)

    manager = GitWorktreeManager()
    result = manager.create(repo, worktree, "feature/US-005-isolated-work", "main")
    assert Path(result["worktree_path"]).is_dir()
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=worktree,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert branch == "feature/US-005-isolated-work"
    (worktree / "uncommitted.txt").write_text("do not discard me", encoding="utf-8")
    with pytest.raises(GitHubIntegrationError):
        manager.remove(repo, worktree)
    assert (worktree / "uncommitted.txt").exists()
    (worktree / "uncommitted.txt").unlink()
    manager.remove(repo, worktree)
    assert not worktree.exists()


def test_identity_role_is_added_without_changing_original_twelve_delivery_roles():
    assert len([role for role in Role if role != Role.IDENTITY_ADMIN]) == 9
    assert Role.IDENTITY_ADMIN.value == "identity_admin"


def test_github_cli_adapter_reports_pending_checks_instead_of_losing_json(monkeypatch):
    from subprocess import CompletedProcess

    from ai_sdlc.integrations.github import GitHubCLIAdapter

    monkeypatch.setattr("ai_sdlc.integrations.github.shutil.which", lambda _name: "/usr/bin/gh")
    responses = [
        CompletedProcess(
            args=["gh"], returncode=0,
            stdout='{"reviewDecision":"APPROVED","mergeStateStatus":"CLEAN","isDraft":false}',
            stderr="",
        ),
        CompletedProcess(
            args=["gh"], returncode=8,
            stdout='[{"name":"required-tests","state":"PENDING","link":null}]',
            stderr="",
        ),
    ]
    def fake_run(*_args, **_kwargs):
        return responses.pop(0)

    monkeypatch.setattr("ai_sdlc.integrations.github.subprocess.run", fake_run)
    adapter = GitHubCLIAdapter()
    gate = adapter.get_pull_request_gate(RepositoryRef("demo-org", "sample-app", "main"), 42)
    assert not gate.can_merge
    assert gate.blockers() == ("Check 'required-tests' is PENDING",)
