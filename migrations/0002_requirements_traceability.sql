-- M3 additive schema migration. Existing M2 tables are left unchanged.
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
CREATE INDEX IF NOT EXISTS idx_requirement_events_time ON requirement_events(requirement_id, occurred_at);
