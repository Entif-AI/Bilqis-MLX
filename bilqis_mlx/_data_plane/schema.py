"""SQLite schema owned by the shared Bilqis data plane."""

C05_FIXED_SCHOOL_TRUST_SQL = """
CREATE TABLE IF NOT EXISTS bamf_c05_fixed_school_trust(
    run_identity_sha256 TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    foundation_parent_manifest_sha256 TEXT NOT NULL,
    receipt_sha256 TEXT NOT NULL UNIQUE,
    receipt_payload BLOB NOT NULL,
    cohort_sha256 TEXT NOT NULL,
    cohort_payload_sha256 TEXT NOT NULL,
    cohort_payload BLOB NOT NULL
) WITHOUT ROWID;
CREATE TRIGGER IF NOT EXISTS bamf_c05_fixed_school_trust_no_update
BEFORE UPDATE ON bamf_c05_fixed_school_trust
BEGIN
    SELECT RAISE(ABORT, 'BAMF_C05_FIXED_SCHOOL_TRUST_IMMUTABLE');
END;
CREATE TRIGGER IF NOT EXISTS bamf_c05_fixed_school_trust_no_delete
BEFORE DELETE ON bamf_c05_fixed_school_trust
BEGIN
    SELECT RAISE(ABORT, 'BAMF_C05_FIXED_SCHOOL_TRUST_IMMUTABLE');
END;
"""

PLANNER_FRONTIER_TRUST_SQL = """
CREATE TABLE IF NOT EXISTS bamf_planner_frontier_trust(
    trust_key_sha256 TEXT PRIMARY KEY,
    builder_sha256 TEXT NOT NULL,
    input_digest TEXT NOT NULL,
    factory_release_sha256 TEXT NOT NULL,
    output_digest TEXT NOT NULL,
    frontier_release_sha256 TEXT NOT NULL,
    receipt_sha256 TEXT NOT NULL UNIQUE,
    receipt_payload BLOB NOT NULL
) WITHOUT ROWID;
CREATE TRIGGER IF NOT EXISTS bamf_planner_frontier_trust_no_update
BEFORE UPDATE ON bamf_planner_frontier_trust
BEGIN
    SELECT RAISE(ABORT, 'BAMF_PLANNER_FRONTIER_TRUST_IMMUTABLE');
END;
CREATE TRIGGER IF NOT EXISTS bamf_planner_frontier_trust_no_delete
BEFORE DELETE ON bamf_planner_frontier_trust
BEGIN
    SELECT RAISE(ABORT, 'BAMF_PLANNER_FRONTIER_TRUST_IMMUTABLE');
END;
"""

ACCEPTED_AUTHORITY_SQL = """
CREATE TABLE IF NOT EXISTS bamf_accepted_authority_checkpoints(
    checkpoint_sha256 TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    generation INTEGER NOT NULL CHECK(generation >= 0),
    manifest_sha256 TEXT NOT NULL,
    parent_checkpoint_sha256 TEXT,
    payload BLOB NOT NULL,
    UNIQUE(run_id,manifest_sha256)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS bamf_accepted_authority_checkpoints_generation
ON bamf_accepted_authority_checkpoints(run_id,generation);
CREATE TRIGGER IF NOT EXISTS bamf_accepted_authority_checkpoints_no_update
BEFORE UPDATE ON bamf_accepted_authority_checkpoints
BEGIN
    SELECT RAISE(ABORT, 'BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_IMMUTABLE');
END;
CREATE TRIGGER IF NOT EXISTS bamf_accepted_authority_checkpoints_no_delete
BEFORE DELETE ON bamf_accepted_authority_checkpoints
BEGIN
    SELECT RAISE(ABORT, 'BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_IMMUTABLE');
END;
CREATE TABLE IF NOT EXISTS bamf_accepted_authority_tips(
    run_id TEXT PRIMARY KEY,
    generation INTEGER NOT NULL CHECK(generation >= 0),
    checkpoint_sha256 TEXT NOT NULL
) WITHOUT ROWID;
CREATE TRIGGER IF NOT EXISTS bamf_accepted_authority_tips_insert_guard
BEFORE INSERT ON bamf_accepted_authority_tips
WHEN NOT EXISTS(
    SELECT 1 FROM bamf_accepted_authority_checkpoints
    WHERE checkpoint_sha256=NEW.checkpoint_sha256
      AND run_id=NEW.run_id
      AND generation=NEW.generation
      AND parent_checkpoint_sha256 IS NULL
)
BEGIN
    SELECT RAISE(ABORT, 'BAMF_ACCEPTED_AUTHORITY_TIP_UNOWNED');
END;
CREATE TRIGGER IF NOT EXISTS bamf_accepted_authority_tips_no_delete
BEFORE DELETE ON bamf_accepted_authority_tips
BEGIN
    SELECT RAISE(ABORT, 'BAMF_ACCEPTED_AUTHORITY_TIP_PROTECTED');
END;
CREATE TRIGGER IF NOT EXISTS bamf_accepted_authority_tips_monotonic_update
BEFORE UPDATE ON bamf_accepted_authority_tips
WHEN NEW.run_id != OLD.run_id OR NEW.generation != OLD.generation + 1
BEGIN
    SELECT RAISE(ABORT, 'BAMF_ACCEPTED_AUTHORITY_TIP_NON_MONOTONIC');
END;
CREATE TRIGGER IF NOT EXISTS bamf_accepted_authority_tips_update_guard
BEFORE UPDATE ON bamf_accepted_authority_tips
WHEN NOT EXISTS(
    SELECT 1 FROM bamf_accepted_authority_checkpoints
    WHERE checkpoint_sha256=NEW.checkpoint_sha256
      AND run_id=OLD.run_id
      AND generation=NEW.generation
      AND parent_checkpoint_sha256=OLD.checkpoint_sha256
)
BEGIN
    SELECT RAISE(ABORT, 'BAMF_ACCEPTED_AUTHORITY_TIP_UNOWNED');
END;
"""

