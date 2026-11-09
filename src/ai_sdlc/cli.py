"""Command-line interface for the local AI SDLC Orchestrator."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from uuid import uuid4
from pathlib import Path

from ai_sdlc import __version__
from ai_sdlc.domain.architecture import ArchitectureError
from ai_sdlc.domain.requirements import RequirementError
from ai_sdlc.domain.workflow import (
    Action,
    FeatureRequest,
    Role,
    WorkflowError,
    WorkflowValidationError,
)
from ai_sdlc.infrastructure.sqlite_repository import SQLiteRepository
from ai_sdlc.integrations.github import (
    BranchPolicy,
    GitHubCLIAdapter,
    GitHubGovernanceService,
    GitHubIntegrationError,
    GitWorktreeManager,
)
from ai_sdlc.services.identity_service import (
    AuthenticationError,
    AuthenticatedWorkflowGateway,
    AuthorizationError,
    IdentityService,
)
from ai_sdlc.services.architecture_service import ArchitectureService
from ai_sdlc.services.requirements_service import RequirementsService
from ai_sdlc.services.workflow_service import WorkflowService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-sdlc",
        description="Governed AI SDLC orchestration framework.",
        epilog="Use --db before the command to select a database file.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"AI SDLC Orchestrator {__version__}",
    )
    parser.add_argument(
        "--db",
        default=os.getenv("AI_SDLC_DB_PATH", "data/ai_sdlc.db"),
        help="SQLite database path (default: data/ai_sdlc.db or AI_SDLC_DB_PATH).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("version", help="Show the installed version.")
    commands.add_parser("init-db", help="Create or upgrade the local SQLite schema.")

    feature = commands.add_parser("feature", help="Create and inspect feature workflows.")
    feature_commands = feature.add_subparsers(dest="feature_command", required=True)
    create = feature_commands.add_parser("create", help="Create a feature request.")
    create.add_argument("--id", required=True, help="Stable feature ID, e.g. AUTH-001.")
    create.add_argument("--title", required=True)
    create.add_argument("--problem", required=True, help="Business problem statement.")
    create.add_argument(
        "--ac", action="append", required=True, help="Acceptance criterion; repeat for each AC."
    )
    feature_commands.add_parser("list", help="List all features and their states.")
    show = feature_commands.add_parser("show", help="Show a feature, criteria, and audit history.")
    show.add_argument("feature_id")
    transition = feature_commands.add_parser("transition", help="Apply a governed workflow action.")
    transition.add_argument("feature_id")
    transition.add_argument("action", choices=[item.value for item in Action])
    transition.add_argument(
        "--token-env", default="AI_SDLC_AGENT_TOKEN",
        help="Environment variable containing the authenticated agent token.",
    )
    transition.add_argument(
        "--unsafe-local-demo", action="store_true",
        help="Allow an unauthenticated demonstration identity; never use in shared environments.",
    )
    transition.add_argument("--unsafe-local-demo-role", choices=[item.value for item in Role])
    transition.add_argument("--unsafe-local-demo-actor-id")
    transition.add_argument("--note", required=True)
    transition.add_argument("--evidence", help="Required for actions with evidence gates.")

    resource = commands.add_parser("resource", help="Manage team resource records.")
    resource_commands = resource.add_subparsers(dest="resource_command", required=True)
    resource_add = resource_commands.add_parser("add", help="Register a team resource.")
    resource_add.add_argument("--id", required=True)
    resource_add.add_argument("--name", required=True)
    resource_add.add_argument("--role", required=True, choices=[item.value for item in Role])
    resource_add.add_argument("--capacity", type=float, default=0)
    resource_commands.add_parser("list", help="List registered resources.")

    item = commands.add_parser(
        "work-item", help="Create and assign tasks, defects, and test cases."
    )
    item_commands = item.add_subparsers(dest="work_item_command", required=True)
    item_create = item_commands.add_parser("create", help="Create a work item.")
    item_create.add_argument("--id", required=True)
    item_create.add_argument("--feature", required=True)
    item_create.add_argument("--title", required=True)
    item_create.add_argument("--description", default="")
    item_create.add_argument(
        "--type", dest="item_type", choices=("task", "defect", "test_case"), default="task"
    )
    item_create.add_argument(
        "--priority", choices=("low", "medium", "high", "critical"), default="medium"
    )
    item_create.add_argument("--estimate", type=float)
    item_assign = item_commands.add_parser("assign", help="Assign a work item to a resource.")
    item_assign.add_argument("--id", required=True)
    item_assign.add_argument("--resource", required=True)
    item_assign.add_argument("--assigned-by", required=True)
    item_assign.add_argument("--allocation", type=float, default=100)
    item_status = item_commands.add_parser(
        "status", help="Update work item status with an audit event."
    )
    item_status.add_argument("--id", required=True)
    item_status.add_argument(
        "--status", required=True, choices=("todo", "in_progress", "blocked", "done")
    )
    item_status.add_argument("--actor-id", required=True)
    item_status.add_argument("--note", required=True)
    item_status.add_argument("--evidence")
    item_history = item_commands.add_parser("history", help="Show work item activity history.")
    item_history.add_argument("work_item_id")
    item_list = item_commands.add_parser("list", help="List work items.")
    item_list.add_argument("--feature")

    requirement = commands.add_parser(
        "requirement", help="Manage BA requirements, stories, criteria, and traceability."
    )
    req_commands = requirement.add_subparsers(dest="requirement_command", required=True)

    req_create = req_commands.add_parser("create", help="Capture a new business requirement.")
    req_create.add_argument("--id", required=True)
    req_create.add_argument("--title", required=True)
    req_create.add_argument("--description", required=True)
    req_create.add_argument("--business-value", required=True)
    req_create.add_argument("--priority", choices=("low", "medium", "high", "critical"),
                             default="medium")
    req_create.add_argument("--created-by", required=True)

    req_update = req_commands.add_parser("update", help="Create a new requirement version.")
    req_update.add_argument("requirement_id")
    req_update.add_argument("--changed-by", required=True)
    req_update.add_argument("--change-note", required=True)
    req_update.add_argument("--actor-role", choices=("requester", "business_analyst"),
                             default="requester")
    for field_name in ("title", "description", "business-value", "priority"):
        req_update.add_argument(f"--{field_name}")
    req_update.add_argument("--expected-version", type=int)

    req_clarification = req_commands.add_parser(
        "clarification", help="Raise or answer a BA clarification."
    )
    clarification_commands = req_clarification.add_subparsers(
        dest="clarification_command", required=True
    )
    clarification_add = clarification_commands.add_parser("add")
    clarification_add.add_argument("--requirement", required=True)
    clarification_add.add_argument("--id", required=True)
    clarification_add.add_argument("--question", required=True)
    clarification_add.add_argument("--asked-by", required=True)
    clarification_add.add_argument("--actor-role", default="business_analyst",
                                   choices=("business_analyst",))
    clarification_answer = clarification_commands.add_parser("answer")
    clarification_answer.add_argument("--id", required=True)
    clarification_answer.add_argument("--answer", required=True)
    clarification_answer.add_argument("--answered-by", required=True)
    clarification_answer.add_argument("--actor-role", default="requester", choices=("requester",))

    story = req_commands.add_parser("story", help="Create a BA-owned user story.")
    story.add_argument("--id", required=True)
    story.add_argument("--requirement", required=True)
    story.add_argument("--title", required=True)
    story.add_argument("--as-a", dest="user_role", required=True)
    story.add_argument("--i-want", dest="goal", required=True)
    story.add_argument("--so-that", dest="benefit", required=True)
    story.add_argument("--created-by", required=True)
    story.add_argument("--actor-role", default="business_analyst",
                       choices=("business_analyst",))

    criterion = req_commands.add_parser("criterion", help="Add a uniquely identified AC.")
    criterion.add_argument("--id", required=True)
    criterion.add_argument("--story", required=True)
    criterion.add_argument("--description", required=True)
    criterion.add_argument("--created-by", required=True)
    criterion.add_argument("--actor-role", default="business_analyst",
                           choices=("business_analyst",))

    test_case = req_commands.add_parser("test-case", help="Create a traceability test case.")
    test_case.add_argument("--id", required=True)
    test_case.add_argument("--title", required=True)
    test_case.add_argument("--description", required=True)
    test_case.add_argument("--level", dest="test_level",
                           choices=("unit", "api", "ui", "integration", "security",
                                    "accessibility", "rag"), required=True)
    test_case.add_argument("--created-by", required=True)
    test_case.add_argument("--automation-reference")
    test_case.add_argument("--actor-role", default="qa_engineer", choices=("qa_engineer",))

    mapping = req_commands.add_parser("map-test", help="Map a test case to an AC.")
    mapping.add_argument("--criterion", required=True)
    mapping.add_argument("--test-case", required=True)
    mapping.add_argument("--mapped-by", required=True)
    mapping.add_argument("--actor-role", default="qa_engineer", choices=("qa_engineer",))

    for command_name, help_text in (
        ("submit-ba", "Submit a complete requirement package for BA approval."),
        ("approve-ba", "Move a BA-approved package to PO review."),
        ("approve-po", "Approve only when every AC has test coverage."),
        ("request-changes", "Return the package to the requester for changes."),
    ):
        action_parser = req_commands.add_parser(command_name, help=help_text)
        action_parser.add_argument("requirement_id")
        action_parser.add_argument("--actor-id", required=True)
        action_parser.add_argument("--note", required=True)

    req_show = req_commands.add_parser(
        "show", help="Show requirement, stories, history and coverage."
    )
    req_show.add_argument("requirement_id")
    req_brd = req_commands.add_parser("brd", help="Print a Markdown BRD and traceability matrix.")
    req_brd.add_argument("requirement_id")
    req_commands.add_parser("list", help="List requirements and lifecycle states.")

    architecture = commands.add_parser(
        "architecture", help="Create, review, and approve solution architecture/TDD packages."
    )
    architecture_commands = architecture.add_subparsers(
        dest="architecture_command", required=True
    )
    arch_create = architecture_commands.add_parser(
        "create", help="Create a draft architecture package for an approved requirement."
    )
    arch_create.add_argument("--id", required=True)
    arch_create.add_argument("--feature", required=True)
    arch_create.add_argument("--requirement", required=True)
    arch_create.add_argument("--created-by", required=True)
    arch_create.add_argument("--actor-role", default="architect", choices=("architect",))

    arch_artifact = architecture_commands.add_parser(
        "artifact", help="Add or replace one required architecture/TDD section."
    )
    arch_artifact.add_argument("--package", required=True)
    arch_artifact.add_argument(
        "--type", dest="artifact_type", required=True,
        choices=("solution_overview", "component_design", "technical_design", "database_design",
                 "api_contracts", "security_threat_model", "coding_standards",
                 "test_driven_development_plan", "test_strategy",
                 "deployment_rollback"),
    )
    arch_artifact.add_argument("--title", required=True)
    source = arch_artifact.add_mutually_exclusive_group(required=True)
    source.add_argument("--content", help="Inline design content (use --file for longer text).")
    source.add_argument("--file", dest="content_file", help="UTF-8 Markdown file to import.")
    arch_artifact.add_argument("--created-by", required=True)

    arch_adr = architecture_commands.add_parser(
        "adr", help="Record an Architecture Decision Record (ADR)."
    )
    for name in ("id", "package", "title", "context", "decision", "consequences", "created-by"):
        arch_adr.add_argument(f"--{name}", required=True)
    arch_adr.add_argument("--actor-role", default="architect", choices=("architect",))

    arch_map = architecture_commands.add_parser(
        "map-story", help="Map a user story to the architecture package."
    )
    arch_map.add_argument("--package", required=True)
    arch_map.add_argument("--story", required=True)
    arch_map.add_argument("--mapped-by", required=True)
    arch_map.add_argument("--actor-role", default="architect", choices=("architect",))

    arch_submit = architecture_commands.add_parser(
        "submit", help="Submit a complete architecture package for independent review."
    )
    arch_submit.add_argument("package_id")
    arch_submit.add_argument("--actor-id", required=True)
    arch_submit.add_argument("--note", required=True)
    arch_submit.add_argument("--actor-role", default="architect", choices=("architect",))

    arch_review = architecture_commands.add_parser(
        "review", help="Independently approve the package or request changes."
    )
    arch_review.add_argument("package_id")
    arch_review.add_argument("--outcome", required=True,
                             choices=("approved", "changes_requested"))
    arch_review.add_argument("--reviewer-id", required=True)
    arch_review.add_argument("--note", required=True)
    arch_review.add_argument("--evidence", required=True)
    arch_review.add_argument("--actor-role", default="architecture_reviewer",
                             choices=("architecture_reviewer",))

    arch_checklist = architecture_commands.add_parser(
        "checklist", help="Check all mandatory design sections and story mappings."
    )
    arch_checklist.add_argument("package_id")
    arch_show = architecture_commands.add_parser("show", help="Show package and review history.")
    arch_show.add_argument("package_id")

    agent = commands.add_parser("agent", help="Manage authenticated agent identities.")
    agent_commands = agent.add_subparsers(dest="agent_command", required=True)
    bootstrap = agent_commands.add_parser(
        "bootstrap-admin", help="Create the first control-plane administrator (one-time)."
    )
    bootstrap.add_argument("--id", required=True)
    bootstrap.add_argument("--name", required=True)
    bootstrap.add_argument("--expires-in-days", type=int, default=90)
    agent_create = agent_commands.add_parser("create", help="Register a delivery-team identity.")
    agent_create.add_argument("--id", required=True)
    agent_create.add_argument("--name", required=True)
    agent_create.add_argument("--role", required=True, choices=[item.value for item in Role if item != Role.IDENTITY_ADMIN])
    agent_create.add_argument("--type", dest="identity_type", choices=("agent", "human", "service"), default="agent")
    agent_create.add_argument("--capacity", type=float, default=0)
    agent_create.add_argument("--expires-in-days", type=int, default=90)
    agent_create.add_argument("--admin-token-env", default="AI_SDLC_ADMIN_TOKEN")
    agent_list = agent_commands.add_parser("list", help="List registered identities (admin only).")
    agent_list.add_argument("--admin-token-env", default="AI_SDLC_ADMIN_TOKEN")
    agent_rotate = agent_commands.add_parser("rotate-token", help="Revoke all active tokens and issue a replacement.")
    agent_rotate.add_argument("--id", required=True)
    agent_rotate.add_argument("--note", required=True)
    agent_rotate.add_argument("--expires-in-days", type=int, default=90)
    agent_rotate.add_argument("--admin-token-env", default="AI_SDLC_ADMIN_TOKEN")
    agent_revoke = agent_commands.add_parser("revoke-token", help="Revoke one API credential.")
    agent_revoke.add_argument("--credential-id", required=True)
    agent_revoke.add_argument("--note", required=True)
    agent_revoke.add_argument("--admin-token-env", default="AI_SDLC_ADMIN_TOKEN")
    agent_disable = agent_commands.add_parser("disable", help="Disable an identity and revoke its tokens.")
    agent_disable.add_argument("--id", required=True)
    agent_disable.add_argument("--note", required=True)
    agent_disable.add_argument("--admin-token-env", default="AI_SDLC_ADMIN_TOKEN")

    auth = commands.add_parser("auth", help="Verify an agent bearer token from an environment variable.")
    auth_commands = auth.add_subparsers(dest="auth_command", required=True)
    auth_verify = auth_commands.add_parser("verify", help="Display authenticated identity and scopes.")
    auth_verify.add_argument("--token-env", default="AI_SDLC_AGENT_TOKEN")
    auth_verify.add_argument("--require-scope")

    github = commands.add_parser("github", help="Governed GitHub and Git worktree operations.")
    github_commands = github.add_subparsers(dest="github_command", required=True)
    github_commands.add_parser("auth-check", help="Check GitHub CLI authentication without exposing tokens.")
    github_repo = github_commands.add_parser("repo", help="Register and inspect connected repositories.")
    github_repo_commands = github_repo.add_subparsers(dest="github_repo_command", required=True)
    github_repo_add = github_repo_commands.add_parser("add", help="Register a GitHub repository (admin only).")
    github_repo_add.add_argument("--owner", required=True)
    github_repo_add.add_argument("--name", required=True)
    github_repo_add.add_argument("--admin-token-env", default="AI_SDLC_ADMIN_TOKEN")
    github_repo_list = github_repo_commands.add_parser("list", help="List registered repositories.")
    github_repo_list.add_argument("--token-env", default="AI_SDLC_AGENT_TOKEN")
    branch_name = github_commands.add_parser("branch-name", help="Generate a policy-compliant branch name.")
    branch_name.add_argument("--kind", required=True, choices=("feature", "bugfix", "qa", "chore"))
    branch_name.add_argument("--work-id", required=True)
    branch_name.add_argument("--summary", required=True)
    worktree = github_commands.add_parser("worktree", help="Create an isolated agent Git worktree.")
    worktree_commands = worktree.add_subparsers(dest="worktree_command", required=True)
    worktree_add = worktree_commands.add_parser("add")
    worktree_add.add_argument("--repository-id", required=True, help="Registered owner/name.")
    worktree_add.add_argument("--repo-path", required=True)
    worktree_add.add_argument("--path", required=True)
    worktree_add.add_argument("--branch", required=True)
    worktree_add.add_argument("--base")
    worktree_add.add_argument("--token-env", default="AI_SDLC_AGENT_TOKEN")
    worktree_remove = worktree_commands.add_parser("remove")
    worktree_remove.add_argument("--repo-path", required=True)
    worktree_remove.add_argument("--path", required=True)
    worktree_remove.add_argument("--token-env", default="AI_SDLC_AGENT_TOKEN")
    github_pr = github_commands.add_parser("pr", help="Create, review and merge pull requests.")
    github_pr_commands = github_pr.add_subparsers(dest="github_pr_command", required=True)
    pr_create = github_pr_commands.add_parser("create")
    pr_create.add_argument("--repository-id", required=True)
    pr_create.add_argument("--feature", required=True)
    pr_create.add_argument("--head", required=True)
    pr_create.add_argument("--base")
    pr_create.add_argument("--title", required=True)
    pr_create.add_argument("--body-file", required=True)
    pr_create.add_argument("--cwd")
    pr_create.add_argument("--token-env", default="AI_SDLC_AGENT_TOKEN")
    pr_review = github_pr_commands.add_parser("review")
    pr_review.add_argument("--repository-id", required=True)
    pr_review.add_argument("--number", type=int, required=True)
    pr_review.add_argument("--outcome", required=True, choices=("approved", "changes_requested"))
    pr_review.add_argument("--note", required=True)
    pr_review.add_argument("--cwd")
    pr_review.add_argument("--token-env", default="AI_SDLC_AGENT_TOKEN")
    pr_merge = github_pr_commands.add_parser("merge")
    pr_merge.add_argument("--repository-id", required=True)
    pr_merge.add_argument("--number", type=int, required=True)
    pr_merge.add_argument("--cwd")
    pr_merge.add_argument("--token-env", default="AI_SDLC_AGENT_TOKEN")

    scrum = commands.add_parser("scrum", help="View evidence-based project status summaries.")
    scrum_commands = scrum.add_subparsers(dest="scrum_command", required=True)
    scrum_commands.add_parser("summary", help="Show feature, work, defect, and resource counts.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(f"AI SDLC Orchestrator {__version__}")
        return 0

    repository = SQLiteRepository(Path(args.db))
    try:
        repository.initialize()
        if args.command == "init-db":
            print(f"Database initialized: {Path(args.db).resolve()}")
            return 0
        return _run_command(args, repository)
    except (
        ValueError,
        ArchitectureError,
        WorkflowError,
        RequirementError,
        AuthenticationError,
        AuthorizationError,
        GitHubIntegrationError,
        sqlite3.IntegrityError,
        sqlite3.OperationalError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


def _run_requirement_command(args: argparse.Namespace, repository: SQLiteRepository) -> int:
    service = RequirementsService(repository)
    command = args.requirement_command
    if command == "create":
        record = service.create_requirement(
            requirement_id=args.id, title=args.title, description=args.description,
            business_value=args.business_value, priority=args.priority,
            created_by=args.created_by,
        )
        print(f"Created requirement {record['requirement_id']} (version {record['version']}).")
    elif command == "update":
        record = service.update_requirement(
            args.requirement_id,
            changed_by=args.changed_by,
            change_note=args.change_note,
            actor_role=args.actor_role,
            title=args.title,
            description=args.description,
            business_value=args.business_value,
            priority=args.priority,
            expected_version=args.expected_version,
        )
        print(f"Updated {args.requirement_id} to version {record['version']}.")
    elif command == "clarification":
        if args.clarification_command == "add":
            record = service.add_clarification(
                args.requirement, clarification_id=args.id, question=args.question,
                asked_by=args.asked_by, actor_role=args.actor_role,
            )
            print(f"Opened clarification {record['clarification_id']}.")
        else:
            record = service.answer_clarification(
                args.id, answer=args.answer, answered_by=args.answered_by,
                actor_role=args.actor_role,
            )
            print(f"Answered clarification {record['clarification_id']}.")
    elif command == "story":
        record = service.create_story(
            story_id=args.id, requirement_id=args.requirement, title=args.title,
            user_role=args.user_role, goal=args.goal, benefit=args.benefit,
            created_by=args.created_by, actor_role=args.actor_role,
        )
        print(f"Created user story {record['story_id']} for {record['requirement_id']}.")
    elif command == "criterion":
        record = service.add_acceptance_criterion(
            criterion_id=args.id, story_id=args.story, description=args.description,
            created_by=args.created_by, actor_role=args.actor_role,
        )
        print(f"Created acceptance criterion {record['criterion_id']}.")
    elif command == "test-case":
        record = service.create_test_case(
            test_case_id=args.id, title=args.title, description=args.description,
            test_level=args.test_level, created_by=args.created_by,
            actor_role=args.actor_role, automation_reference=args.automation_reference,
        )
        print(f"Created test case {record['test_case_id']}.")
    elif command == "map-test":
        service.map_test_case(
            criterion_id=args.criterion, test_case_id=args.test_case,
            mapped_by=args.mapped_by, actor_role=args.actor_role,
        )
        print(f"Mapped {args.test_case} to {args.criterion}.")
    elif command in {"submit-ba", "approve-ba", "approve-po", "request-changes"}:
        action = {
            "submit-ba": service.submit_for_ba_review,
            "approve-ba": service.approve_ba,
            "approve-po": service.approve_po,
            "request-changes": service.request_changes,
        }[command]
        role = (
            "product_owner"
            if command in {"approve-po", "request-changes"}
            else "business_analyst"
        )
        record = action(
            args.requirement_id, actor_id=args.actor_id, note=args.note, actor_role=role,
        )
        print(f"Requirement {args.requirement_id} is now '{record['status']}'.")
    elif command == "show":
        trace = service.get_traceability(args.requirement_id)
        record = trace["requirement"]
        print(f"Requirement: {record['requirement_id']} — {record['title']}")
        print(
            f"Status: {record['status']} | Version: {record['version']} "
            f"| Priority: {record['priority']}"
        )
        print(f"Business value: {record['business_value']}")
        open_questions = sum(
            1 for item in record["clarifications"] if item["status"] == "open"
        )
        print(f"Clarifications: {open_questions} open")
        for story in trace["stories"]:
            item = story["story"]
            print(f"  Story {item['story_id']} [{item['status']}]: {item['title']}")
            for criterion in story["criteria"]:
                c = criterion["criterion"]
                tests = ", ".join(
                    test["test_case_id"] for test in criterion["test_cases"]
                ) or "NOT MAPPED"
                print(f"    {c['criterion_id']}: {c['description']} | Tests: {tests}")
        print(f"Coverage: {trace['covered_criteria_count']}/{trace['acceptance_criteria_count']} "
              f"({trace['coverage_percent']}%)")
        print(
            f"Version history entries: {len(record['versions'])}; "
            f"audit events: {len(record['events'])}"
        )
    elif command == "brd":
        print(repository.get_requirement_brd(args.requirement_id))
    elif command == "list":
        rows = repository.list_requirements()
        if not rows:
            print("No business requirements found.")
        for row in rows:
            print(f"{row['requirement_id']}\t{row['status']}\tv{row['version']}\t{row['title']}")
    return 0


def _run_architecture_command(args: argparse.Namespace, repository: SQLiteRepository) -> int:
    service = ArchitectureService(repository)
    command = args.architecture_command
    if command == "create":
        record = service.create_package(
            package_id=args.id, feature_id=args.feature, requirement_id=args.requirement,
            created_by=args.created_by, actor_role=args.actor_role,
        )
        print(
            f"Created architecture package {record['package_id']} "
            f"(version {record['version_no']}, status {record['status']})."
        )
    elif command == "artifact":
        if args.content_file:
            artifact = service.add_artifact_from_file(
                package_id=args.package, artifact_type=args.artifact_type, title=args.title,
                content_file=args.content_file, created_by=args.created_by, actor_role="architect",
            )
        else:
            artifact = service.add_artifact(
                package_id=args.package, artifact_type=args.artifact_type, title=args.title,
                content=args.content, created_by=args.created_by, actor_role="architect",
            )
        print(f"Saved architecture section '{artifact['artifact_type']}' to {args.package}.")
    elif command == "adr":
        service.add_decision(
            package_id=args.package, decision_id=args.id, title=args.title,
            context=args.context, decision=args.decision, consequences=args.consequences,
            created_by=args.created_by, actor_role=args.actor_role,
        )
        print(f"Recorded ADR {args.id} in {args.package}.")
    elif command == "map-story":
        service.map_story(
            package_id=args.package, story_id=args.story, mapped_by=args.mapped_by,
            actor_role=args.actor_role,
        )
        print(f"Mapped story {args.story} to {args.package}.")
    elif command == "submit":
        record = service.submit(
            args.package_id, actor_id=args.actor_id, note=args.note, actor_role=args.actor_role,
        )
        print(f"Submitted {record['package_id']} for independent architecture review.")
    elif command == "review":
        record = service.review(
            args.package_id, outcome=args.outcome, reviewer_id=args.reviewer_id,
            note=args.note, evidence_uri=args.evidence, actor_role=args.actor_role,
        )
        print(f"Architecture package {record['package_id']} is now '{record['status']}'.")
    elif command == "checklist":
        checklist = service.checklist(args.package_id)
        print(f"Architecture checklist: {args.package_id}")
        print(f"Status: {checklist['status']}")
        print(f"Required artifact sections: {len(checklist['present_artifacts'])}/"
              f"{len(checklist['required_artifacts'])}")
        for missing in checklist["missing_artifacts"]:
            print(f"  MISSING: {missing}")
        print(f"Architecture decisions recorded: {checklist['decision_count']}")
        print(f"User stories mapped: {len(checklist['mapped_stories'])}/"
              f"{len(checklist['required_stories'])}")
        for story_id in checklist["unmapped_stories"]:
            print(f"  UNMAPPED: {story_id}")
        print(f"Complete: {'YES' if checklist['complete'] else 'NO'}")
    elif command == "show":
        record = service.get(args.package_id)
        print(f"Architecture: {record['package_id']} v{record['version_no']}")
        print(f"Feature: {record['feature_id']} — {record['feature_title']}")
        print(f"Requirement: {record['requirement_id']} — {record['requirement_title']}")
        print(f"Status: {record['status']} | Created by: {record['created_by']}")
        if record["approved_by"]:
            print(f"Approved by: {record['approved_by']} at {record['approved_at']}")
        print("Architecture artifacts:")
        for artifact in record["artifacts"]:
            print(
                f"  {artifact['artifact_type']} r{artifact['revision_no']}: {artifact['title']}"
            )
        print(f"Prior artifact revisions retained: {len(record['artifact_history'])}")
        print(f"ADRs: {len(record['decisions'])}")
        mapped_stories = ", ".join(item["story_id"] for item in record["story_mappings"])
        print(f"Mapped stories: {mapped_stories or 'none'}")
        print(f"Reviews: {len(record['reviews'])} | Audit events: {len(record['events'])}")
        if record["review_note"]:
            print(f"Latest review note: {record['review_note']}")
    return 0


def _run_command(args: argparse.Namespace, repository: SQLiteRepository) -> int:
    if args.command == "agent":
        identity_service = IdentityService(repository)
        if args.agent_command == "bootstrap-admin":
            credential = identity_service.bootstrap_admin(
                identity_id=args.id, display_name=args.name,
                expires_in_days=args.expires_in_days,
            )
            print(f"Bootstrapped control-plane administrator {credential.identity_id}.")
            print("Store this token securely; it is displayed only once:")
            print(credential.token)
        elif args.agent_command == "create":
            admin_token = os.getenv(args.admin_token_env)
            if not admin_token:
                raise AuthenticationError(
                    f"Set {args.admin_token_env} to an active identity_admin bearer token."
                )
            principal = identity_service.authenticate(admin_token, required_scope="identity.manage")
            credential = identity_service.create_identity(
                identity_id=args.id, display_name=args.name, role=args.role,
                identity_type=args.identity_type, capacity_points=args.capacity,
                expires_in_days=args.expires_in_days,
            )
            repository.record_identity_event(
                args.id, event_type="identity_registered_by_admin",
                actor_id=principal.identity_id, note="Registered by authenticated administrator.",
            )
            print(f"Registered {credential.identity_id}; role={args.role}.")
            print("Store this token securely; it is displayed only once:")
            print(credential.token)
        elif args.agent_command == "list":
            token = os.getenv(args.admin_token_env)
            if not token:
                raise AuthenticationError(f"Set {args.admin_token_env} to an admin token.")
            identity_service.authenticate(token, required_scope="identity.manage")
            for identity in repository.list_agent_identities():
                print(f"{identity['identity_id']}\t{identity['role']}\t{identity['status']}\t{identity['display_name']}")
        elif args.agent_command == "rotate-token":
            token = os.getenv(args.admin_token_env)
            if not token:
                raise AuthenticationError(f"Set {args.admin_token_env} to an admin token.")
            admin = identity_service.authenticate(token, required_scope="identity.manage")
            credential = identity_service.rotate_credential(
                args.id, actor_id=admin.identity_id, note=args.note,
                expires_in_days=args.expires_in_days,
            )
            print(f"Rotated active credentials for {args.id}.")
            print("Store this replacement token securely; it is displayed only once:")
            print(credential.token)
        elif args.agent_command == "revoke-token":
            token = os.getenv(args.admin_token_env)
            if not token:
                raise AuthenticationError(f"Set {args.admin_token_env} to an admin token.")
            admin = identity_service.authenticate(token, required_scope="identity.manage")
            if not identity_service.revoke_credential(
                args.credential_id, actor_id=admin.identity_id, note=args.note
            ):
                raise ValueError(f"Credential '{args.credential_id}' was not found")
            print(f"Revoked credential {args.credential_id}.")
        elif args.agent_command == "disable":
            token = os.getenv(args.admin_token_env)
            if not token:
                raise AuthenticationError(f"Set {args.admin_token_env} to an admin token.")
            admin = identity_service.authenticate(token, required_scope="identity.manage")
            identity_service.disable_identity(args.id, actor_id=admin.identity_id, note=args.note)
            print(f"Disabled identity {args.id} and revoked its credentials.")
        return 0

    if args.command == "auth":
        token = os.getenv(args.token_env)
        if not token:
            raise AuthenticationError(f"Environment variable {args.token_env} is not set.")
        principal = IdentityService(repository).authenticate(
            token, required_scope=args.require_scope
        )
        print(f"Authenticated: {principal.identity_id} ({principal.role.value})")
        print("Scopes:")
        for scope in sorted(principal.scopes):
            print(f"  {scope}")
        return 0

    if args.command == "github":
        identity_service = IdentityService(repository)
        command = args.github_command
        if command == "auth-check":
            adapter = GitHubCLIAdapter()
            if not adapter.auth_status():
                raise AuthenticationError("GitHub CLI is not authenticated; run 'gh auth login'.")
            print("GitHub CLI authentication confirmed. Credential value was not accessed or printed.")
        elif command == "repo":
            if args.github_repo_command == "add":
                admin_token = os.getenv(args.admin_token_env)
                if not admin_token:
                    raise AuthenticationError(f"Set {args.admin_token_env} to an admin token.")
                admin = identity_service.authenticate(
                    admin_token, required_scope="github.repository.register"
                )
                adapter = GitHubCLIAdapter()
                if not adapter.auth_status():
                    raise AuthenticationError("GitHub CLI is not authenticated; run 'gh auth login'.")
                remote = adapter.get_repository(args.owner, args.name)
                record = repository.register_github_repository(
                    repository_id=remote.full_name, owner=remote.owner, name=remote.name,
                    default_branch=remote.default_branch, provider="github_cli",
                    registered_by=admin.identity_id,
                )
                print(f"Registered {record['owner']}/{record['name']} (default: {record['default_branch']}).")
            else:
                token = os.getenv(args.token_env)
                if not token:
                    raise AuthenticationError(f"Set {args.token_env} to an agent token.")
                identity_service.authenticate(token, required_scope="github.read")
                for record in repository.list_github_repositories():
                    print(f"{record['owner']}/{record['name']}\t{record['default_branch']}\t{record['status']}")
        elif command == "branch-name":
            print(BranchPolicy.build(args.kind, args.work_id, args.summary))
        elif command == "worktree":
            if args.worktree_command == "add":
                token = os.getenv(args.token_env)
                if not token:
                    raise AuthenticationError(f"Set {args.token_env} to an agent token.")
                principal = identity_service.authenticate(token, required_scope="github.branch.create")
                record = repository.get_github_repository(args.repository_id)
                if record is None or record['status'] != 'active':
                    raise ValueError(f"Active repository '{args.repository_id}' is not registered")
                result = GitWorktreeManager().create(
                    args.repo_path, args.path, args.branch, args.base or str(record['default_branch'])
                )
                workspace_id = uuid4().hex
                repository.create_github_workspace(
                    workspace_id=workspace_id, repository_id=args.repository_id,
                    identity_id=principal.identity_id, branch_name=args.branch,
                    worktree_path=result['worktree_path'],
                )
                print(f"Created isolated worktree {result['worktree_path']} for {principal.identity_id}.")
            else:
                token = os.getenv(args.token_env)
                if not token:
                    raise AuthenticationError(f"Set {args.token_env} to an agent token.")
                principal = identity_service.authenticate(token, required_scope="github.branch.create")
                workspace = repository.get_github_workspace(str(Path(args.path).expanduser().resolve()))
                if workspace is None:
                    raise ValueError("Worktree is not registered or is already closed")
                if workspace['identity_id'] != principal.identity_id and "identity.manage" not in principal.scopes:
                    raise AuthorizationError("Only the assigned agent or an administrator can close this worktree")
                GitWorktreeManager().remove(args.repo_path, args.path)
                repository.close_github_workspace(str(workspace['workspace_id']))
                print(f"Removed worktree {Path(args.path).resolve()}.")
        elif command == "pr":
            record = repository.get_github_repository(args.repository_id)
            if record is None or record['status'] != 'active':
                raise ValueError(f"Active repository '{args.repository_id}' is not registered")
            adapter = GitHubCLIAdapter(cwd=getattr(args, 'cwd', None))
            if not adapter.auth_status():
                raise AuthenticationError("GitHub CLI is not authenticated; run 'gh auth login'.")
            remote = adapter.get_repository(str(record['owner']), str(record['name']))
            governance = GitHubGovernanceService(identity_service, adapter)
            token = os.getenv(args.token_env)
            if not token:
                raise AuthenticationError(f"Set {args.token_env} to an agent token.")
            if args.github_pr_command == "create":
                body = Path(args.body_file).read_text(encoding="utf-8")
                principal = identity_service.authenticate(token, required_scope="github.pr.create")
                if repository.get_feature(args.feature) is None:
                    raise ValueError(f"Feature '{args.feature}' does not exist")
                pr = governance.create_pull_request(
                    token, repository=remote, head=args.head,
                    base=args.base or str(record['default_branch']), title=args.title, body=body,
                )
                repository.create_github_pull_request(
                    pr_record_id=uuid4().hex, repository_id=args.repository_id,
                    feature_id=args.feature, head_branch=pr.head_branch, base_branch=pr.base_branch,
                    pr_number=pr.number, pr_url=pr.url, created_by=principal.identity_id,
                )
                print(f"Created PR #{pr.number}: {pr.url}")
            elif args.github_pr_command == "review":
                record_pr = next((row for row in repository.list_github_prs(args.repository_id)
                                  if row['pr_number'] == args.number), None)
                if record_pr is None:
                    raise ValueError(f"PR #{args.number} is not registered in the orchestrator database")
                principal = governance.review_pull_request(
                    token, repository=remote, number=args.number,
                    outcome=args.outcome, note=args.note,
                    pull_request_author_id=str(record_pr['created_by']),
                )
                repository.record_github_pr_review(
                    pr_record_id=str(record_pr['pr_record_id']), reviewer_id=principal.identity_id,
                    outcome=args.outcome, note=args.note,
                )
                repository.update_github_pull_request_status(
                    str(record_pr['pr_record_id']), 'approved' if args.outcome == 'approved' else 'changes_requested'
                )
                print(f"Recorded {args.outcome} review for PR #{args.number}.")
            elif args.github_pr_command == "merge":
                record_pr = next((row for row in repository.list_github_prs(args.repository_id)
                                  if row['pr_number'] == args.number), None)
                if record_pr is None:
                    raise ValueError(f"PR #{args.number} is not registered in the orchestrator database")
                gate_snapshot = adapter.get_pull_request_gate(remote, args.number)
                conclusion_map = {
                    "success": "success", "failure": "failure", "failed": "failure",
                    "error": "failure", "pending": "pending", "queued": "pending",
                    "in_progress": "pending", "cancelled": "cancelled", "skipped": "skipped",
                    "neutral": "neutral",
                }
                for check in gate_snapshot.checks:
                    conclusion = conclusion_map.get(check.state.lower(), "pending")
                    repository.record_github_ci_check(
                        pr_record_id=str(record_pr['pr_record_id']), check_name=check.name,
                        conclusion=conclusion, details_url=check.url,
                    )
                governance.merge_pull_request(token, repository=remote, number=args.number)
                repository.update_github_pull_request_status(str(record_pr['pr_record_id']), 'merged')
                print(f"Merged PR #{args.number} after review and CI gates passed.")
        return 0

    if args.command == "architecture":
        return _run_architecture_command(args, repository)

    if args.command == "requirement":
        return _run_requirement_command(args, repository)

    if args.command == "feature":
        if args.feature_command == "create":
            request = FeatureRequest(args.id, args.title, args.problem, tuple(args.ac))
            record = repository.create_feature(request)
            print(f"Created {record.request.feature_id} in state '{record.state.value}'.")
        elif args.feature_command == "list":
            records = repository.list_features()
            if not records:
                print("No features found.")
            for record in records:
                print(f"{record.request.feature_id}\t{record.state.value}\t{record.request.title}")
        elif args.feature_command == "show":
            record = repository.get_feature(args.feature_id)
            if record is None:
                raise WorkflowValidationError(f"Feature '{args.feature_id}' does not exist.")
            print(f"Feature: {record.request.feature_id} — {record.request.title}")
            print(f"State: {record.state.value} | Version: {record.version}")
            print(f"Problem: {record.request.problem_statement}")
            print("Acceptance criteria:")
            for index, criterion in enumerate(record.request.acceptance_criteria, start=1):
                print(f"  AC-{index:03d}: {criterion}")
            workflow = repository.get_workflow(args.feature_id)
            assert workflow is not None
            print("Audit history:")
            if not workflow.history:
                print("  No transitions recorded.")
            for event in workflow.history:
                print(
                    f"  #{event.event_id} {event.action.value}: {event.from_state.value} -> "
                    f"{event.to_state.value} | {event.actor_id} ({event.actor_role.value})"
                )
                if event.evidence_uri:
                    print(f"     Evidence: {event.evidence_uri}")
        elif args.feature_command == "transition":
            action = Action(args.action)
            token = os.getenv(args.token_env)
            if token:
                event = AuthenticatedWorkflowGateway(
                    IdentityService(repository), WorkflowService(repository)
                ).apply(
                    token, args.feature_id, action, note=args.note,
                    evidence_uri=args.evidence,
                )
            elif args.unsafe_local_demo:
                if not args.unsafe_local_demo_role or not args.unsafe_local_demo_actor_id:
                    raise ValueError(
                        "Unsafe local demo mode requires --unsafe-local-demo-role and "
                        "--unsafe-local-demo-actor-id."
                    )
                event = WorkflowService(repository).apply(
                    args.feature_id, action, Role(args.unsafe_local_demo_role),
                    actor_id=args.unsafe_local_demo_actor_id,
                    note=args.note, evidence_uri=args.evidence,
                )
            else:
                raise AuthenticationError(
                    f"No token found in {args.token_env}. Bootstrap an admin, create an agent, "
                    "and export its token. For isolated tests only, pass --unsafe-local-demo."
                )
            print(
                f"Accepted event #{event.event_id}: {event.action.value}; "
                f"{event.from_state.value} -> {event.to_state.value}."
            )
        return 0

    if args.command == "resource":
        if args.resource_command == "add":
            record = repository.create_resource(
                args.id, args.name, Role(args.role), capacity_points=args.capacity
            )
            print(f"Registered {record.resource_id} ({record.role.value}).")
        else:
            resources = repository.list_resources()
            if not resources:
                print("No resources registered.")
            for resource_record in resources:
                active = "active" if resource_record.active else "inactive"
                print(
                    f"{resource_record.resource_id}\t{resource_record.role.value}\t"
                    f"{resource_record.capacity_points:g} pts\t{active}\t"
                    f"{resource_record.display_name}"
                )
        return 0

    if args.command == "work-item":
        if args.work_item_command == "create":
            record = repository.create_work_item(
                work_item_id=args.id,
                feature_id=args.feature,
                title=args.title,
                description=args.description,
                item_type=args.item_type,
                priority=args.priority,
                estimate_points=args.estimate,
            )
            print(f"Created {record.work_item_id} for {record.feature_id}.")
        elif args.work_item_command == "assign":
            repository.assign_work_item(
                work_item_id=args.id,
                resource_id=args.resource,
                assigned_by=args.assigned_by,
                allocation_percent=args.allocation,
            )
            print(f"Assigned {args.id} to {args.resource}.")
        elif args.work_item_command == "status":
            repository.update_work_item_status(
                work_item_id=args.id,
                status=args.status,
                actor_id=args.actor_id,
                note=args.note,
                evidence_uri=args.evidence,
            )
            print(f"Updated {args.id} to '{args.status}'.")
        elif args.work_item_command == "history":
            history = repository.get_work_item_activity(args.work_item_id)
            if not history:
                print("No activity found (or the work item does not exist).")
            for activity in history:
                transition = ""
                if activity["from_status"] or activity["to_status"]:
                    transition = f" {activity['from_status']} -> {activity['to_status']}"
                print(
                    f"{activity['occurred_at']} | {activity['event_type']}{transition} | "
                    f"{activity['actor_id']} | {activity['note']}"
                )
                if activity["evidence_uri"]:
                    print(f"  Evidence: {activity['evidence_uri']}")
        else:
            items = repository.list_work_items(args.feature)
            if not items:
                print("No work items found.")
            for work_item in items:
                owners = ",".join(work_item.assignees) or "unassigned"
                print(
                    f"{work_item.work_item_id}\t{work_item.status}\t{work_item.priority}\t"
                    f"{owners}\t{work_item.title}"
                )
        return 0

    if args.command == "scrum" and args.scrum_command == "summary":
        summary = repository.scrum_summary()
        print("Scrum summary (derived from local database records):")
        for name, value in summary.items():
            print(f"  {name.replace('_', ' ').title()}: {value}")
        print("Resource workload (assignment and completion counts):")
        workload = repository.resource_workload_summary()
        if not workload:
            print("  No active resources registered.")
        for resource_row in workload:
            print(
                f"  {resource_row['resource_id']} ({resource_row['role']}): "
                f"{resource_row['assigned_items']} assigned, "
                f"{resource_row['completed_items']} completed, "
                f"{resource_row['open_items']} open / "
                f"{resource_row['capacity_points']:g} capacity points"
            )
        return 0

    raise WorkflowValidationError("Unsupported command.")


if __name__ == "__main__":
    raise SystemExit(main())
