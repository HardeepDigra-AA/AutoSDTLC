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
