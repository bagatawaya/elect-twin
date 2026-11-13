-- OpenTwin V0.5 Migration 0001
-- Target: projects.sqlite3 (private vault). Stdlib-only; runs in one transaction.
-- vec_chunks (sqlite-vec vec0) is created separately by migrate.py after pack
-- verification, because vec0 is a virtual table requiring the extension.
-- Posture: airlocked private vault. Do NOT execute this against zoo.sqlite3.

BEGIN;

-- 0. Migration bookkeeping ---------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- 1. Scoped tool capability grants per room ---------------------------------
CREATE TABLE IF NOT EXISTS room_tool_grants (
    grant_id             TEXT PRIMARY KEY,
    room_id              TEXT NOT NULL,
    zone                 TEXT NOT NULL CHECK (zone IN ('PRIVATE_TWIN','SHARED_ROOM','PUBLIC_ZOO')),
    tool_name            TEXT NOT NULL,
    capability_tier      TEXT NOT NULL CHECK (capability_tier IN ('GREEN_READ','YELLOW_STAGE','AMBER_CONSEQUENTIAL','RED_BLOCKED')),
    allowed_paths_json   TEXT NOT NULL DEFAULT '[]'
                         CHECK (json_valid(allowed_paths_json)),
    allowed_domains_json TEXT NOT NULL DEFAULT '[]'
                         CHECK (json_valid(allowed_domains_json)),
    max_calls_per_turn   INTEGER NOT NULL DEFAULT 3
                         CHECK (max_calls_per_turn BETWEEN 0 AND 100),
    max_worst_case_usd   NUMERIC NOT NULL DEFAULT 0.05
                         CHECK (max_worst_case_usd >= 0),
    UNIQUE(room_id, tool_name)
);

-- 2. Action-bound single-use human approvals (Amber Gate) --------------------
CREATE TABLE IF NOT EXISTS authoritative_tool_approvals (
    approval_id          TEXT PRIMARY KEY,
    room_id              TEXT NOT NULL,
    turn_id              TEXT NOT NULL,
    tool_name            TEXT NOT NULL,
    capability_tier      TEXT NOT NULL,
    sanitized_payload_json TEXT NOT NULL
                           CHECK (json_valid(sanitized_payload_json)),
    payload_sha256       TEXT NOT NULL CHECK (length(payload_sha256) = 64),
    idempotency_key      TEXT NOT NULL UNIQUE,
    status               TEXT NOT NULL
                         CHECK (status IN ('PENDING_HUMAN','APPROVED','CONSUMED','REJECTED','PAUSED_UNCERTAIN')),
    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    consumed_at          TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_approvals_room_status ON authoritative_tool_approvals(room_id, status);

-- 3. Outbound airlock audit ---------------------------------------------------
CREATE TABLE IF NOT EXISTS outbound_audit (
    audit_id         TEXT PRIMARY KEY,
    room_id          TEXT NOT NULL,
    turn_id          TEXT NOT NULL,
    direction        TEXT NOT NULL CHECK (direction IN ('SHARED_ROOM','PUBLIC_ZOO','MCP_CLIENT')),
    raw_sha256       TEXT NOT NULL CHECK (length(raw_sha256) = 64),
    sanitized_sha256 TEXT NOT NULL CHECK (length(sanitized_sha256) = 64),
    diff_report_json TEXT NOT NULL CHECK (json_valid(diff_report_json)),
    -- diff_report_json: [{path, reason, kind}] for every stripped field.
    stripped_count   INTEGER NOT NULL CHECK (stripped_count >= 0),
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- 4. Crew blueprints (sanitized forks from OpenZoo) ---------------------------
CREATE TABLE IF NOT EXISTS crew_blueprints (
    crew_id           TEXT PRIMARY KEY,
    blueprint_sha256  TEXT NOT NULL CHECK (length(blueprint_sha256) = 64),
    source_room_id    TEXT,
    forked_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    -- schema-validated, free-text-stripped blueprint:
    -- only role_slug / role_category / turn_order / tool_archetype survive.
    roles_json        TEXT NOT NULL CHECK (json_valid(roles_json)),
    UNIQUE(blueprint_sha256, crew_id)
);

-- 5. Model slot bindings + rebind provenance ----------------------------------
CREATE TABLE IF NOT EXISTS model_bindings (
    binding_id     TEXT PRIMARY KEY,
    crew_id        TEXT NOT NULL REFERENCES crew_blueprints(crew_id),
    slot_name      TEXT NOT NULL,
    provider       TEXT,
    model_id       TEXT,
    status         TEXT NOT NULL CHECK (status IN ('BOUND','NEEDS_KEY','DISABLED')),
    rebinding_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(rebinding_json)),
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(crew_id, slot_name)
);

-- 6. Blind scrimmage ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS scrimmage_matches (
    match_id      TEXT PRIMARY KEY,
    task_category TEXT NOT NULL,
    room_id       TEXT NOT NULL,
    model_a_id    TEXT NOT NULL,          -- hidden from UI until vote closes
    model_b_id    TEXT NOT NULL,
    prompt_sha256 TEXT NOT NULL CHECK (length(prompt_sha256) = 64),
    status        TEXT NOT NULL CHECK (status IN ('OPEN','VOTED','EXPIRED')),
    winner_slot   TEXT CHECK (winner_slot IN ('A','B')),
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    voted_at      TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_scrimmage_category ON scrimmage_matches(task_category, status);

-- 7. Inference telemetry (router input) ---------------------------------------
CREATE TABLE IF NOT EXISTS telemetry_inferences (
    inference_id       TEXT PRIMARY KEY,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    task_category      TEXT NOT NULL,
    model_id           TEXT NOT NULL,
    provider           TEXT NOT NULL,
    input_tokens       INTEGER NOT NULL CHECK (input_tokens >= 0),
    cached_tokens      INTEGER NOT NULL DEFAULT 0 CHECK (cached_tokens >= 0),
    output_tokens      INTEGER NOT NULL CHECK (output_tokens >= 0),
    ttft_ms            INTEGER CHECK (ttft_ms >= 0),
    total_latency_ms   INTEGER CHECK (total_latency_ms >= 0),
    estimated_cost_usd NUMERIC NOT NULL DEFAULT 0 CHECK (estimated_cost_usd >= 0),
    scrimmage_match_id TEXT REFERENCES scrimmage_matches(match_id),
    blind_slot         TEXT CHECK (blind_slot IN ('A','B')),
    qc_pass_bool       INTEGER CHECK (qc_pass_bool IN (0,1)),
    human_lock_bool    INTEGER CHECK (human_lock_bool IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_telemetry_model_cat ON telemetry_inferences(model_id, task_category);

-- 8. Ingested documents + FTS5 ------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    document_id   TEXT PRIMARY KEY,
    source_path   TEXT NOT NULL,          -- original path; never leaves the vault
    source_sha256 TEXT NOT NULL CHECK (length(source_sha256) = 64),
    mime_type     TEXT NOT NULL,
    ingested_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json))
);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id      TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL REFERENCES documents(document_id),
    chunk_seq     INTEGER NOT NULL CHECK (chunk_seq >= 0),
    chunk_text    TEXT NOT NULL,
    byte_start    INTEGER,                -- byte span for claim verification
    byte_end      INTEGER,
    page_or_ts    TEXT,                   -- page number or "mm:ss" timestamp
    ingested_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(document_id, chunk_seq)
);

CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(
    chunk_text,
    content='document_chunks',
    content_rowid='rowid',
    tokenize='porter'
);

-- 9. Fact / Inference ledger --------------------------------------------------
CREATE TABLE IF NOT EXISTS claims_ledger (
    claim_id       TEXT PRIMARY KEY,
    room_id        TEXT NOT NULL,
    turn_id        TEXT,
    claim_text     TEXT NOT NULL,
    claim_type     TEXT NOT NULL
                   CHECK (claim_type IN ('EXTRACTED_FACT','MODEL_INFERENCE','UNVERIFIED_HYPOTHESIS')),
    source_sha256  TEXT,                  -- null for pure inferences
    chunk_id       TEXT REFERENCES document_chunks(chunk_id),
    byte_span      TEXT,                  -- "start:end" within chunk source
    freshness_flag TEXT CHECK (freshness_flag IN (NULL,'OK','STALE_SOURCE')),
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- 10. Prompt-cache entries (V0.5 seed; full compiler in V0.8) -----------------
CREATE TABLE IF NOT EXISTS context_cache_entries (
    cache_id        TEXT PRIMARY KEY,
    prefix_sha256   TEXT NOT NULL CHECK (length(prefix_sha256) = 64),
    provider        TEXT NOT NULL,
    provider_handle TEXT,                 -- e.g. Anthropic ephemeral / Gemini ctx id
    byte_length     INTEGER NOT NULL CHECK (byte_length > 0),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    last_hit_at     TEXT,
    UNIQUE(prefix_sha256, provider)
);

-- 11. Time-travel savepoints (room branching) ---------------------------------
CREATE TABLE IF NOT EXISTS time_travel_savepoints (
    savepoint_id TEXT PRIMARY KEY,
    room_id      TEXT NOT NULL,
    label        TEXT NOT NULL,
    -- SQLite SAVEPOINT name actually held on the connection while branching:
    sqlite_sp    TEXT NOT NULL,
    parent_id    TEXT REFERENCES time_travel_savepoints(savepoint_id),
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(room_id, label)
);

-- 12. Error & hallucination quarantine (Flag & Freeze) ------------------------
CREATE TABLE IF NOT EXISTS error_quarantine (
    quarantine_id TEXT PRIMARY KEY,
    room_id       TEXT NOT NULL,
    claim_text    TEXT NOT NULL,
    reason        TEXT NOT NULL,
    negative_constraint_json TEXT NOT NULL CHECK (json_valid(negative_constraint_json)),
    paused_widget_ids_json   TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(paused_widget_ids_json)),
    status        TEXT NOT NULL CHECK (status IN ('FROZEN','RESOLVED')),
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    resolved_at   TEXT NULL
);

-- 13. Worst-case budget reservations ------------------------------------------
CREATE TABLE IF NOT EXISTS budget_reservations (
    reservation_id TEXT PRIMARY KEY,
    room_id        TEXT NOT NULL,
    turn_id        TEXT NOT NULL,
    tool_name      TEXT NOT NULL,
    worst_case_usd NUMERIC NOT NULL CHECK (worst_case_usd >= 0),
    status         TEXT NOT NULL
                   CHECK (status IN ('HELD','RELEASED','CONSUMED','PAUSED_UNCERTAIN')),
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    closed_at      TEXT NULL
);

-- 14. Capability Pack manifest (sha256-pinned downloads) ----------------------
CREATE TABLE IF NOT EXISTS pack_manifest (
    pack_name     TEXT PRIMARY KEY,       -- e.g. 'sqlite-vec', 'kokoro-onnx'
    version       TEXT NOT NULL,
    platform      TEXT NOT NULL,          -- 'macos-arm64' | 'win-x64' | ...
    artifact_sha256 TEXT NOT NULL CHECK (length(artifact_sha256) = 64),
    installed_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    enabled       INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1))
);

INSERT INTO schema_migrations (version, name) VALUES (1, 'v05_security_grounding');

COMMIT;