CORE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta(
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS objects(
    sha256 TEXT PRIMARY KEY,
    payload BLOB NOT NULL,
    raw_bytes INTEGER NOT NULL
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS archived_objects(
    sha256 TEXT PRIMARY KEY,
    pack_id TEXT NOT NULL,
    pack_offset INTEGER NOT NULL,
    raw_bytes INTEGER NOT NULL,
    compressed_bytes INTEGER NOT NULL
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS nodes(
    sha256 TEXT PRIMARY KEY,
    payload BLOB NOT NULL,
    generation INTEGER NOT NULL,
    parent_sha256 TEXT
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS archived_nodes(
    sha256 TEXT PRIMARY KEY,
    pack_id TEXT NOT NULL,
    pack_offset INTEGER NOT NULL,
    raw_bytes INTEGER NOT NULL,
    compressed_bytes INTEGER NOT NULL,
    generation INTEGER NOT NULL,
    parent_sha256 TEXT
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS retention_pins(
    kind TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    tier TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY(kind,sha256)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS verified_files(
    path TEXT NOT NULL,
    expected_sha256 TEXT NOT NULL,
    st_dev INTEGER NOT NULL,
    st_ino INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    ctime_ns INTEGER NOT NULL,
    verified_ns INTEGER NOT NULL,
    PRIMARY KEY(path, expected_sha256)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS verified_files_identity
ON verified_files(expected_sha256,st_dev,st_ino,size_bytes,mtime_ns,ctime_ns);
CREATE TABLE IF NOT EXISTS event_ledgers(
    run_dir TEXT PRIMARY KEY,
    st_dev INTEGER NOT NULL,
    st_ino INTEGER NOT NULL,
    indexed_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    ctime_ns INTEGER NOT NULL
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS event_index(
    run_dir TEXT NOT NULL,
    event_id TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    occurrences INTEGER NOT NULL,
    conflicted INTEGER NOT NULL,
    PRIMARY KEY(run_dir, event_id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS event_stream(
    run_dir TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    start_byte INTEGER NOT NULL,
    end_byte INTEGER NOT NULL,
    event_id TEXT,
    payload_sha256 TEXT,
    payload BLOB NOT NULL,
    PRIMARY KEY(run_dir, sequence)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS event_stream_byte_frontier
ON event_stream(run_dir,end_byte);
CREATE TABLE IF NOT EXISTS event_projections(
    run_dir TEXT NOT NULL,
    projection_key TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    st_dev INTEGER NOT NULL,
    st_ino INTEGER NOT NULL,
    indexed_bytes INTEGER NOT NULL,
    payload BLOB NOT NULL,
    PRIMARY KEY(run_dir,projection_key,schema_version)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS bamf_genesis_trust(
    run_id TEXT PRIMARY KEY,
    generation INTEGER NOT NULL CHECK(generation = 0),
    manifest_sha256 TEXT NOT NULL UNIQUE,
    payload_sha256 TEXT NOT NULL,
    payload BLOB NOT NULL
) WITHOUT ROWID;
CREATE TRIGGER IF NOT EXISTS bamf_genesis_trust_no_update
BEFORE UPDATE ON bamf_genesis_trust
BEGIN
    SELECT RAISE(ABORT, 'BAMF_GENESIS_TRUST_IMMUTABLE');
END;
CREATE TRIGGER IF NOT EXISTS bamf_genesis_trust_no_delete
BEFORE DELETE ON bamf_genesis_trust
BEGIN
    SELECT RAISE(ABORT, 'BAMF_GENESIS_TRUST_IMMUTABLE');
END;
"""
