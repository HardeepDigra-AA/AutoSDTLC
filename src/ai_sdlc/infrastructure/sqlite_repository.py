"""SQLite persistence adapter for features, workflow history, resources, and work items.

The repository deliberately uses Python's standard-library sqlite3 module so the local
starter has no runtime dependency. The service/domain boundary allows a PostgreSQL adapter
to replace this repository later without changing the workflow rules.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ai_sdlc.domain.requirements import RequirementStatus
from ai_sdlc.domain.workflow import (
    Action,
    FeatureRequest,
    FeatureWorkflow,
    Role,
    WorkflowEvent,
    WorkflowState,
    WorkflowValidationError,
)

SCHEMA_VERSION = 4


@dataclass(frozen=True, slots=True)
class FeatureRecord:
    request: FeatureRequest
    state: WorkflowState
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class ResourceRecord:
    resource_id: str
    display_name: str
    role: Role
    capacity_points: float
    active: bool


@dataclass(frozen=True, slots=True)
class WorkItemRecord:
    work_item_id: str
    feature_id: str
    title: str
    description: str
    item_type: str
    status: str
    priority: str
    estimate_points: float | None
    assignees: tuple[str, ...]
    created_at: datetime
    updated_at: datetime


class SQLiteRepository:
    """A small repository with one short-lived connection per operation."""

    def __init__(self, database_path: str | Path = "data/ai_sdlc.db") -> None:
        raw_path = str(database_path)
        self._use_uri = raw_path == ":memory:"
        self._anchor_connection: sqlite3.Connection | None = None
        if self._use_uri:
            self.database_path = f"file:ai_sdlc_{uuid4().hex}?mode=memory&cache=shared"
            # Keep one connection open so short-lived operation connections share this DB.
            self._anchor_connection = sqlite3.connect(self.database_path, uri=True)
        else:
            self.database_path = str(Path(raw_path).expanduser())
            Path(self.database_path).resolve().parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10.0, uri=self._use_uri)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def close(self) -> None:
        """Release the keeper connection used by an in-memory database."""
        if self._anchor_connection is not None:
            self._anchor_connection.close()
            self._anchor_connection = None

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create tables and record the current schema version; safe to run repeatedly."""
        schema = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS features (
            feature_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            problem_statement TEXT NOT NULL,
            state TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS acceptance_criteria (
            feature_id TEXT NOT NULL,
            criterion_id TEXT NOT NULL,
            sequence_no INTEGER NOT NULL CHECK (sequence_no > 0),
            description TEXT NOT NULL,
            PRIMARY KEY (feature_id, criterion_id),
            UNIQUE (feature_id, sequence_no),
            FOREIGN KEY (feature_id) REFERENCES features(feature_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS workflow_events (
            feature_id TEXT NOT NULL,
            event_id INTEGER NOT NULL CHECK (event_id > 0),
            action TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            actor_role TEXT NOT NULL,
            from_state TEXT NOT NULL,
            to_state TEXT NOT NULL,
            note TEXT NOT NULL,
            evidence_uri TEXT,
            occurred_at TEXT NOT NULL,
            PRIMARY KEY (feature_id, event_id),
            FOREIGN KEY (feature_id) REFERENCES features(feature_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS resources (
            resource_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            capacity_points REAL NOT NULL DEFAULT 0 CHECK (capacity_points >= 0),
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS work_items (
            work_item_id TEXT PRIMARY KEY,
            feature_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            item_type TEXT NOT NULL CHECK (item_type IN ('task', 'defect', 'test_case')),
            status TEXT NOT NULL DEFAULT 'todo'
                CHECK (status IN ('todo', 'in_progress', 'blocked', 'done')),
            priority TEXT NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('low', 'medium', 'high', 'critical')),
            estimate_points REAL CHECK (estimate_points IS NULL OR estimate_points >= 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (feature_id) REFERENCES features(feature_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS work_item_assignments (
            work_item_id TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            assigned_by TEXT NOT NULL,
            allocation_percent REAL NOT NULL DEFAULT 100
                CHECK (allocation_percent > 0 AND allocation_percent <= 100),
            assigned_at TEXT NOT NULL,
            PRIMARY KEY (work_item_id, resource_id),
            FOREIGN KEY (work_item_id) REFERENCES work_items(work_item_id) ON DELETE CASCADE,
            FOREIGN KEY (resource_id) REFERENCES resources(resource_id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS work_item_activity (
            activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_item_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            resource_id TEXT,
            from_status TEXT,
            to_status TEXT,
            note TEXT NOT NULL,
            evidence_uri TEXT,
            occurred_at TEXT NOT NULL,
            FOREIGN KEY (work_item_id) REFERENCES work_items(work_item_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_features_state ON features(state);
        CREATE INDEX IF NOT EXISTS idx_work_items_feature ON work_items(feature_id);
        CREATE INDEX IF NOT EXISTS idx_work_items_status ON work_items(status);
        CREATE INDEX IF NOT EXISTS idx_assignments_resource ON work_item_assignments(resource_id);
        CREATE INDEX IF NOT EXISTS idx_activity_work_item_time
            ON work_item_activity(work_item_id, occurred_at);
        CREATE INDEX IF NOT EXISTS idx_events_feature_time
            ON workflow_events(feature_id, occurred_at);
        """
        with self._connection() as connection:
            connection.executescript(schema)
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (1, ?)",
                (_now(),),
            )
            current_version = int(
                connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
            )
            if current_version < 2:
                connection.executescript(REQUIREMENTS_MIGRATION_2)
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (2, ?)",
                    (_now(),),
                )
                current_version = 2
            if current_version < 3:
                connection.executescript(ARCHITECTURE_MIGRATION_3)
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (3, ?)",
                    (_now(),),
                )
                current_version = 3
            if current_version < 4:
                connection.executescript(IDENTITY_GITHUB_MIGRATION_4)
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (4, ?)",
                    (_now(),),
                )

    # Requirement and traceability methods are kept in the persistence adapter so the
    # service layer can later target PostgreSQL without changing the workflow use cases.
    def create_requirement(
        self, *, requirement_id: str, title: str, description: str, business_value: str,
        priority: str, created_by: str,
    ) -> dict[str, object]:
        _validate_priority(priority)
        now = _now()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO business_requirements
                   (requirement_id, title, description, business_value, priority, status,
                    version, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'draft', 1, ?, ?, ?)""",
                (
                    requirement_id, title, description, business_value, priority,
                    created_by, now, now,
                ),
            )
            connection.execute(
                """INSERT INTO requirement_versions
                   (requirement_id, version_no, title, description, business_value, priority,
                    change_note, changed_by, changed_at)
                   VALUES (?, 1, ?, ?, ?, ?, 'Initial requirement intake', ?, ?)""",
                (requirement_id, title, description, business_value, priority, created_by, now),
            )
            self._requirement_event(
                connection, requirement_id, "created", created_by, "requester", "",
                "draft", "Requirement captured.", now,
            )
        return self.get_requirement(requirement_id)

    def get_requirement(self, requirement_id: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM business_requirements WHERE requirement_id = ?",
                (requirement_id,),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["clarifications"] = [
                dict(item) for item in connection.execute(
                    "SELECT * FROM requirement_clarifications WHERE requirement_id = ? "
                    "ORDER BY asked_at, clarification_id", (requirement_id,),
                ).fetchall()
            ]
            result["stories"] = [
                dict(item) for item in connection.execute(
                    "SELECT * FROM user_stories WHERE requirement_id = ? ORDER BY story_id",
                    (requirement_id,),
                ).fetchall()
            ]
            result["versions"] = [
                dict(item) for item in connection.execute(
                    "SELECT * FROM requirement_versions WHERE requirement_id = ? "
                    "ORDER BY version_no", (requirement_id,),
                ).fetchall()
            ]
            result["events"] = [
                dict(item) for item in connection.execute(
                    "SELECT * FROM requirement_events WHERE requirement_id = ? "
                    "ORDER BY event_id", (requirement_id,),
                ).fetchall()
            ]
        return result

    def list_requirements(self) -> list[dict[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT requirement_id, title, priority, status, version, created_at, updated_at "
                "FROM business_requirements ORDER BY created_at, requirement_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def update_requirement(
        self, requirement_id: str, *, changes: dict[str, object], changed_by: str,
        actor_role: str, change_note: str, expected_version: int | None = None,
    ) -> dict[str, object]:
        allowed = {"title", "description", "business_value", "priority"}
        if not changes or set(changes) - allowed:
            raise ValueError(
                "Only title, description, business_value, and priority can be updated."
            )
        if "priority" in changes:
            _validate_priority(str(changes["priority"]))
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT * FROM business_requirements WHERE requirement_id = ?", (requirement_id,)
            ).fetchone()
            if current is None:
                raise ValueError(f"Requirement '{requirement_id}' does not exist.")
            if current["status"] not in {"draft", "changes_requested"}:
                raise ValueError("Only draft or changes-requested requirements can be edited.")
            if expected_version is not None and int(current["version"]) != expected_version:
                raise ValueError(
                    f"Requirement version changed from {expected_version} to {current['version']}; "
                    "reload before updating."
                )
            updated = {key: changes.get(key, current[key]) for key in allowed}
            new_version = int(current["version"]) + 1
            now = _now()
            connection.execute(
                """UPDATE business_requirements SET title = ?, description = ?, business_value = ?,
                   priority = ?, version = ?, updated_at = ? WHERE requirement_id = ? """,
                (updated["title"], updated["description"], updated["business_value"],
                 updated["priority"], new_version, now, requirement_id),
            )
            connection.execute(
                """INSERT INTO requirement_versions
                   (requirement_id, version_no, title, description, business_value, priority,
                    change_note, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (requirement_id, new_version, updated["title"], updated["description"],
                 updated["business_value"], updated["priority"], change_note, changed_by, now),
            )
            self._requirement_event(
                connection, requirement_id, "updated", changed_by, actor_role, current["status"],
                current["status"], change_note, now,
            )
        return self.get_requirement(requirement_id)

    def add_requirement_clarification(
        self, *, requirement_id: str, clarification_id: str, question: str, asked_by: str,
    ) -> dict[str, object]:
        now = _now()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT status FROM business_requirements WHERE requirement_id = ?",
                (requirement_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Requirement '{requirement_id}' does not exist.")
            if row["status"] not in {"draft", "changes_requested", "clarification_required"}:
                raise ValueError("Clarifications can only be raised before BA review submission.")
            connection.execute(
                """INSERT INTO requirement_clarifications
                   (clarification_id, requirement_id, question, status, asked_by, asked_at)
                   VALUES (?, ?, ?, 'open', ?, ?)""",
                (clarification_id, requirement_id, question, asked_by, now),
            )
            connection.execute(
                "UPDATE business_requirements SET status = 'clarification_required', "
                "updated_at = ? WHERE requirement_id = ?", (now, requirement_id),
            )
            self._requirement_event(
                connection, requirement_id, "clarification_opened", asked_by,
                "business_analyst", row["status"], "clarification_required", question, now,
            )
        return self.get_requirement_clarification(clarification_id)

    def answer_requirement_clarification(
        self, *, clarification_id: str, answer: str, answered_by: str,
    ) -> dict[str, object]:
        now = _now()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM requirement_clarifications WHERE clarification_id = ?",
                (clarification_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Clarification '{clarification_id}' does not exist.")
            if row["status"] != "open":
                raise ValueError(f"Clarification '{clarification_id}' is already answered.")
            connection.execute(
                """UPDATE requirement_clarifications SET status = 'answered', answer = ?,
                   answered_by = ?, answered_at = ? WHERE clarification_id = ?""",
                (answer, answered_by, now, clarification_id),
            )
            open_count = connection.execute(
                """SELECT COUNT(*) FROM requirement_clarifications
                   WHERE requirement_id = ? AND status = 'open'""", (row["requirement_id"],),
            ).fetchone()[0]
            current_status = "clarification_required" if open_count else "draft"
            connection.execute(
                "UPDATE business_requirements SET status = ?, updated_at = ? "
                "WHERE requirement_id = ?",
                (current_status, now, row["requirement_id"]),
            )
            self._requirement_event(
                connection, row["requirement_id"], "clarification_answered", answered_by,
                "requester", "clarification_required", current_status,
                f"Answered {clarification_id}.", now,
            )
        return self.get_requirement_clarification(clarification_id)

    def get_requirement_clarification(self, clarification_id: str) -> dict[str, object]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM requirement_clarifications WHERE clarification_id = ?",
                (clarification_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Clarification '{clarification_id}' does not exist.")
        return dict(row)

    def create_user_story(
        self, *, story_id: str, requirement_id: str, title: str, user_role: str, goal: str,
        benefit: str, created_by: str,
    ) -> dict[str, object]:
        now = _now()
        with self._connection() as connection:
            requirement = connection.execute(
                "SELECT status FROM business_requirements WHERE requirement_id = ?",
                (requirement_id,),
            ).fetchone()
            if requirement is None:
                raise ValueError(f"Requirement '{requirement_id}' does not exist.")
            if requirement["status"] not in {"draft", "changes_requested"}:
                raise ValueError("Stories can only be drafted before BA review submission.")
            connection.execute(
                """INSERT INTO user_stories
                   (story_id, requirement_id, title, user_role, goal, benefit, status, created_by,
                    version, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, 1, ?, ?)""",
                (story_id, requirement_id, title, user_role, goal, benefit, created_by, now, now),
            )
            self._requirement_event(
                connection, requirement_id, "story_created", created_by, "business_analyst",
                requirement["status"], requirement["status"], f"Created {story_id}: {title}", now,
            )
        return self.get_user_story(story_id)

    def get_user_story(self, story_id: str) -> dict[str, object]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM user_stories WHERE story_id = ?", (story_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"User story '{story_id}' does not exist.")
            result = dict(row)
            result["acceptance_criteria"] = [
                dict(item) for item in connection.execute(
                    "SELECT * FROM story_acceptance_criteria WHERE story_id = ? "
                    "ORDER BY sequence_no", (story_id,),
                ).fetchall()
            ]
        return result

    def create_story_acceptance_criterion(
        self, *, criterion_id: str, story_id: str, description: str, created_by: str,
    ) -> dict[str, object]:
        now = _now()
        with self._connection() as connection:
            story = connection.execute(
                """SELECT s.requirement_id, r.status FROM user_stories s
                   JOIN business_requirements r ON r.requirement_id = s.requirement_id
                   WHERE s.story_id = ?""", (story_id,),
            ).fetchone()
            if story is None:
                raise ValueError(f"User story '{story_id}' does not exist.")
            if story["status"] not in {"draft", "changes_requested"}:
                raise ValueError(
                    "Acceptance criteria can only be drafted before BA review submission."
                )
            sequence = int(connection.execute(
                "SELECT COALESCE(MAX(sequence_no), 0) + 1 FROM story_acceptance_criteria "
                "WHERE story_id = ?", (story_id,),
            ).fetchone()[0])
            connection.execute(
                """INSERT INTO story_acceptance_criteria
                   (criterion_id, story_id, sequence_no, description, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (criterion_id, story_id, sequence, description, created_by, now),
            )
            self._requirement_event(
                connection, story["requirement_id"], "acceptance_criterion_created", created_by,
                "business_analyst", story["status"], story["status"],
                f"Created {criterion_id} for {story_id}.", now,
            )
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM story_acceptance_criteria WHERE criterion_id = ?",
                (criterion_id,),
            ).fetchone()
        return dict(row)

    def create_traceability_test_case(
        self, *, test_case_id: str, title: str, description: str, test_level: str,
        created_by: str, automation_reference: str | None = None,
    ) -> dict[str, object]:
        allowed_levels = {"unit", "api", "ui", "integration", "security", "accessibility", "rag"}
        if test_level not in allowed_levels:
            raise ValueError(f"Unsupported test level '{test_level}'.")
        now = _now()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO traceability_test_cases
                   (test_case_id, title, description, test_level, status, automation_reference,
                    created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?)""",
                (test_case_id, title, description, test_level, automation_reference,
                 created_by, now, now),
            )
        return self.get_traceability_test_case(test_case_id)

    def get_traceability_test_case(self, test_case_id: str) -> dict[str, object]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM traceability_test_cases WHERE test_case_id = ?", (test_case_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Test case '{test_case_id}' does not exist.")
        return dict(row)

    def map_test_case_to_criterion(
        self, *, criterion_id: str, test_case_id: str, mapped_by: str,
    ) -> dict[str, object]:
        now = _now()
        with self._connection() as connection:
            row = connection.execute(
                """SELECT c.story_id, s.requirement_id, r.status
                   FROM story_acceptance_criteria c
                   JOIN user_stories s ON s.story_id = c.story_id
                   JOIN business_requirements r ON r.requirement_id = s.requirement_id
                   WHERE c.criterion_id = ?""", (criterion_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Acceptance criterion '{criterion_id}' does not exist.")
            if row["status"] != "po_review":
                raise ValueError("Test-case traceability can only be mapped during PO review.")
            test_case = connection.execute(
                "SELECT test_case_id FROM traceability_test_cases WHERE test_case_id = ?",
                (test_case_id,),
            ).fetchone()
            if test_case is None:
                raise ValueError(f"Test case '{test_case_id}' does not exist.")
            cursor = connection.execute(
                """INSERT OR IGNORE INTO criterion_test_case_map
                   (criterion_id, test_case_id, mapped_by, mapped_at) VALUES (?, ?, ?, ?)""",
                (criterion_id, test_case_id, mapped_by, now),
            )
            if cursor.rowcount == 1:
                self._requirement_event(
                    connection, row["requirement_id"], "test_case_mapped", mapped_by,
                    "qa_engineer", "po_review", "po_review",
                    f"Mapped {test_case_id} to {criterion_id}.", now,
                )
        with self._connection() as connection:
            mapped = connection.execute(
                "SELECT * FROM criterion_test_case_map WHERE criterion_id = ? AND test_case_id = ?",
                (criterion_id, test_case_id),
            ).fetchone()
        return dict(mapped)

    def get_requirement_traceability(self, requirement_id: str) -> dict[str, object]:
        requirement = self.get_requirement(requirement_id)
        if requirement is None:
            raise ValueError(f"Requirement '{requirement_id}' does not exist.")
        with self._connection() as connection:
            stories = connection.execute(
                "SELECT * FROM user_stories WHERE requirement_id = ? ORDER BY story_id",
                (requirement_id,),
            ).fetchall()
            story_results: list[dict[str, object]] = []
            for story in stories:
                criteria = connection.execute(
                    "SELECT * FROM story_acceptance_criteria "
                    "WHERE story_id = ? ORDER BY sequence_no",
                    (story["story_id"],),
                ).fetchall()
                criterion_results = []
                for criterion in criteria:
                    tests = connection.execute(
                        """SELECT t.* FROM traceability_test_cases t
                           JOIN criterion_test_case_map m ON m.test_case_id = t.test_case_id
                           WHERE m.criterion_id = ? ORDER BY t.test_case_id""",
                        (criterion["criterion_id"],),
                    ).fetchall()
                    criterion_results.append({
                        "criterion": dict(criterion),
                        "test_cases": [dict(test) for test in tests],
                        "covered": bool(tests),
                    })
                story_results.append({"story": dict(story), "criteria": criterion_results})
        criteria_count = sum(len(item["criteria"]) for item in story_results)
        covered_count = sum(
            1 for story in story_results for criterion in story["criteria"] if criterion["covered"]
        )
        return {
            "requirement": requirement,
            "stories": story_results,
            "acceptance_criteria_count": criteria_count,
            "covered_criteria_count": covered_count,
            "coverage_percent": round(covered_count * 100 / criteria_count, 2)
            if criteria_count else 0.0,
            "uncovered_criteria": [
                criterion["criterion"]["criterion_id"]
                for story in story_results for criterion in story["criteria"]
                if not criterion["covered"]
            ],
        }

    def get_requirement_brd(self, requirement_id: str) -> str:
        trace = self.get_requirement_traceability(requirement_id)
        requirement = trace["requirement"]
        lines = [
            f"# {requirement['requirement_id']} — {requirement['title']}", "",
            f"**Status:** {requirement['status']}  ",
            f"**Priority:** {requirement['priority']}  ",
            f"**Version:** {requirement['version']}", "",
            "## Business requirement", "", str(requirement["description"]), "",
            "## Business value", "", str(requirement["business_value"]), "",
            "## User stories", "",
        ]
        for story in trace["stories"]:
            item = story["story"]
            lines.extend([
                f"### {item['story_id']} — {item['title']}", "",
                f"As a {item['user_role']}, I want {item['goal']}, so that {item['benefit']}.", "",
                "#### Acceptance criteria", "",
            ])
            for criterion in story["criteria"]:
                c = criterion["criterion"]
                lines.append(f"- **{c['criterion_id']}** {c['description']}")
                if criterion["test_cases"]:
                    for test in criterion["test_cases"]:
                        lines.append(f"  - Test: {test['test_case_id']} ({test['test_level']})")
                else:
                    lines.append("  - Test coverage: NOT MAPPED")
            lines.append("")
        lines.extend(["## Clarification log", ""])
        if requirement["clarifications"]:
            for item in requirement["clarifications"]:
                lines.extend([
                    f"- **{item['clarification_id']}** ({item['status']}): {item['question']}",
                    f"  - Answer: {item['answer'] or 'Pending'}",
                    f"  - Asked by: {item['asked_by']}; answered by: "
                    f"{item['answered_by'] or 'Pending'}",
                ])
        else:
            lines.append("No clarification questions recorded.")
        lines.extend(["", "## Requirement version history", ""])
        for version in requirement["versions"]:
            lines.append(
                f"- **Version {version['version_no']}** — {version['change_note']} "
                f"(changed by {version['changed_by']} on {version['changed_at']})"
            )
        lines.extend([
            "", "## Traceability summary", "",
            f"Acceptance criteria covered: {trace['covered_criteria_count']} / "
            f"{trace['acceptance_criteria_count']} ({trace['coverage_percent']}%)", "",
        ])
        return "\n".join(lines)

    def transition_requirement(
        self, requirement_id: str, *, to_status: RequirementStatus, actor_id: str,
        actor_role: str, note: str, allowed_from: set[RequirementStatus], event_type: str,
        validate_submission: bool = False, validate_traceability: bool = False,
        approve_stories: bool = False,
    ) -> dict[str, object]:
        now = _now()
        target_status = str(to_status.value)
        allowed_values = {str(item.value) for item in allowed_from}
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            requirement = connection.execute(
                "SELECT * FROM business_requirements WHERE requirement_id = ?", (requirement_id,),
            ).fetchone()
            if requirement is None:
                raise ValueError(f"Requirement '{requirement_id}' does not exist.")
            if requirement["status"] not in allowed_values:
                raise ValueError(
                    f"Cannot move requirement from '{requirement['status']}' to '{target_status}'."
                )
            if validate_submission:
                open_clarifications = int(connection.execute(
                    """SELECT COUNT(*) FROM requirement_clarifications
                       WHERE requirement_id = ? AND status = 'open'""", (requirement_id,),
                ).fetchone()[0])
                if open_clarifications:
                    raise ValueError(
                        f"Cannot submit: {open_clarifications} clarification(s) remain open."
                    )
                stories = connection.execute(
                    "SELECT story_id FROM user_stories WHERE requirement_id = ?", (requirement_id,),
                ).fetchall()
                if not stories:
                    raise ValueError("Cannot submit: create at least one BA-owned user story.")
                missing = connection.execute(
                    """SELECT s.story_id FROM user_stories s
                       LEFT JOIN story_acceptance_criteria c ON c.story_id = s.story_id
                       WHERE s.requirement_id = ? GROUP BY s.story_id """
                    "HAVING COUNT(c.criterion_id) = 0",
                    (requirement_id,),
                ).fetchall()
                if missing:
                    ids = ", ".join(row["story_id"] for row in missing)
                    raise ValueError(f"Cannot submit: stories without acceptance criteria: {ids}.")
            if validate_traceability:
                missing = connection.execute(
                    """SELECT c.criterion_id FROM story_acceptance_criteria c
                       JOIN user_stories s ON s.story_id = c.story_id
                       LEFT JOIN criterion_test_case_map m ON m.criterion_id = c.criterion_id
                       WHERE s.requirement_id = ? GROUP BY c.criterion_id
                       HAVING COUNT(m.test_case_id) = 0 ORDER BY c.criterion_id""",
                    (requirement_id,),
                ).fetchall()
                if missing:
                    ids = ", ".join(row["criterion_id"] for row in missing)
                    raise ValueError(
                        "PO approval blocked: every acceptance criterion needs at least one "
                        f"mapped test case. Uncovered: {ids}."
                    )
            connection.execute(
                "UPDATE business_requirements SET status = ?, updated_at = ? "
                "WHERE requirement_id = ?",
                (target_status, now, requirement_id),
            )
            if approve_stories:
                connection.execute(
                    "UPDATE user_stories SET status = 'approved', updated_at = ? "
                    "WHERE requirement_id = ?", (now, requirement_id),
                )
            self._requirement_event(
                connection, requirement_id, event_type, actor_id, actor_role,
                requirement["status"], target_status, note, now,
            )
        return self.get_requirement(requirement_id)

    @staticmethod
    def _requirement_event(
        connection: sqlite3.Connection, requirement_id: str, event_type: str, actor_id: str,
        actor_role: str, from_status: str, to_status: str, note: str, occurred_at: str,
    ) -> None:
        connection.execute(
            """INSERT INTO requirement_events
               (requirement_id, event_type, actor_id, actor_role, from_status, to_status, note,
                occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (requirement_id, event_type, actor_id, actor_role, from_status, to_status, note,
             occurred_at),
        )

    # Solution architecture and TDD package persistence.
    def create_architecture_package(
        self, *, package_id: str, feature_id: str, requirement_id: str, created_by: str,
    ) -> dict[str, object]:
        now = _now()
        with self._connection() as connection:
            feature = connection.execute(
                "SELECT state FROM features WHERE feature_id = ?", (feature_id,)
            ).fetchone()
            if feature is None:
                raise ValueError(f"Feature '{feature_id}' does not exist.")
            if feature["state"] != WorkflowState.ARCHITECTURE_REVIEW.value:
                raise ValueError(
                    "Architecture packages can only be created while the feature is in "
                    "'architecture_review'."
                )
            requirement = connection.execute(
                "SELECT status FROM business_requirements WHERE requirement_id = ?",
                (requirement_id,),
            ).fetchone()
            if requirement is None:
                raise ValueError(f"Requirement '{requirement_id}' does not exist.")
            if requirement["status"] != RequirementStatus.APPROVED.value:
                raise ValueError(
                    f"Requirement '{requirement_id}' must be Product Owner approved before "
                    "architecture design can begin."
                )
            version_no = int(connection.execute(
                "SELECT COALESCE(MAX(version_no), 0) + 1 FROM architecture_packages "
                "WHERE feature_id = ?", (feature_id,),
            ).fetchone()[0])
            connection.execute(
                """INSERT INTO architecture_packages
                   (package_id, feature_id, requirement_id, version_no, status, created_by,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'draft', ?, ?, ?)""",
                (package_id, feature_id, requirement_id, version_no, created_by, now, now),
            )
            self._architecture_event(
                connection, package_id, "created", created_by,
                f"Architecture package version {version_no} created.", now,
            )
        return self.get_architecture_package(package_id)

    def add_architecture_artifact(
        self, *, package_id: str, artifact_type: str, title: str, content: str,
        created_by: str, source_uri: str | None = None,
    ) -> dict[str, object]:
        now = _now()
        with self._connection() as connection:
            package = self._editable_architecture_package(connection, package_id)
            previous = connection.execute(
                "SELECT * FROM architecture_artifacts WHERE package_id = ? AND artifact_type = ?",
                (package_id, artifact_type),
            ).fetchone()
            if previous is not None:
                connection.execute(
                    """INSERT INTO architecture_artifact_history
                       (package_id, artifact_type, revision_no, title, content, source_uri,
                        created_by, created_at, updated_at, archived_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        previous["package_id"], previous["artifact_type"],
                        previous["revision_no"], previous["title"], previous["content"],
                        previous["source_uri"], previous["created_by"],
                        previous["created_at"], previous["updated_at"], now,
                    ),
                )
            connection.execute(
                """INSERT INTO architecture_artifacts
                   (package_id, artifact_type, revision_no, title, content, source_uri,
                    created_by, created_at, updated_at)
                   VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(package_id, artifact_type) DO UPDATE SET
                     revision_no = architecture_artifacts.revision_no + 1,
                     title = excluded.title, content = excluded.content,
                     source_uri = excluded.source_uri, created_by = excluded.created_by,
                     updated_at = excluded.updated_at""",
                (package_id, artifact_type, title, content, source_uri, created_by, now, now),
            )
            self._architecture_event(
                connection, package_id, "artifact_added_or_updated", created_by,
                f"Architecture artifact '{artifact_type}' was saved.", now,
            )
        package = self.get_architecture_package(package_id)
        for artifact in package["artifacts"]:
            if artifact["artifact_type"] == artifact_type:
                return artifact
        raise ValueError("Saved architecture artifact could not be reloaded.")

    def add_architecture_decision(
        self, *, package_id: str, decision_id: str, title: str, context: str,
        decision: str, consequences: str, created_by: str,
    ) -> dict[str, object]:
        now = _now()
        with self._connection() as connection:
            self._editable_architecture_package(connection, package_id)
            connection.execute(
                """INSERT INTO architecture_decisions
                   (decision_id, package_id, title, context, decision, consequences,
                    status, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'accepted', ?, ?)""",
                (decision_id, package_id, title, context, decision, consequences, created_by, now),
            )
            self._architecture_event(
                connection, package_id, "decision_recorded", created_by,
                f"Architecture decision '{decision_id}' recorded.", now,
            )
        return self.get_architecture_package(package_id)

    def map_story_to_architecture(
        self, *, package_id: str, story_id: str, mapped_by: str,
    ) -> None:
        now = _now()
        with self._connection() as connection:
            package = self._editable_architecture_package(connection, package_id)
            story = connection.execute(
                "SELECT requirement_id FROM user_stories WHERE story_id = ?", (story_id,)
            ).fetchone()
            if story is None:
                raise ValueError(f"User story '{story_id}' does not exist.")
            if story["requirement_id"] != package["requirement_id"]:
                raise ValueError(
                    f"User story '{story_id}' does not belong to requirement "
                    f"'{package['requirement_id']}'."
                )
            connection.execute(
                """INSERT OR IGNORE INTO architecture_story_map
                   (package_id, story_id, mapped_by, mapped_at) VALUES (?, ?, ?, ?)""",
                (package_id, story_id, mapped_by, now),
            )
            self._architecture_event(
                connection, package_id, "story_mapped", mapped_by,
                f"User story '{story_id}' mapped to architecture package.", now,
            )

    def get_architecture_checklist(self, package_id: str) -> dict[str, object]:
        with self._connection() as connection:
            package = connection.execute(
                """SELECT p.*, f.state AS feature_state, r.status AS requirement_status
                   FROM architecture_packages p
                   JOIN features f ON f.feature_id = p.feature_id
                   JOIN business_requirements r ON r.requirement_id = p.requirement_id
                   WHERE p.package_id = ?""", (package_id,),
            ).fetchone()
            if package is None:
                raise ValueError(f"Architecture package '{package_id}' does not exist.")
            artifact_rows = connection.execute(
                "SELECT artifact_type FROM architecture_artifacts WHERE package_id = ?",
                (package_id,),
            ).fetchall()
            decision_count = int(connection.execute(
                "SELECT COUNT(*) FROM architecture_decisions WHERE package_id = ?",
                (package_id,),
            ).fetchone()[0])
            required_story_rows = connection.execute(
                "SELECT story_id FROM user_stories WHERE requirement_id = ? ORDER BY story_id",
                (package["requirement_id"],),
            ).fetchall()
            mapped_story_rows = connection.execute(
                "SELECT story_id FROM architecture_story_map WHERE package_id = ?",
                (package_id,),
            ).fetchall()
        artifact_types = {row["artifact_type"] for row in artifact_rows}
        required_stories = {row["story_id"] for row in required_story_rows}
        mapped_stories = {row["story_id"] for row in mapped_story_rows}
        return {
            "package_id": package_id,
            "status": package["status"],
            "feature_state": package["feature_state"],
            "requirement_status": package["requirement_status"],
            "required_artifacts": list(REQUIRED_ARCHITECTURE_ARTIFACTS),
            "present_artifacts": sorted(artifact_types),
            "missing_artifacts": [
                item for item in REQUIRED_ARCHITECTURE_ARTIFACTS if item not in artifact_types
            ],
            "decision_count": decision_count,
            "required_stories": sorted(required_stories),
            "mapped_stories": sorted(mapped_stories),
            "unmapped_stories": sorted(required_stories - mapped_stories),
            "complete": (
                package["requirement_status"] == RequirementStatus.APPROVED.value
                and package["feature_state"] == WorkflowState.ARCHITECTURE_REVIEW.value
                and not set(REQUIRED_ARCHITECTURE_ARTIFACTS) - artifact_types
                and decision_count > 0
                and not required_stories - mapped_stories
            ),
        }

    def submit_architecture_package(
        self, *, package_id: str, actor_id: str, note: str,
    ) -> dict[str, object]:
        now = _now()
        with self._connection() as connection:
            package = self._editable_architecture_package(connection, package_id)
            requirement_status = connection.execute(
                "SELECT status FROM business_requirements WHERE requirement_id = ?",
                (package["requirement_id"],),
            ).fetchone()["status"]
            feature_state = connection.execute(
                "SELECT state FROM features WHERE feature_id = ?", (package["feature_id"],)
            ).fetchone()["state"]
            present = {
                row["artifact_type"] for row in connection.execute(
                    "SELECT artifact_type FROM architecture_artifacts WHERE package_id = ?",
                    (package_id,),
                ).fetchall()
            }
            missing = [item for item in REQUIRED_ARCHITECTURE_ARTIFACTS if item not in present]
            decision_count = int(connection.execute(
                "SELECT COUNT(*) FROM architecture_decisions WHERE package_id = ?",
                (package_id,),
            ).fetchone()[0])
            stories = {
                row["story_id"] for row in connection.execute(
                    "SELECT story_id FROM user_stories WHERE requirement_id = ?",
                    (package["requirement_id"],),
                ).fetchall()
            }
            mapped = {
                row["story_id"] for row in connection.execute(
                    "SELECT story_id FROM architecture_story_map WHERE package_id = ?",
                    (package_id,),
                ).fetchall()
            }
            problems: list[str] = []
            if requirement_status != RequirementStatus.APPROVED.value:
                problems.append("the linked business requirement is not PO approved")
            if feature_state != WorkflowState.ARCHITECTURE_REVIEW.value:
                problems.append("the feature is not in architecture_review")
            if missing:
                problems.append("missing design sections: " + ", ".join(missing))
            if decision_count == 0:
                problems.append("at least one Architecture Decision Record (ADR) is required")
            if stories - mapped:
                problems.append("unmapped user stories: " + ", ".join(sorted(stories - mapped)))
            if problems:
                message = "; ".join(problems)
                raise ValueError(
                    "Architecture package is not ready for review: " + message
                )
            if package["status"] not in {"draft", "changes_requested"}:
                raise ValueError(
                    f"Architecture package cannot be submitted from status '{package['status']}'."
                )
            connection.execute(
                "UPDATE architecture_packages SET status = 'submitted', updated_at = ? "
                "WHERE package_id = ?", (now, package_id),
            )
            self._architecture_event(connection, package_id, "submitted", actor_id, note, now)
        return self.get_architecture_package(package_id)

    def review_architecture_package(
        self, *, package_id: str, outcome: str, reviewer_id: str, note: str,
        evidence_uri: str,
    ) -> dict[str, object]:
        now = _now()
        with self._connection() as connection:
            package = connection.execute(
                "SELECT * FROM architecture_packages WHERE package_id = ?", (package_id,)
            ).fetchone()
            if package is None:
                raise ValueError(f"Architecture package '{package_id}' does not exist.")
            if package["status"] != "submitted":
                raise ValueError("Only a submitted architecture package can be reviewed.")
            if package["created_by"] == reviewer_id:
                raise ValueError(
                    "The package author cannot approve their own architecture package; "
                    "an independent architecture reviewer is required."
                )
            connection.execute(
                """INSERT INTO architecture_reviews
                   (package_id, reviewer_id, outcome, note, evidence_uri, reviewed_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (package_id, reviewer_id, outcome, note, evidence_uri, now),
            )
            if outcome == "approved":
                connection.execute(
                    """UPDATE architecture_packages SET status = 'superseded', updated_at = ?
                       WHERE feature_id = ? AND status = 'approved' AND package_id <> ?""",
                    (now, package["feature_id"], package_id),
                )
                connection.execute(
                    """UPDATE architecture_packages SET status = 'approved', approved_by = ?,
                       approved_at = ?, updated_at = ?, review_note = ? WHERE package_id = ?""",
                    (reviewer_id, now, now, note, package_id),
                )
            else:
                connection.execute(
                    """UPDATE architecture_packages SET status = 'changes_requested',
                       updated_at = ?, review_note = ? WHERE package_id = ?""",
                    (now, note, package_id),
                )
            self._architecture_event(
                connection, package_id, f"review_{outcome}", reviewer_id,
                f"{note} Evidence: {evidence_uri}", now,
            )
        return self.get_architecture_package(package_id)

    def get_approved_architecture_for_feature(
        self, feature_id: str,
    ) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT p.*, r.status AS requirement_status
                   FROM architecture_packages p
                   JOIN business_requirements r ON r.requirement_id = p.requirement_id
                   WHERE p.feature_id = ? AND p.status = 'approved'
                   ORDER BY p.version_no DESC LIMIT 1""", (feature_id,),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["requirement_is_approved"] = (
                row["requirement_status"] == RequirementStatus.APPROVED.value
            )
            return result

    def get_architecture_package(self, package_id: str) -> dict[str, object]:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT p.*, f.title AS feature_title, f.state AS feature_state,
                          r.title AS requirement_title, r.status AS requirement_status
                   FROM architecture_packages p
                   JOIN features f ON f.feature_id = p.feature_id
                   JOIN business_requirements r ON r.requirement_id = p.requirement_id
                   WHERE p.package_id = ?""", (package_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Architecture package '{package_id}' does not exist.")
            package = dict(row)
            package["artifacts"] = [dict(item) for item in connection.execute(
                "SELECT * FROM architecture_artifacts WHERE package_id = ? ORDER BY artifact_type",
                (package_id,),
            ).fetchall()]
            package["artifact_history"] = [dict(item) for item in connection.execute(
                """SELECT * FROM architecture_artifact_history WHERE package_id = ?
                   ORDER BY artifact_type, revision_no""", (package_id,),
            ).fetchall()]
            package["decisions"] = [dict(item) for item in connection.execute(
                "SELECT * FROM architecture_decisions WHERE package_id = ? ORDER BY decision_id",
                (package_id,),
            ).fetchall()]
            package["story_mappings"] = [dict(item) for item in connection.execute(
                "SELECT * FROM architecture_story_map WHERE package_id = ? ORDER BY story_id",
                (package_id,),
            ).fetchall()]
            package["reviews"] = [dict(item) for item in connection.execute(
                "SELECT * FROM architecture_reviews WHERE package_id = ? ORDER BY review_id",
                (package_id,),
            ).fetchall()]
            package["events"] = [dict(item) for item in connection.execute(
                "SELECT * FROM architecture_events WHERE package_id = ? ORDER BY event_id",
                (package_id,),
            ).fetchall()]
        package["checklist"] = self.get_architecture_checklist(package_id)
        return package

    def _editable_architecture_package(
        self, connection: sqlite3.Connection, package_id: str,
    ) -> sqlite3.Row:
        package = connection.execute(
            "SELECT * FROM architecture_packages WHERE package_id = ?", (package_id,)
        ).fetchone()
        if package is None:
            raise ValueError(f"Architecture package '{package_id}' does not exist.")
        if package["status"] not in {"draft", "changes_requested"}:
            raise ValueError(
                f"Architecture package '{package_id}' is not editable from status "
                f"'{package['status']}'."
            )
        return package

    @staticmethod
    def _architecture_event(
        connection: sqlite3.Connection, package_id: str, event_type: str,
        actor_id: str, note: str, occurred_at: str,
    ) -> None:
        connection.execute(
            """INSERT INTO architecture_events
               (package_id, event_type, actor_id, note, occurred_at)
               VALUES (?, ?, ?, ?, ?)""",
            (package_id, event_type, actor_id, note, occurred_at),
        )

    def create_feature(self, request: FeatureRequest) -> FeatureRecord:
        request.validate_for_ba_review()
        now = _now()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO features
                   (feature_id, title, problem_statement, state, version, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 0, ?, ?)""",
                (
                    request.feature_id.strip(),
                    request.title.strip(),
                    request.problem_statement.strip(),
                    WorkflowState.INTAKE.value,
                    now,
                    now,
                ),
            )
            for index, description in enumerate(request.acceptance_criteria, start=1):
                connection.execute(
                    """INSERT INTO acceptance_criteria
                       (feature_id, criterion_id, sequence_no, description)
                       VALUES (?, ?, ?, ?)""",
                    (request.feature_id.strip(), f"AC-{index:03d}", index, description.strip()),
                )
        record = self.get_feature(request.feature_id)
        assert record is not None
        return record

    def get_feature(self, feature_id: str) -> FeatureRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM features WHERE feature_id = ?", (feature_id,)
            ).fetchone()
            if row is None:
                return None
            criteria = connection.execute(
                """SELECT description FROM acceptance_criteria
                   WHERE feature_id = ? ORDER BY sequence_no""",
                (feature_id,),
            ).fetchall()
        request = FeatureRequest(
            feature_id=row["feature_id"],
            title=row["title"],
            problem_statement=row["problem_statement"],
            acceptance_criteria=tuple(item["description"] for item in criteria),
        )
        return FeatureRecord(
            request=request,
            state=WorkflowState(row["state"]),
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
            version=int(row["version"]),
        )

    def list_features(self) -> list[FeatureRecord]:
        with self._connection() as connection:
            ids = connection.execute(
                "SELECT feature_id FROM features ORDER BY created_at, feature_id"
            ).fetchall()
        records = [self.get_feature(row["feature_id"]) for row in ids]
        return [record for record in records if record is not None]

    def get_workflow(self, feature_id: str) -> FeatureWorkflow | None:
        record = self.get_feature(feature_id)
        if record is None:
            return None
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT * FROM workflow_events WHERE feature_id = ? ORDER BY event_id""",
                (feature_id,),
            ).fetchall()
        history = [
            WorkflowEvent(
                event_id=int(row["event_id"]),
                feature_id=row["feature_id"],
                action=Action(row["action"]),
                actor_id=row["actor_id"],
                actor_role=Role(row["actor_role"]),
                from_state=WorkflowState(row["from_state"]),
                to_state=WorkflowState(row["to_state"]),
                note=row["note"],
                evidence_uri=row["evidence_uri"],
                occurred_at=_parse_datetime(row["occurred_at"]),
            )
            for row in rows
        ]
        return FeatureWorkflow(request=record.request, _state=record.state, _history=history)

    def save_transition(self, event: WorkflowEvent) -> None:
        """Atomically append an event and update state, rejecting stale writers."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state, version FROM features WHERE feature_id = ?",
                (event.feature_id,),
            ).fetchone()
            if row is None:
                raise WorkflowValidationError(f"Feature '{event.feature_id}' does not exist.")
            if row["state"] != event.from_state.value:
                raise WorkflowValidationError(
                    f"Feature '{event.feature_id}' changed in the database; "
                    "reload it before retrying."
                )
            last = connection.execute(
                """SELECT COALESCE(MAX(event_id), 0) AS last_id
                   FROM workflow_events WHERE feature_id = ?""",
                (event.feature_id,),
            ).fetchone()["last_id"]
            expected_event_id = int(last) + 1
            if event.event_id != expected_event_id:
                raise WorkflowValidationError(
                    "Workflow history is stale; reload the feature before saving this transition."
                )
            connection.execute(
                """INSERT INTO workflow_events
                   (feature_id, event_id, action, actor_id, actor_role, from_state, to_state,
                    note, evidence_uri, occurred_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.feature_id,
                    event.event_id,
                    event.action.value,
                    event.actor_id,
                    event.actor_role.value,
                    event.from_state.value,
                    event.to_state.value,
                    event.note,
                    event.evidence_uri,
                    event.occurred_at.isoformat(),
                ),
            )
            cursor = connection.execute(
                """UPDATE features SET state = ?, version = version + 1, updated_at = ?
                   WHERE feature_id = ? AND state = ? AND version = ?""",
                (
                    event.to_state.value,
                    _now(),
                    event.feature_id,
                    event.from_state.value,
                    row["version"],
                ),
            )
            if cursor.rowcount != 1:
                raise WorkflowValidationError(
                    f"Feature '{event.feature_id}' changed concurrently; reload before retrying."
                )

    def create_resource(
        self,
        resource_id: str,
        display_name: str,
        role: Role | str,
        *,
        capacity_points: float = 0,
        active: bool = True,
    ) -> ResourceRecord:
        try:
            normalized_role = Role(role)
        except ValueError as error:
            raise ValueError(f"Unknown resource role: {role!r}") from error
        if not resource_id.strip() or not display_name.strip():
            raise ValueError("resource_id and display_name are required")
        if capacity_points < 0:
            raise ValueError("capacity_points cannot be negative")
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO resources
                   (resource_id, display_name, role, capacity_points, active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    resource_id.strip(), display_name.strip(), normalized_role.value,
                    float(capacity_points), int(active), _now(),
                ),
            )
        return ResourceRecord(
            resource_id=resource_id.strip(),
            display_name=display_name.strip(),
            role=normalized_role,
            capacity_points=float(capacity_points),
            active=active,
        )

    def list_resources(self, active_only: bool = False) -> list[ResourceRecord]:
        query = "SELECT * FROM resources"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY resource_id"
        with self._connection() as connection:
            rows = connection.execute(query).fetchall()
        return [
            ResourceRecord(
                resource_id=row["resource_id"],
                display_name=row["display_name"],
                role=Role(row["role"]),
                capacity_points=float(row["capacity_points"]),
                active=bool(row["active"]),
            )
            for row in rows
        ]

    def create_work_item(
        self,
        *,
        work_item_id: str,
        feature_id: str,
        title: str,
        description: str = "",
        item_type: str = "task",
        status: str = "todo",
        priority: str = "medium",
        estimate_points: float | None = None,
    ) -> WorkItemRecord:
        now = _now()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO work_items
                   (work_item_id, feature_id, title, description, item_type, status, priority,
                    estimate_points, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    work_item_id.strip(), feature_id.strip(), title.strip(), description.strip(),
                    item_type, status, priority, estimate_points, now, now,
                ),
            )
            connection.execute(
                """INSERT INTO work_item_activity
                   (work_item_id, event_type, actor_id, note, occurred_at)
                   VALUES (?, 'created', 'system', ?, ?)""",
                (work_item_id, "Work item created.", now),
            )
        items = self.list_work_items(feature_id=feature_id)
        return next(item for item in items if item.work_item_id == work_item_id)

    def assign_work_item(
        self,
        *,
        work_item_id: str,
        resource_id: str,
        assigned_by: str,
        allocation_percent: float = 100,
    ) -> None:
        if not assigned_by.strip():
            raise ValueError("assigned_by is required for assignment audit")
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO work_item_assignments
                   (work_item_id, resource_id, assigned_by, allocation_percent, assigned_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (work_item_id, resource_id, assigned_by, allocation_percent, _now()),
            )
            connection.execute(
                """INSERT INTO work_item_activity
                   (work_item_id, event_type, actor_id, resource_id, note, occurred_at)
                   VALUES (?, 'assigned', ?, ?, ?, ?)""",
                (
                    work_item_id, assigned_by, resource_id,
                    f"Assigned to {resource_id} ({allocation_percent:g}% allocation).", _now(),
                ),
            )

    def update_work_item_status(
        self,
        *,
        work_item_id: str,
        status: str,
        actor_id: str,
        note: str,
        evidence_uri: str | None = None,
    ) -> None:
        allowed_statuses = {"todo", "in_progress", "blocked", "done"}
        if status not in allowed_statuses:
            raise ValueError(f"Invalid work item status: {status!r}")
        if not actor_id.strip() or not note.strip():
            raise ValueError("actor_id and an audit note are required")
        now = _now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT status FROM work_items WHERE work_item_id = ?", (work_item_id,)
            ).fetchone()
            if existing is None:
                raise ValueError(f"Work item '{work_item_id}' does not exist")
            actor = connection.execute(
                "SELECT resource_id FROM resources WHERE resource_id = ? AND active = 1",
                (actor_id,),
            ).fetchone()
            if actor is None:
                raise ValueError(f"Active resource '{actor_id}' is not registered")
            old_status = str(existing["status"])
            if old_status == status:
                raise ValueError(f"Work item '{work_item_id}' is already '{status}'")
            connection.execute(
                "UPDATE work_items SET status = ?, updated_at = ? WHERE work_item_id = ?",
                (status, now, work_item_id),
            )
            connection.execute(
                """INSERT INTO work_item_activity
                   (work_item_id, event_type, actor_id, from_status, to_status, note,
                    evidence_uri, occurred_at)
                   VALUES (?, 'status_changed', ?, ?, ?, ?, ?, ?)""",
                (work_item_id, actor_id, old_status, status, note.strip(), evidence_uri, now),
            )

    def get_work_item_activity(self, work_item_id: str) -> list[dict[str, str | None]]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT event_type, actor_id, resource_id, from_status, to_status, note,
                          evidence_uri, occurred_at
                   FROM work_item_activity WHERE work_item_id = ? ORDER BY activity_id""",
                (work_item_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def resource_workload_summary(self) -> list[dict[str, int | float | str]]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT r.resource_id, r.display_name, r.role, r.capacity_points,
                          COUNT(DISTINCT wi.work_item_id) AS assigned_items,
                          COUNT(DISTINCT CASE WHEN wi.status = 'done' THEN wi.work_item_id END)
                              AS completed_items,
                          COUNT(DISTINCT CASE WHEN wi.status != 'done' THEN wi.work_item_id END)
                              AS open_items
                   FROM resources r
                   LEFT JOIN work_item_assignments wa ON wa.resource_id = r.resource_id
                   LEFT JOIN work_items wi ON wi.work_item_id = wa.work_item_id
                   WHERE r.active = 1
                   GROUP BY r.resource_id
                   ORDER BY r.resource_id"""
            ).fetchall()
        return [
            {
                "resource_id": row["resource_id"],
                "display_name": row["display_name"],
                "role": row["role"],
                "capacity_points": float(row["capacity_points"]),
                "assigned_items": int(row["assigned_items"]),
                "completed_items": int(row["completed_items"]),
                "open_items": int(row["open_items"]),
            }
            for row in rows
        ]

    def list_work_items(self, feature_id: str | None = None) -> list[WorkItemRecord]:
        sql = """SELECT wi.*,
                         GROUP_CONCAT(wia.resource_id, char(31)) AS assignee_ids
                  FROM work_items wi
                  LEFT JOIN work_item_assignments wia ON wia.work_item_id = wi.work_item_id"""
        params: Sequence[object] = ()
        if feature_id:
            sql += " WHERE wi.feature_id = ?"
            params = (feature_id,)
        sql += " GROUP BY wi.work_item_id ORDER BY wi.created_at, wi.work_item_id"
        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [
            WorkItemRecord(
                work_item_id=row["work_item_id"],
                feature_id=row["feature_id"],
                title=row["title"],
                description=row["description"],
                item_type=row["item_type"],
                status=row["status"],
                priority=row["priority"],
                estimate_points=row["estimate_points"],
                assignees=tuple(row["assignee_ids"].split(chr(31)))
                if row["assignee_ids"]
                else (),
                created_at=_parse_datetime(row["created_at"]),
                updated_at=_parse_datetime(row["updated_at"]),
            )
            for row in rows
        ]

    def scrum_summary(self) -> dict[str, int | float]:
        with self._connection() as connection:
            feature_count = connection.execute("SELECT COUNT(*) FROM features").fetchone()[0]
            work_counts = connection.execute(
                "SELECT status, COUNT(*) AS total FROM work_items GROUP BY status"
            ).fetchall()
            resource_count = connection.execute(
                "SELECT COUNT(*) FROM resources WHERE active = 1"
            ).fetchone()[0]
            open_defects = connection.execute(
                "SELECT COUNT(*) FROM work_items WHERE item_type = 'defect' AND status != 'done'"
            ).fetchone()[0]
        summary: dict[str, int | float] = {
            "features": int(feature_count),
            "active_resources": int(resource_count),
            "open_defects": int(open_defects),
            "todo": 0,
            "in_progress": 0,
            "blocked": 0,
            "done": 0,
        }
        summary.update({str(row["status"]): int(row["total"]) for row in work_counts})
        return summary


    # M5 identity, credentials, audit, repository and PR persistence.
    def bootstrap_admin_identity(
        self,
        *,
        identity_id: str,
        display_name: str,
        token_salt: bytes,
        token_hash: bytes,
        hash_iterations: int,
        expires_at: str | None,
        credential_id: str,
    ) -> None:
        """Atomically claim first-admin bootstrap and persist its hashed credential."""
        now = _now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            count = int(connection.execute(
                "SELECT COUNT(*) FROM agent_identities"
            ).fetchone()[0])
            if count or connection.execute(
                "SELECT 1 FROM control_plane_bootstrap WHERE singleton_id = 1"
            ).fetchone():
                raise ValueError(
                    "Bootstrap is allowed only when no control-plane identity exists."
                )
            connection.execute(
                """INSERT INTO resources
                   (resource_id, display_name, role, capacity_points, active, created_at)
                   VALUES (?, ?, 'identity_admin', 0, 1, ?)""",
                (identity_id, display_name, now),
            )
            connection.execute(
                """INSERT INTO agent_identities
                   (identity_id, display_name, role, identity_type, status, created_at, updated_at)
                   VALUES (?, ?, 'identity_admin', 'human', 'active', ?, ?)""",
                (identity_id, display_name, now, now),
            )
            connection.execute(
                """INSERT INTO control_plane_bootstrap
                   (singleton_id, admin_identity_id, completed_at) VALUES (1, ?, ?)""",
                (identity_id, now),
            )
            connection.execute(
                """INSERT INTO agent_credentials
                   (credential_id, identity_id, token_prefix, token_salt, token_hash,
                    hash_iterations, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (credential_id, identity_id, credential_id, token_salt, token_hash,
                 hash_iterations, now, expires_at),
            )
            connection.execute(
                """INSERT INTO identity_events
                   (identity_id, event_type, actor_id, note, occurred_at)
                   VALUES (?, 'control_plane_bootstrapped', ?, ?, ?)""",
                (identity_id, identity_id, "First identity administrator bootstrapped.", now),
            )

    def create_agent_identity(
        self,
        *,
        identity_id: str,
        display_name: str,
        role: str,
        identity_type: str = "agent",
        capacity_points: float = 0,
    ) -> dict[str, object]:
        if identity_type not in {"agent", "human", "service"}:
            raise ValueError("identity_type must be agent, human, or service")
        if not identity_id.strip() or not display_name.strip():
            raise ValueError("identity_id and display_name are required")
        if capacity_points < 0:
            raise ValueError("capacity_points cannot be negative")
        try:
            normalized_role = Role(role)
        except ValueError as error:
            raise ValueError(f"Unknown identity role: {role!r}") from error
        now = _now()
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT role, display_name FROM resources WHERE resource_id = ?",
                (identity_id.strip(),),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """INSERT INTO resources
                       (resource_id, display_name, role, capacity_points, active, created_at)
                       VALUES (?, ?, ?, ?, 1, ?)""",
                    (identity_id.strip(), display_name.strip(), normalized_role.value,
                     float(capacity_points), now),
                )
            elif existing["role"] != normalized_role.value:
                raise ValueError("Existing resource role does not match requested identity role")
            else:
                connection.execute(
                    "UPDATE resources SET display_name = ?, capacity_points = ?, active = 1 "
                    "WHERE resource_id = ?",
                    (display_name.strip(), float(capacity_points), identity_id.strip()),
                )
            connection.execute(
                """INSERT INTO agent_identities
                   (identity_id, display_name, role, identity_type, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'active', ?, ?)""",
                (identity_id.strip(), display_name.strip(), normalized_role.value,
                 identity_type, now, now),
            )
            connection.execute(
                """INSERT INTO identity_events
                   (identity_id, event_type, actor_id, note, occurred_at)
                   VALUES (?, 'identity_created', ?, ?, ?)""",
                (identity_id.strip(), identity_id.strip(), "Identity registered.", now),
            )
        return self.get_agent_identity(identity_id.strip()) or {}

    def get_agent_identity(self, identity_id: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT i.*, r.capacity_points FROM agent_identities i
                   JOIN resources r ON r.resource_id = i.identity_id WHERE i.identity_id = ?""",
                (identity_id,),
            ).fetchone()
            if row is None:
                return None
            credentials = connection.execute(
                """SELECT credential_id, created_at, expires_at, last_used_at, revoked_at
                   FROM agent_credentials WHERE identity_id = ? ORDER BY created_at""",
                (identity_id,),
            ).fetchall()
        result = dict(row)
        result["credentials"] = [dict(item) for item in credentials]
        return result

    def list_agent_identities(self) -> list[dict[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_identities ORDER BY identity_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def create_agent_credential(
        self,
        *,
        credential_id: str,
        identity_id: str,
        token_salt: bytes,
        token_hash: bytes,
        hash_iterations: int,
        expires_at: str | None,
    ) -> None:
        with self._connection() as connection:
            active = connection.execute(
                "SELECT status FROM agent_identities WHERE identity_id = ?", (identity_id,)
            ).fetchone()
            if active is None or active["status"] != "active":
                raise ValueError(f"Identity '{identity_id}' does not exist or is disabled")
            connection.execute(
                """INSERT INTO agent_credentials
                   (credential_id, identity_id, token_prefix, token_salt, token_hash,
                    hash_iterations, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (credential_id, identity_id, credential_id, token_salt, token_hash,
                 hash_iterations, _now(), expires_at),
            )
            connection.execute(
                """INSERT INTO identity_events
                   (identity_id, event_type, actor_id, note, occurred_at)
                   VALUES (?, 'credential_issued', ?, ?, ?)""",
                (identity_id, identity_id, f"Credential {credential_id} issued.", _now()),
            )

    def get_agent_credential(self, credential_id: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT c.*, i.display_name, i.role, i.identity_type, i.status AS identity_status
                   FROM agent_credentials c JOIN agent_identities i
                   ON i.identity_id = c.identity_id WHERE c.credential_id = ?""",
                (credential_id,),
            ).fetchone()
        return dict(row) if row else None

    def touch_agent_credential(self, credential_id: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE agent_credentials SET last_used_at = ? WHERE credential_id = ?",
                (_now(), credential_id),
            )

    def revoke_agent_credential(
        self, credential_id: str, *, actor_id: str, note: str
    ) -> bool:
        now = _now()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT identity_id, revoked_at FROM agent_credentials WHERE credential_id = ?",
                (credential_id,),
            ).fetchone()
            if row is None:
                return False
            if row["revoked_at"] is None:
                connection.execute(
                    "UPDATE agent_credentials SET revoked_at = ? WHERE credential_id = ?",
                    (now, credential_id),
                )
                connection.execute(
                    """INSERT INTO identity_events
                       (identity_id, event_type, actor_id, note, occurred_at)
                       VALUES (?, 'credential_revoked', ?, ?, ?)""",
                    (row["identity_id"], actor_id, f"{credential_id}: {note}", now),
                )
        return True

    def set_agent_identity_status(
        self, identity_id: str, *, active: bool, actor_id: str, note: str
    ) -> None:
        now = _now()
        status = "active" if active else "disabled"
        with self._connection() as connection:
            row = connection.execute(
                "SELECT identity_id FROM agent_identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Identity '{identity_id}' does not exist")
            connection.execute(
                """UPDATE agent_identities SET status = ?, updated_at = ?, disabled_at = ?
                   WHERE identity_id = ?""",
                (status, now, None if active else now, identity_id),
            )
            connection.execute(
                "UPDATE resources SET active = ? WHERE resource_id = ?",
                (int(active), identity_id),
            )
            if not active:
                connection.execute(
                    """UPDATE agent_credentials SET revoked_at = COALESCE(revoked_at, ?)
                       WHERE identity_id = ?""",
                    (now, identity_id),
                )
            connection.execute(
                """INSERT INTO identity_events
                   (identity_id, event_type, actor_id, note, occurred_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (identity_id, "identity_enabled" if active else "identity_disabled",
                 actor_id, note, now),
            )

    def record_identity_event(
        self, identity_id: str, *, event_type: str, actor_id: str, note: str
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO identity_events
                   (identity_id, event_type, actor_id, note, occurred_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (identity_id, event_type, actor_id, note, _now()),
            )

    def register_github_repository(
        self, *, repository_id: str, owner: str, name: str, default_branch: str,
        provider: str, registered_by: str,
    ) -> dict[str, object]:
        if provider not in {"github_cli", "mock"}:
            raise ValueError("provider must be github_cli or mock")
        now = _now()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO github_repositories
                   (repository_id, owner, name, default_branch, provider, status, registered_by,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
                (repository_id, owner, name, default_branch, provider, registered_by, now, now),
            )
        return self.get_github_repository(repository_id) or {}

    def get_github_repository(self, repository_id: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM github_repositories WHERE repository_id = ?", (repository_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_github_repositories(self) -> list[dict[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM github_repositories ORDER BY owner, name"
            ).fetchall()
        return [dict(row) for row in rows]

    def create_github_workspace(
        self, *, workspace_id: str, repository_id: str, identity_id: str,
        branch_name: str, worktree_path: str,
    ) -> dict[str, object]:
        now = _now()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO github_workspaces
                   (workspace_id, repository_id, identity_id, branch_name, worktree_path,
                    status, created_at) VALUES (?, ?, ?, ?, ?, 'active', ?)""",
                (workspace_id, repository_id, identity_id, branch_name, worktree_path, now),
            )
            row = connection.execute(
                "SELECT * FROM github_workspaces WHERE workspace_id = ?", (workspace_id,)
            ).fetchone()
        return dict(row)

    def get_github_workspace(self, worktree_path: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM github_workspaces WHERE worktree_path = ? AND status = 'active'",
                (worktree_path,),
            ).fetchone()
        return dict(row) if row else None

    def close_github_workspace(self, workspace_id: str) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE github_workspaces SET status = 'closed', closed_at = ? "
                "WHERE workspace_id = ? AND status = 'active'",
                (_now(), workspace_id),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Active workspace '{workspace_id}' was not found")

    def create_github_pull_request(
        self, *, pr_record_id: str, repository_id: str, feature_id: str,
        head_branch: str, base_branch: str, pr_number: int | None, pr_url: str | None,
        created_by: str,
    ) -> dict[str, object]:
        now = _now()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO github_pull_requests
                   (pr_record_id, repository_id, feature_id, head_branch, base_branch,
                    pr_number, pr_url, status, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)""",
                (pr_record_id, repository_id, feature_id, head_branch, base_branch,
                 pr_number, pr_url, created_by, now, now),
            )
            row = connection.execute(
                "SELECT * FROM github_pull_requests WHERE pr_record_id = ?", (pr_record_id,)
            ).fetchone()
        return dict(row)

    def record_github_pr_review(
        self, *, pr_record_id: str, reviewer_id: str, outcome: str, note: str
    ) -> None:
        if outcome not in {"approved", "changes_requested"}:
            raise ValueError("outcome must be approved or changes_requested")
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO github_pr_reviews
                   (pr_record_id, reviewer_id, outcome, note, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (pr_record_id, reviewer_id, outcome, note, _now()),
            )

    def update_github_pull_request_status(self, pr_record_id: str, status: str) -> None:
        if status not in {"draft", "open", "approved", "changes_requested", "merged", "closed"}:
            raise ValueError(f"Unsupported pull request status: {status}")
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE github_pull_requests SET status = ?, updated_at = ? WHERE pr_record_id = ?",
                (status, _now(), pr_record_id),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Pull request record '{pr_record_id}' was not found")

    def record_github_ci_check(
        self, *, pr_record_id: str, check_name: str, conclusion: str,
        details_url: str | None = None,
    ) -> None:
        if conclusion not in {"success", "failure", "pending", "cancelled", "skipped", "neutral"}:
            raise ValueError(f"Unknown CI conclusion: {conclusion}")
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO github_ci_checks
                   (pr_record_id, check_name, conclusion, details_url, checked_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (pr_record_id, check_name, conclusion, details_url, _now()),
            )

    def list_github_prs(self, repository_id: str | None = None) -> list[dict[str, object]]:
        sql = "SELECT * FROM github_pull_requests"
        params: tuple[object, ...] = ()
        if repository_id:
            sql += " WHERE repository_id = ?"
            params = (repository_id,)
        sql += " ORDER BY created_at DESC"
        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


REQUIRED_ARCHITECTURE_ARTIFACTS = (
    "solution_overview",
    "component_design",
    "technical_design",
    "database_design",
    "api_contracts",
    "security_threat_model",
    "coding_standards",
    "test_driven_development_plan",
    "test_strategy",
    "deployment_rollback",
)

IDENTITY_GITHUB_MIGRATION_4 = r"""
-- M5: authenticated agent identities, credentials, GitHub records and workspaces.
CREATE TABLE IF NOT EXISTS agent_identities (
    identity_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    identity_type TEXT NOT NULL CHECK (identity_type IN ('agent', 'human', 'service')),
    status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    disabled_at TEXT,
    FOREIGN KEY (identity_id) REFERENCES resources(resource_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS control_plane_bootstrap (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    admin_identity_id TEXT NOT NULL UNIQUE,
    completed_at TEXT NOT NULL,
    FOREIGN KEY (admin_identity_id) REFERENCES agent_identities(identity_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS agent_credentials (
    credential_id TEXT PRIMARY KEY,
    identity_id TEXT NOT NULL,
    token_prefix TEXT NOT NULL UNIQUE,
    token_salt BLOB NOT NULL,
    token_hash BLOB NOT NULL,
    hash_iterations INTEGER NOT NULL CHECK (hash_iterations >= 100000),
    created_at TEXT NOT NULL,
    expires_at TEXT,
    last_used_at TEXT,
    revoked_at TEXT,
    FOREIGN KEY (identity_id) REFERENCES agent_identities(identity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_credentials_identity
    ON agent_credentials(identity_id, revoked_at, expires_at);

CREATE TABLE IF NOT EXISTS identity_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    note TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (identity_id) REFERENCES agent_identities(identity_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_identity_events_identity_time
    ON identity_events(identity_id, occurred_at);

CREATE TRIGGER IF NOT EXISTS trg_identity_events_no_update
BEFORE UPDATE ON identity_events BEGIN
    SELECT RAISE(ABORT, 'identity events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_identity_events_no_delete
BEFORE DELETE ON identity_events BEGIN
    SELECT RAISE(ABORT, 'identity events are append-only');
END;

CREATE TABLE IF NOT EXISTS github_repositories (
    repository_id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,
    default_branch TEXT NOT NULL,
    provider TEXT NOT NULL CHECK (provider IN ('github_cli', 'mock')),
    status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
    registered_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(owner, name)
);

CREATE TABLE IF NOT EXISTS github_workspaces (
    workspace_id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    identity_id TEXT NOT NULL,
    branch_name TEXT NOT NULL,
    worktree_path TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'closed')),
    created_at TEXT NOT NULL,
    closed_at TEXT,
    UNIQUE(repository_id, branch_name),
    UNIQUE(worktree_path),
    FOREIGN KEY (repository_id) REFERENCES github_repositories(repository_id) ON DELETE RESTRICT,
    FOREIGN KEY (identity_id) REFERENCES agent_identities(identity_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS github_pull_requests (
    pr_record_id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    feature_id TEXT NOT NULL,
    head_branch TEXT NOT NULL,
    base_branch TEXT NOT NULL,
    pr_number INTEGER,
    pr_url TEXT,
    status TEXT NOT NULL CHECK (status IN
        ('draft', 'open', 'approved', 'changes_requested', 'merged', 'closed')),
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (repository_id) REFERENCES github_repositories(repository_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_github_pr_repository_status
    ON github_pull_requests(repository_id, status);

CREATE TABLE IF NOT EXISTS github_pr_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_record_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('approved', 'changes_requested')),
    note TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (pr_record_id) REFERENCES github_pull_requests(pr_record_id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_id) REFERENCES agent_identities(identity_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS github_ci_checks (
    check_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_record_id TEXT NOT NULL,
    check_name TEXT NOT NULL,
    conclusion TEXT NOT NULL CHECK (conclusion IN
        ('success', 'failure', 'pending', 'cancelled', 'skipped', 'neutral')),
    details_url TEXT,
    checked_at TEXT NOT NULL,
    FOREIGN KEY (pr_record_id) REFERENCES github_pull_requests(pr_record_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_github_ci_checks_pr_time
    ON github_ci_checks(pr_record_id, checked_at);

"""


ARCHITECTURE_MIGRATION_3 = """
CREATE TABLE IF NOT EXISTS architecture_packages (
    package_id TEXT PRIMARY KEY,
    feature_id TEXT NOT NULL,
    requirement_id TEXT NOT NULL,
    version_no INTEGER NOT NULL CHECK (version_no > 0),
    status TEXT NOT NULL CHECK (status IN
        ('draft', 'submitted', 'changes_requested', 'approved', 'superseded')),
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT,
    review_note TEXT,
    UNIQUE(feature_id, version_no),
    FOREIGN KEY (feature_id) REFERENCES features(feature_id) ON DELETE CASCADE,
    FOREIGN KEY (requirement_id) REFERENCES business_requirements(requirement_id)
        ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS architecture_artifacts (
    artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL CHECK (artifact_type IN
        ('solution_overview', 'component_design', 'technical_design', 'database_design',
         'api_contracts', 'security_threat_model', 'coding_standards',
         'test_driven_development_plan', 'test_strategy', 'deployment_rollback')),
    revision_no INTEGER NOT NULL DEFAULT 1 CHECK (revision_no > 0),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_uri TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(package_id, artifact_type),
    FOREIGN KEY (package_id) REFERENCES architecture_packages(package_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS architecture_artifact_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    revision_no INTEGER NOT NULL CHECK (revision_no > 0),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_uri TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT NOT NULL,
    UNIQUE(package_id, artifact_type, revision_no),
    FOREIGN KEY (package_id) REFERENCES architecture_packages(package_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS architecture_decisions (
    decision_id TEXT PRIMARY KEY,
    package_id TEXT NOT NULL,
    title TEXT NOT NULL,
    context TEXT NOT NULL,
    decision TEXT NOT NULL,
    consequences TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('proposed', 'accepted', 'superseded', 'rejected')),
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (package_id) REFERENCES architecture_packages(package_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS architecture_story_map (
    package_id TEXT NOT NULL,
    story_id TEXT NOT NULL,
    mapped_by TEXT NOT NULL,
    mapped_at TEXT NOT NULL,
    PRIMARY KEY (package_id, story_id),
    FOREIGN KEY (package_id) REFERENCES architecture_packages(package_id) ON DELETE CASCADE,
    FOREIGN KEY (story_id) REFERENCES user_stories(story_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS architecture_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('approved', 'changes_requested')),
    note TEXT NOT NULL,
    evidence_uri TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    FOREIGN KEY (package_id) REFERENCES architecture_packages(package_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS architecture_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    note TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (package_id) REFERENCES architecture_packages(package_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_architecture_feature_status
    ON architecture_packages(feature_id, status, version_no);
CREATE INDEX IF NOT EXISTS idx_architecture_requirement
    ON architecture_packages(requirement_id);
CREATE INDEX IF NOT EXISTS idx_architecture_events_package_time
    ON architecture_events(package_id, occurred_at);
"""


REQUIREMENTS_MIGRATION_2 = """
CREATE TABLE IF NOT EXISTS business_requirements (
    requirement_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    business_value TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status TEXT NOT NULL CHECK (status IN
        ('draft', 'clarification_required', 'ba_review', 'po_review',
         'changes_requested', 'approved', 'rejected')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requirement_versions (
    requirement_id TEXT NOT NULL,
    version_no INTEGER NOT NULL CHECK (version_no > 0),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    business_value TEXT NOT NULL,
    priority TEXT NOT NULL,
    change_note TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    PRIMARY KEY (requirement_id, version_no),
    FOREIGN KEY (requirement_id) REFERENCES business_requirements(requirement_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS requirement_clarifications (
    clarification_id TEXT PRIMARY KEY,
    requirement_id TEXT NOT NULL,
    question TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'answered')),
    answer TEXT,
    asked_by TEXT NOT NULL,
    answered_by TEXT,
    asked_at TEXT NOT NULL,
    answered_at TEXT,
    FOREIGN KEY (requirement_id) REFERENCES business_requirements(requirement_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS user_stories (
    story_id TEXT PRIMARY KEY,
    requirement_id TEXT NOT NULL,
    title TEXT NOT NULL,
    user_role TEXT NOT NULL,
    goal TEXT NOT NULL,
    benefit TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'approved')),
    created_by TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (requirement_id) REFERENCES business_requirements(requirement_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS story_acceptance_criteria (
    criterion_id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL,
    sequence_no INTEGER NOT NULL CHECK (sequence_no > 0),
    description TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (story_id, sequence_no),
    FOREIGN KEY (story_id) REFERENCES user_stories(story_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS traceability_test_cases (
    test_case_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    test_level TEXT NOT NULL CHECK (test_level IN
        ('unit', 'api', 'ui', 'integration', 'security', 'accessibility', 'rag')),
    status TEXT NOT NULL CHECK (status IN ('draft', 'approved', 'automated', 'retired')),
    automation_reference TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS criterion_test_case_map (
    criterion_id TEXT NOT NULL,
    test_case_id TEXT NOT NULL,
    mapped_by TEXT NOT NULL,
    mapped_at TEXT NOT NULL,
    PRIMARY KEY (criterion_id, test_case_id),
    FOREIGN KEY (criterion_id) REFERENCES story_acceptance_criteria(criterion_id) ON DELETE CASCADE,
    FOREIGN KEY (test_case_id) REFERENCES traceability_test_cases(test_case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS requirement_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    requirement_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    note TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (requirement_id) REFERENCES business_requirements(requirement_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_requirements_status ON business_requirements(status);
CREATE INDEX IF NOT EXISTS idx_stories_requirement ON user_stories(requirement_id);
CREATE INDEX IF NOT EXISTS idx_criteria_story ON story_acceptance_criteria(story_id);
CREATE INDEX IF NOT EXISTS idx_requirement_events_time
    ON requirement_events(requirement_id, occurred_at);
"""


def _validate_priority(priority: str) -> None:
    if priority not in {"low", "medium", "high", "critical"}:
        raise ValueError(f"Unsupported priority '{priority}'.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
