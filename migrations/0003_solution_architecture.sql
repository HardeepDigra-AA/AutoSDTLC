-- M4: persisted solution architecture, TDD artifacts, ADRs, reviews and audit events.
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
