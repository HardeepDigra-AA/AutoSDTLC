"""GitHub provider boundary, least-privilege governance, and isolated Git worktrees.

The MockGitHubAdapter is used by tests and dry runs. GitHubCLIAdapter delegates credentials
to the official `gh` CLI and never reads, stores, or prints GitHub access tokens itself.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from ai_sdlc.services.identity_service import IdentityService, Principal


class GitHubIntegrationError(Exception):
    """Raised for Git/GitHub CLI failures or invalid repository operations."""


@dataclass(frozen=True, slots=True)
class RepositoryRef:
    owner: str
    name: str
    default_branch: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True, slots=True)
class PullRequestRef:
    number: int
    url: str
    head_branch: str
    base_branch: str
    status: str = "open"


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    state: str
    url: str | None = None


@dataclass(frozen=True, slots=True)
class PullRequestGate:
    review_decision: str
    merge_state: str
    is_draft: bool
    checks: tuple[CheckResult, ...]

    @property
    def can_merge(self) -> bool:
        if self.is_draft or self.review_decision != "APPROVED" or self.merge_state != "CLEAN":
            return False
        return bool(self.checks) and all(check.state.lower() == "success" for check in self.checks)

    def blockers(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if self.is_draft:
            reasons.append("Pull request is still a draft")
        if self.review_decision != "APPROVED":
            reasons.append(f"Required review decision is {self.review_decision or 'missing'}")
        if self.merge_state != "CLEAN":
            reasons.append(f"GitHub merge state is {self.merge_state or 'unknown'}")
        if not self.checks:
            reasons.append("No CI checks were reported")
        for check in self.checks:
            if check.state.lower() != "success":
                reasons.append(f"Check '{check.name}' is {check.state}")
        return tuple(reasons)


class GitHubProvider(Protocol):
    """Operations required by the orchestration service."""

    def auth_status(self) -> bool: ...
    def get_repository(self, owner: str, name: str) -> RepositoryRef: ...
    def create_pull_request(
        self, repository: RepositoryRef, head: str, base: str, title: str, body: str
    ) -> PullRequestRef: ...
    def get_pull_request(self, repository: RepositoryRef, number: int) -> PullRequestRef: ...
    def get_pull_request_gate(
        self, repository: RepositoryRef, number: int
    ) -> PullRequestGate: ...
    def review_pull_request(
        self, repository: RepositoryRef, number: int, outcome: str, note: str
    ) -> None: ...
    def merge_pull_request(self, repository: RepositoryRef, number: int) -> None: ...


BRANCH_PREFIXES = frozenset({"feature", "bugfix", "qa", "chore"})
REQUIRED_PR_SECTIONS = (
    "## Requirements",
    "## Acceptance criteria",
    "## Test evidence",
    "## Risk and rollback",
)


class BranchPolicy:
    """Generate predictable, traceable branch names and reject unsafe branch syntax."""

    @staticmethod
    def build(kind: str, work_id: str, summary: str) -> str:
        if kind not in BRANCH_PREFIXES:
            raise ValueError(f"Branch kind must be one of: {', '.join(sorted(BRANCH_PREFIXES))}")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,63}", work_id):
            raise ValueError("work_id must be 2-64 safe identifier characters")
        slug = re.sub(r"[^a-z0-9]+", "-", summary.lower()).strip("-")[:48].strip("-")
        if not slug:
            raise ValueError("summary must contain at least one letter or number")
        return f"{kind}/{work_id}-{slug}"

    @staticmethod
    def validate(branch: str) -> None:
        if not isinstance(branch, str) or len(branch) > 200:
            raise ValueError("Branch name is empty or too long")
        if ".." in branch or "@{" in branch:
            raise ValueError("Unsafe Git branch name")
        if not any(branch.startswith(f"{prefix}/") for prefix in BRANCH_PREFIXES):
            raise ValueError("Branch must use feature/, bugfix/, qa/, or chore/ prefix")
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch):
            raise ValueError("Branch contains unsupported characters")
        segments = branch.split("/")
        if any(not part or part.startswith(".") or part.endswith(".") or part.endswith(".lock")
               for part in segments):
            raise ValueError("Branch contains an invalid path segment")


class GitWorktreeManager:
    """Create one isolated filesystem worktree per agent/branch."""

    def _run(self, args: list[str], *, cwd: Path) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=cwd, check=False, capture_output=True, text=True
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
            raise GitHubIntegrationError(message)
        return completed.stdout.strip()

    def create(self, repository_path: str | Path, worktree_path: str | Path,
               branch: str, base_branch: str) -> dict[str, str]:
        BranchPolicy.validate(branch)
        repo = Path(repository_path).expanduser().resolve()
        target = Path(worktree_path).expanduser().resolve()
        if not repo.is_dir() or not (repo / ".git").exists():
            raise GitHubIntegrationError(f"'{repo}' is not a Git working tree")
        if target.exists():
            raise GitHubIntegrationError(f"Worktree path already exists: {target}")
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", base_branch) or ".." in base_branch:
            raise ValueError("Invalid base branch")
        target.parent.mkdir(parents=True, exist_ok=True)
        self._run(["fetch", "origin", base_branch], cwd=repo)
        self._run(["worktree", "add", "-b", branch, str(target), f"origin/{base_branch}"], cwd=repo)
        return {"branch": branch, "worktree_path": str(target), "base_branch": base_branch}

    def remove(self, repository_path: str | Path, worktree_path: str | Path) -> None:
        repo = Path(repository_path).expanduser().resolve()
        target = Path(worktree_path).expanduser().resolve()
        self._run(["worktree", "remove", str(target)], cwd=repo)


class GitHubCLIAdapter:
    """Real provider powered by the official GitHub CLI (`gh`)."""

    def __init__(self, *, cwd: str | Path | None = None) -> None:
        self.cwd = Path(cwd).expanduser().resolve() if cwd else None
        if shutil.which("gh") is None:
            raise GitHubIntegrationError(
                "GitHub CLI 'gh' is not installed. Install it and run 'gh auth login'."
            )

    def _run(self, args: list[str], *, allowed_returncodes: frozenset[int] = frozenset({0})) -> str:
        completed = subprocess.run(
            ["gh", *args], cwd=self.cwd, check=False, capture_output=True, text=True
        )
        if completed.returncode not in allowed_returncodes:
            message = completed.stderr.strip() or completed.stdout.strip() or "gh command failed"
            raise GitHubIntegrationError(message)
        return completed.stdout.strip()

    def auth_status(self) -> bool:
        try:
            self._run(["auth", "status", "--hostname", "github.com"])
            return True
        except GitHubIntegrationError:
            return False

    def get_repository(self, owner: str, name: str) -> RepositoryRef:
        data = json.loads(self._run([
            "repo", "view", f"{owner}/{name}",
            "--json", "nameWithOwner,defaultBranchRef",
        ]))
        default_branch = (data.get("defaultBranchRef") or {}).get("name")
        if not default_branch:
            raise GitHubIntegrationError("Repository does not expose a default branch")
        full_name = data.get("nameWithOwner", f"{owner}/{name}")
        actual_owner, actual_name = full_name.split("/", maxsplit=1)
        return RepositoryRef(actual_owner, actual_name, default_branch)

    def create_pull_request(
        self, repository: RepositoryRef, head: str, base: str, title: str, body: str
    ) -> PullRequestRef:
        url = self._run([
            "pr", "create", "--repo", repository.full_name, "--head", head,
            "--base", base, "--title", title, "--body", body,
        ])
        match = re.search(r"/pull/(\d+)", url)
        if not match:
            raise GitHubIntegrationError(f"Could not parse pull request number from: {url}")
        return PullRequestRef(int(match.group(1)), url, head, base)

    def get_pull_request(self, repository: RepositoryRef, number: int) -> PullRequestRef:
        detail = json.loads(self._run([
            "pr", "view", str(number), "--repo", repository.full_name,
            "--json", "url,headRefName,baseRefName,state",
        ]))
        return PullRequestRef(
            number=number,
            url=str(detail["url"]),
            head_branch=str(detail["headRefName"]),
            base_branch=str(detail["baseRefName"]),
            status=str(detail["state"]).lower(),
        )

    def get_pull_request_gate(self, repository: RepositoryRef, number: int) -> PullRequestGate:
        detail = json.loads(self._run([
            "pr", "view", str(number), "--repo", repository.full_name,
            "--json", "reviewDecision,mergeStateStatus,isDraft",
        ]))
        # gh pr checks documents exit code 8 when checks are pending. A non-empty JSON
        # response is still valuable because the orchestration gate must report blockers.
        check_output = self._run(
            ["pr", "checks", str(number), "--repo", repository.full_name,
             "--json", "name,state,link"],
            allowed_returncodes=frozenset({0, 1, 8}),
        )
        try:
            check_data = json.loads(check_output)
        except json.JSONDecodeError as error:
            raise GitHubIntegrationError(
                "GitHub CLI returned malformed pull-request check JSON."
            ) from error
        checks = tuple(
            CheckResult(str(item.get("name", "unnamed")),
                        str(item.get("state", "unknown")), item.get("link"))
            for item in check_data
        )
        return PullRequestGate(
            review_decision=str(detail.get("reviewDecision") or "MISSING"),
            merge_state=str(detail.get("mergeStateStatus") or "UNKNOWN"),
            is_draft=bool(detail.get("isDraft")),
            checks=checks,
        )

    def review_pull_request(
        self, repository: RepositoryRef, number: int, outcome: str, note: str
    ) -> None:
        flag = "--approve" if outcome == "approved" else "--request-changes"
        self._run(["pr", "review", str(number), "--repo", repository.full_name,
                   flag, "--body", note])

    def merge_pull_request(self, repository: RepositoryRef, number: int) -> None:
        self._run(["pr", "merge", str(number), "--repo", repository.full_name,
                   "--squash", "--delete-branch"])


class MockGitHubAdapter:
    """Deterministic fake provider used in tests and safe local demonstrations."""

    def __init__(self) -> None:
        self.repositories: dict[str, RepositoryRef] = {}
        self.pull_requests: dict[tuple[str, int], PullRequestRef] = {}
        self.gates: dict[tuple[str, int], PullRequestGate] = {}
        self.reviews: list[dict[str, object]] = []
        self.merged: list[tuple[str, int]] = []
        self._next_number = 1

    def auth_status(self) -> bool:
        return True

    def add_repository(self, repository: RepositoryRef) -> None:
        self.repositories[repository.full_name] = repository

    def get_repository(self, owner: str, name: str) -> RepositoryRef:
        try:
            return self.repositories[f"{owner}/{name}"]
        except KeyError as error:
            raise GitHubIntegrationError(f"Mock repository {owner}/{name} is not registered") from error

    def create_pull_request(
        self, repository: RepositoryRef, head: str, base: str, title: str, body: str
    ) -> PullRequestRef:
        number = self._next_number
        self._next_number += 1
        pr = PullRequestRef(number, f"https://github.com/{repository.full_name}/pull/{number}",
                            head, base)
        self.pull_requests[(repository.full_name, number)] = pr
        self.gates[(repository.full_name, number)] = PullRequestGate(
            "REVIEW_REQUIRED", "CLEAN", False,
            (CheckResult("CI", "pending"),),
        )
        return pr

    def get_pull_request(self, repository: RepositoryRef, number: int) -> PullRequestRef:
        try:
            return self.pull_requests[(repository.full_name, number)]
        except KeyError as error:
            raise GitHubIntegrationError(f"Pull request #{number} was not found") from error

    def get_pull_request_gate(self, repository: RepositoryRef, number: int) -> PullRequestGate:
        try:
            return self.gates[(repository.full_name, number)]
        except KeyError as error:
            raise GitHubIntegrationError(f"Pull request #{number} was not found") from error

    def set_pull_request_gate(self, repository: RepositoryRef, number: int,
                              gate: PullRequestGate) -> None:
        if (repository.full_name, number) not in self.pull_requests:
            raise GitHubIntegrationError(f"Pull request #{number} was not found")
        self.gates[(repository.full_name, number)] = gate

    def review_pull_request(
        self, repository: RepositoryRef, number: int, outcome: str, note: str
    ) -> None:
        if (repository.full_name, number) not in self.pull_requests:
            raise GitHubIntegrationError(f"Pull request #{number} was not found")
        self.reviews.append({"repository": repository.full_name, "number": number,
                             "outcome": outcome, "note": note})

    def merge_pull_request(self, repository: RepositoryRef, number: int) -> None:
        if not self.get_pull_request_gate(repository, number).can_merge:
            raise GitHubIntegrationError("Mock provider refused merge because quality gates failed")
        self.merged.append((repository.full_name, number))


class GitHubGovernanceService:
    """Enforces agent permissions and quality rules before calling a GitHub provider."""

    def __init__(self, identity_service: IdentityService, provider: GitHubProvider) -> None:
        self.identity_service = identity_service
        self.provider = provider

    def create_pull_request(
        self, token: str, *, repository: RepositoryRef, head: str, base: str,
        title: str, body: str,
    ) -> PullRequestRef:
        self.identity_service.authenticate(token, required_scope="github.pr.create")
        BranchPolicy.validate(head)
        if not base or "." in base or ".." in base:
            raise ValueError("Invalid PR base branch")
        missing = [section for section in REQUIRED_PR_SECTIONS if section not in body]
        if missing:
            raise ValueError("PR body is missing mandatory sections: " + ", ".join(missing))
        if not title.strip() or len(title) > 120:
            raise ValueError("PR title must contain 1-120 characters")
        return self.provider.create_pull_request(repository, head, base, title, body)

    def review_pull_request(
        self, token: str, *, repository: RepositoryRef, number: int,
        outcome: str, note: str, pull_request_author_id: str,
    ) -> Principal:
        principal = self.identity_service.authenticate(token, required_scope="github.pr.review")
        if principal.identity_id == pull_request_author_id:
            raise GitHubIntegrationError("Pull request authors cannot approve or review their own PR.")
        if outcome not in {"approved", "changes_requested"}:
            raise ValueError("outcome must be approved or changes_requested")
        if not note.strip():
            raise ValueError("Review note is required")
        self.provider.review_pull_request(repository, number, outcome, note)
        return principal

    def merge_pull_request(
        self, token: str, *, repository: RepositoryRef, number: int,
    ) -> None:
        principal = self.identity_service.authenticate(token, required_scope="github.pr.merge")
        gate = self.provider.get_pull_request_gate(repository, number)
        if not gate.can_merge:
            raise GitHubIntegrationError("Merge blocked: " + "; ".join(gate.blockers()))
        pull_request = self.provider.get_pull_request(repository, number)
        base_branch = pull_request.base_branch
        if base_branch in {"main", "master"} and principal.role.value != "release_manager":
            raise GitHubIntegrationError(
                "Direct merge to the protected default branch requires release_manager approval."
            )
        self.provider.merge_pull_request(repository, number)
