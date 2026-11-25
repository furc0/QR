-- QR local encrypted SQLite schema
-- Migration: 0001_local_schema.sql
-- Open this database through SQLCipher (never plain SQLite in production).
-- UUIDs and UTC timestamps are supplied by the application.
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS local_schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE local_organizations (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  sync_state TEXT NOT NULL DEFAULT 'synced'
);
CREATE TABLE local_parts (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  part_code TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  kind TEXT NOT NULL CHECK(kind IN ('part','assembly')),
  status TEXT NOT NULL,
  attributes_json TEXT NOT NULL DEFAULT '{}',
  current_revision_id TEXT,
  server_updated_at TEXT,
  local_updated_at TEXT NOT NULL,
  deleted_at TEXT,
  UNIQUE(organization_id, part_code),
  UNIQUE(id, organization_id),
  FOREIGN KEY(current_revision_id, organization_id, id)
    REFERENCES local_part_revisions(id, organization_id, part_id)
    DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX local_parts_catalog_idx ON local_parts(organization_id, status, title);

CREATE TABLE local_part_revisions (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  part_id TEXT NOT NULL,
  revision_number INTEGER NOT NULL CHECK(revision_number > 0),
  snapshot_json TEXT NOT NULL,
  change_summary TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(part_id, revision_number),
  UNIQUE(id, organization_id, part_id),
  FOREIGN KEY(part_id, organization_id) REFERENCES local_parts(id, organization_id)
);

CREATE TABLE local_bom_items (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  assembly_part_id TEXT NOT NULL,
  component_part_id TEXT NOT NULL,
  component_revision_id TEXT,
  quantity TEXT NOT NULL,
  unit_code TEXT NOT NULL,
  position_no INTEGER NOT NULL DEFAULT 0,
  find_number TEXT,
  notes TEXT,
  server_updated_at TEXT,
  local_updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY(assembly_part_id, organization_id) REFERENCES local_parts(id, organization_id),
  FOREIGN KEY(component_part_id, organization_id) REFERENCES local_parts(id, organization_id),
  FOREIGN KEY(component_revision_id, organization_id, component_part_id)
    REFERENCES local_part_revisions(id, organization_id, part_id)
);
CREATE INDEX local_bom_order_idx ON local_bom_items(organization_id, assembly_part_id, position_no);

-- Keep offline BOM data structurally valid before synchronization.
CREATE TRIGGER local_bom_validate_insert
BEFORE INSERT ON local_bom_items
BEGIN
  SELECT CASE
    WHEN COALESCE((SELECT kind FROM local_parts
                   WHERE id = NEW.assembly_part_id
                     AND organization_id = NEW.organization_id
                     AND deleted_at IS NULL), '') <> 'assembly'
    THEN RAISE(ABORT, 'BOM parent must be a non-deleted assembly')
  END;
  SELECT CASE
    WHEN NEW.assembly_part_id = NEW.component_part_id
    THEN RAISE(ABORT, 'assembly cannot contain itself')
  END;
  SELECT CASE
    WHEN EXISTS (
      WITH RECURSIVE descendants(part_id) AS (
        SELECT component_part_id
        FROM local_bom_items
        WHERE organization_id = NEW.organization_id
          AND assembly_part_id = NEW.component_part_id
          AND deleted_at IS NULL
        UNION
        SELECT b.component_part_id
        FROM local_bom_items b
        JOIN descendants d ON b.assembly_part_id = d.part_id
        WHERE b.organization_id = NEW.organization_id
          AND b.deleted_at IS NULL
      )
      SELECT 1 FROM descendants WHERE part_id = NEW.assembly_part_id
    )
    THEN RAISE(ABORT, 'BOM change would create an assembly cycle')
  END;
END;

CREATE TRIGGER local_bom_validate_update
BEFORE UPDATE OF assembly_part_id, component_part_id, organization_id, deleted_at ON local_bom_items
BEGIN
  SELECT CASE
    WHEN COALESCE((SELECT kind FROM local_parts
                   WHERE id = NEW.assembly_part_id
                     AND organization_id = NEW.organization_id
                     AND deleted_at IS NULL), '') <> 'assembly'
    THEN RAISE(ABORT, 'BOM parent must be a non-deleted assembly')
  END;
  SELECT CASE
    WHEN NEW.assembly_part_id = NEW.component_part_id
    THEN RAISE(ABORT, 'assembly cannot contain itself')
  END;
  SELECT CASE
    WHEN EXISTS (
      WITH RECURSIVE descendants(part_id) AS (
        SELECT component_part_id
        FROM local_bom_items
        WHERE organization_id = NEW.organization_id
          AND assembly_part_id = NEW.component_part_id
          AND deleted_at IS NULL
          AND id <> OLD.id
        UNION
        SELECT b.component_part_id
        FROM local_bom_items b
        JOIN descendants d ON b.assembly_part_id = d.part_id
        WHERE b.organization_id = NEW.organization_id
          AND b.deleted_at IS NULL
          AND b.id <> OLD.id
      )
      SELECT 1 FROM descendants WHERE part_id = NEW.assembly_part_id
    )
    THEN RAISE(ABORT, 'BOM change would create an assembly cycle')
  END;
END;


CREATE TABLE local_documents (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  detected_mime_type TEXT,
  extension TEXT,
  deleted_at TEXT,
  UNIQUE(id, organization_id)
);
CREATE TABLE local_document_versions (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  version_number INTEGER NOT NULL,
  storage_key TEXT NOT NULL,
  checksum_sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
  encryption_metadata_json TEXT NOT NULL,
  scan_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(document_id, version_number),
  UNIQUE(id, organization_id),
  FOREIGN KEY(document_id, organization_id) REFERENCES local_documents(id, organization_id)
);

CREATE TABLE local_part_documents (
  organization_id TEXT NOT NULL,
  part_id TEXT NOT NULL,
  document_version_id TEXT NOT NULL,
  document_role TEXT NOT NULL,
  display_order INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(part_id, document_version_id, document_role),
  FOREIGN KEY(part_id, organization_id) REFERENCES local_parts(id, organization_id),
  FOREIGN KEY(document_version_id, organization_id) REFERENCES local_document_versions(id, organization_id)
);

CREATE TABLE local_outbox (
  operation_id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  base_revision INTEGER,
  operation_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT
);
CREATE INDEX local_outbox_queue_idx ON local_outbox(organization_id, status, created_at);

CREATE TABLE local_sync_cursors (
  organization_id TEXT PRIMARY KEY,
  cursor_value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE local_sync_conflicts (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  base_revision INTEGER,
  server_revision INTEGER,
  client_payload_json TEXT NOT NULL,
  server_payload_json TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL,
  resolved_at TEXT
);

CREATE TABLE local_settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

INSERT INTO local_schema_migrations(version,name,applied_at)
VALUES (1,'local_initial_schema',strftime('%Y-%m-%dT%H:%M:%fZ','now'));

PRAGMA user_version = 1;
COMMIT;
