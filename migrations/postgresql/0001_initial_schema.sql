-- QR PostgreSQL initial schema
-- Migration: 0001_initial_schema.sql
-- Target: PostgreSQL 16+
-- Apply with a dedicated migration role. Do not run as the runtime API role.
BEGIN;

CREATE TABLE users (
  id uuid PRIMARY KEY,
  email_normalized text NOT NULL UNIQUE,
  display_name text NOT NULL,
  password_hash text,
  auth_provider text,
  auth_subject text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','invited','suspended','deleted')),
  mfa_enabled boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  last_login_at timestamptz,
  CHECK ((auth_provider IS NULL) = (auth_subject IS NULL))
);
CREATE UNIQUE INDEX users_external_identity_uq ON users(auth_provider, auth_subject)
  WHERE auth_provider IS NOT NULL;

CREATE TABLE organizations (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  slug text NOT NULL UNIQUE,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','archived')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE memberships (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations(id),
  user_id uuid NOT NULL REFERENCES users(id),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('invited','active','suspended','left')),
  joined_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, user_id),
  UNIQUE (id, organization_id)
);
CREATE INDEX memberships_user_idx ON memberships(user_id, status);

CREATE TABLE permissions (
  key text PRIMARY KEY,
  description text NOT NULL
);
CREATE TABLE roles (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations(id),
  key text NOT NULL,
  name text NOT NULL,
  is_system boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, key),
  UNIQUE (id, organization_id)
);
CREATE TABLE role_permissions (
  role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  permission_key text NOT NULL REFERENCES permissions(key),
  PRIMARY KEY (role_id, permission_key)
);
CREATE TABLE membership_roles (
  organization_id uuid NOT NULL,
  membership_id uuid NOT NULL,
  role_id uuid NOT NULL,
  PRIMARY KEY (membership_id, role_id),
  FOREIGN KEY (membership_id, organization_id) REFERENCES memberships(id, organization_id) ON DELETE CASCADE,
  FOREIGN KEY (role_id, organization_id) REFERENCES roles(id, organization_id) ON DELETE CASCADE
);

CREATE TABLE parts (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations(id),
  part_code text NOT NULL CHECK (length(btrim(part_code)) > 0),
  title text NOT NULL,
  description text,
  kind text NOT NULL DEFAULT 'part' CHECK (kind IN ('part','assembly')),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','archived')),
  attributes_json jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(attributes_json) = 'object'),
  current_revision_id uuid,
  created_by uuid NOT NULL REFERENCES users(id),
  updated_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  UNIQUE (organization_id, part_code),
  UNIQUE (id, organization_id)
);
CREATE INDEX parts_org_status_updated_idx ON parts(organization_id, status, updated_at DESC);
CREATE INDEX parts_org_title_idx ON parts(organization_id, lower(title));

CREATE TABLE part_revisions (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL,
  part_id uuid NOT NULL,
  revision_number integer NOT NULL CHECK (revision_number > 0),
  snapshot_json jsonb NOT NULL CHECK (jsonb_typeof(snapshot_json) = 'object'),
  change_summary text,
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (part_id, revision_number),
  UNIQUE (id, organization_id),
  UNIQUE (id, organization_id, part_id),
  FOREIGN KEY (part_id, organization_id) REFERENCES parts(id, organization_id)
);
ALTER TABLE parts ADD CONSTRAINT parts_current_revision_fk
  FOREIGN KEY (current_revision_id, organization_id, id)
  REFERENCES part_revisions(id, organization_id, part_id)
  DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE categories (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations(id),
  parent_id uuid,
  name text NOT NULL,
  code text,
  sort_order integer NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
  UNIQUE (id, organization_id),
  FOREIGN KEY (parent_id, organization_id) REFERENCES categories(id, organization_id)
);
CREATE UNIQUE INDEX categories_org_code_uq ON categories(organization_id, code) WHERE code IS NOT NULL;
CREATE INDEX categories_parent_idx ON categories(organization_id, parent_id, sort_order);

CREATE TABLE part_categories (
  organization_id uuid NOT NULL,
  part_id uuid NOT NULL,
  category_id uuid NOT NULL,
  PRIMARY KEY (part_id, category_id),
  FOREIGN KEY (part_id, organization_id) REFERENCES parts(id, organization_id) ON DELETE CASCADE,
  FOREIGN KEY (category_id, organization_id) REFERENCES categories(id, organization_id) ON DELETE CASCADE
);

CREATE TABLE tags (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations(id),
  name text NOT NULL,
  normalized_name text NOT NULL,
  UNIQUE (organization_id, normalized_name),
  UNIQUE (id, organization_id)
);
CREATE TABLE part_tags (
  organization_id uuid NOT NULL,
  part_id uuid NOT NULL,
  tag_id uuid NOT NULL,
  PRIMARY KEY (part_id, tag_id),
  FOREIGN KEY (part_id, organization_id) REFERENCES parts(id, organization_id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id, organization_id) REFERENCES tags(id, organization_id) ON DELETE CASCADE
);

-- BOM rows belong to a tenant; only assembly-kind parts may be used as assembly_part_id.
CREATE TABLE bom_items (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL,
  assembly_part_id uuid NOT NULL,
  component_part_id uuid NOT NULL,
  component_revision_id uuid,
  quantity numeric(20,6) NOT NULL CHECK (quantity > 0),
  unit_code text NOT NULL,
  position_no integer NOT NULL DEFAULT 0,
  find_number text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  CHECK (assembly_part_id <> component_part_id),
  FOREIGN KEY (assembly_part_id, organization_id) REFERENCES parts(id, organization_id),
  FOREIGN KEY (component_part_id, organization_id) REFERENCES parts(id, organization_id),
  FOREIGN KEY (component_revision_id, organization_id, component_part_id) REFERENCES part_revisions(id, organization_id, part_id)
);
CREATE INDEX bom_assembly_order_idx ON bom_items(organization_id, assembly_part_id, position_no) WHERE deleted_at IS NULL;
CREATE INDEX bom_component_idx ON bom_items(organization_id, component_part_id) WHERE deleted_at IS NULL;

CREATE TABLE part_relations (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL,
  source_part_id uuid NOT NULL,
  target_part_id uuid NOT NULL,
  relation_type text NOT NULL CHECK (relation_type IN ('replacement','equivalent','related','derived_from','other')),
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (source_part_id <> target_part_id),
  UNIQUE (organization_id, source_part_id, target_part_id, relation_type),
  FOREIGN KEY (source_part_id, organization_id) REFERENCES parts(id, organization_id),
  FOREIGN KEY (target_part_id, organization_id) REFERENCES parts(id, organization_id)
);

CREATE TABLE documents (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations(id),
  original_filename text NOT NULL,
  detected_mime_type text,
  extension text,
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  UNIQUE (id, organization_id)
);
CREATE TABLE document_versions (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL,
  document_id uuid NOT NULL,
  version_number integer NOT NULL CHECK (version_number > 0),
  storage_key text NOT NULL UNIQUE,
  checksum_sha256 char(64) NOT NULL,
  size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
  encryption_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  scan_status text NOT NULL DEFAULT 'pending' CHECK (scan_status IN ('pending','clean','quarantined','failed')),
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, version_number),
  UNIQUE (id, organization_id),
  FOREIGN KEY (document_id, organization_id) REFERENCES documents(id, organization_id)
);
CREATE INDEX document_versions_checksum_idx ON document_versions(organization_id, checksum_sha256);

CREATE TABLE part_documents (
  organization_id uuid NOT NULL,
  part_id uuid NOT NULL,
  document_version_id uuid NOT NULL,
  document_role text NOT NULL CHECK (document_role IN ('drawing','model_3d','image','specification','passport','other')),
  display_order integer NOT NULL DEFAULT 0,
  PRIMARY KEY (part_id, document_version_id, document_role),
  FOREIGN KEY (part_id, organization_id) REFERENCES parts(id, organization_id) ON DELETE CASCADE,
  FOREIGN KEY (document_version_id, organization_id) REFERENCES document_versions(id, organization_id)
);

CREATE TABLE qr_routes (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL,
  part_id uuid NOT NULL,
  route_token_hash char(64) NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  UNIQUE (organization_id, route_token_hash),
  FOREIGN KEY (part_id, organization_id) REFERENCES parts(id, organization_id)
);
CREATE INDEX qr_routes_part_idx ON qr_routes(organization_id, part_id, status);

CREATE TABLE licenses (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations(id),
  status text NOT NULL CHECK (status IN ('trial','active','suspended','expired','revoked')),
  valid_from timestamptz NOT NULL,
  valid_until timestamptz,
  license_reference text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, organization_id)
);
CREATE TABLE license_entitlements (
  id uuid PRIMARY KEY,
  license_id uuid NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
  feature_key text NOT NULL,
  enabled boolean NOT NULL,
  limits_json jsonb,
  UNIQUE (license_id, feature_key)
);
CREATE TABLE owner_feature_policies (
  id uuid PRIMARY KEY,
  feature_key text NOT NULL UNIQUE,
  enabled boolean NOT NULL,
  policy_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  policy_version bigint NOT NULL DEFAULT 1 CHECK (policy_version > 0),
  updated_by_owner text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE device_installations (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations(id),
  user_id uuid REFERENCES users(id),
  public_key text,
  device_label text NOT NULL,
  platform text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked','retired')),
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz,
  revoked_at timestamptz,
  UNIQUE (id, organization_id)
);
CREATE TABLE license_leases (
  id uuid PRIMARY KEY,
  license_id uuid NOT NULL,
  organization_id uuid NOT NULL REFERENCES organizations(id),
  installation_id uuid,
  issued_at timestamptz NOT NULL,
  not_before timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  offline_until timestamptz NOT NULL,
  payload_version integer NOT NULL,
  signing_key_id text NOT NULL,
  signed_payload jsonb NOT NULL,
  signature text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked','expired')),
  revoked_at timestamptz,
  CHECK (not_before <= expires_at),
  CHECK (offline_until <= expires_at),
  FOREIGN KEY (license_id, organization_id) REFERENCES licenses(id, organization_id),
  FOREIGN KEY (installation_id, organization_id) REFERENCES device_installations(id, organization_id)
);
CREATE INDEX license_leases_license_idx ON license_leases(license_id, status, offline_until);

CREATE TABLE sync_operations (
  operation_id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations(id),
  installation_id uuid NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  base_revision integer,
  operation_type text NOT NULL,
  payload jsonb NOT NULL,
  status text NOT NULL DEFAULT 'received' CHECK (status IN ('received','processed','conflict','rejected','failed')),
  received_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz,
  result_json jsonb,
  FOREIGN KEY (installation_id, organization_id) REFERENCES device_installations(id, organization_id)
);
CREATE INDEX sync_operations_queue_idx ON sync_operations(organization_id, installation_id, status, received_at);

CREATE TABLE sync_cursors (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations(id),
  installation_id uuid NOT NULL,
  cursor_value text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, installation_id),
  FOREIGN KEY (installation_id, organization_id) REFERENCES device_installations(id, organization_id)
);
CREATE TABLE sync_conflicts (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations(id),
  installation_id uuid NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  base_revision integer,
  server_revision integer,
  client_payload jsonb NOT NULL,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved','discarded')),
  resolution jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz,
  FOREIGN KEY (installation_id, organization_id) REFERENCES device_installations(id, organization_id)
);
CREATE INDEX sync_conflicts_open_idx ON sync_conflicts(organization_id, installation_id, created_at) WHERE status = 'open';

CREATE TABLE audit_events (
  id uuid PRIMARY KEY,
  organization_id uuid REFERENCES organizations(id),
  actor_user_id uuid REFERENCES users(id),
  actor_type text NOT NULL CHECK (actor_type IN ('user','system','platform_owner')),
  action text NOT NULL,
  target_type text NOT NULL,
  target_id uuid,
  outcome text NOT NULL CHECK (outcome IN ('success','denied','failure')),
  correlation_id uuid,
  metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_events_org_time_idx ON audit_events(organization_id, created_at DESC);
CREATE INDEX audit_events_target_idx ON audit_events(target_type, target_id, created_at DESC);


-- Immutable engineering/document history and append-only audit trail.
CREATE FUNCTION reject_immutable_row_mutation() RETURNS trigger
LANGUAGE plpgsql AS $
BEGIN
  RAISE EXCEPTION '% rows are immutable; create a new version instead', TG_TABLE_NAME
    USING ERRCODE = '55000';
END;
$;
CREATE TRIGGER part_revisions_immutable
  BEFORE UPDATE OR DELETE ON part_revisions
  FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();
CREATE TRIGGER document_versions_immutable
  BEFORE UPDATE OR DELETE ON document_versions
  FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();
CREATE TRIGGER audit_events_immutable
  BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();

-- Enforce assembly type and prevent nested-assembly cycles at the database boundary.
CREATE FUNCTION validate_bom_item() RETURNS trigger
LANGUAGE plpgsql AS $
DECLARE
  parent_kind text;
  creates_cycle boolean;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.organization_id::text, 0));

  SELECT kind INTO parent_kind
  FROM parts
  WHERE id = NEW.assembly_part_id
    AND organization_id = NEW.organization_id
    AND deleted_at IS NULL;

  IF parent_kind IS DISTINCT FROM 'assembly' THEN
    RAISE EXCEPTION 'BOM parent % must be an active assembly', NEW.assembly_part_id
      USING ERRCODE = '23514';
  END IF;

  WITH RECURSIVE descendants(part_id) AS (
    SELECT b.component_part_id
    FROM bom_items b
    WHERE b.organization_id = NEW.organization_id
      AND b.assembly_part_id = NEW.component_part_id
      AND b.deleted_at IS NULL
      AND (TG_OP <> 'UPDATE' OR b.id <> NEW.id)
    UNION
    SELECT b.component_part_id
    FROM bom_items b
    JOIN descendants d ON b.assembly_part_id = d.part_id
    WHERE b.organization_id = NEW.organization_id
      AND b.deleted_at IS NULL
      AND (TG_OP <> 'UPDATE' OR b.id <> NEW.id)
  )
  SELECT EXISTS (
    SELECT 1 FROM descendants WHERE part_id = NEW.assembly_part_id
  ) INTO creates_cycle;

  IF creates_cycle THEN
    RAISE EXCEPTION 'BOM change would create an assembly cycle'
      USING ERRCODE = '23514';
  END IF;

  RETURN NEW;
END;
$;
CREATE TRIGGER bom_items_validate
  BEFORE INSERT OR UPDATE OF assembly_part_id, component_part_id, organization_id, deleted_at
  ON bom_items
  FOR EACH ROW EXECUTE FUNCTION validate_bom_item();

-- Tenant RLS. The API must SET LOCAL app.current_organization_id after validating membership.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'roles','membership_roles','parts','part_revisions','categories','part_categories',
    'tags','part_tags','bom_items','part_relations','documents','document_versions',
    'part_documents','qr_routes','licenses','device_installations','license_leases',
    'sync_operations','sync_cursors','sync_conflicts'
  ] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I USING (organization_id = nullif(current_setting(''app.current_organization_id'', true), '''')::uuid) WITH CHECK (organization_id = nullif(current_setting(''app.current_organization_id'', true), '''')::uuid)',
      t
    );
  END LOOP;
END $;

-- Membership discovery is restricted to the authenticated user set by the trusted API.
-- Tenant writes still require an active tenant context. The API must never accept this GUC
-- from an untrusted client; it is set from a verified authentication session.
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY membership_tenant_or_self ON memberships
  USING (
    organization_id = nullif(current_setting('app.current_organization_id', true), '')::uuid
    OR user_id = nullif(current_setting('app.current_user_id', true), '')::uuid
  )
  WITH CHECK (
    organization_id = nullif(current_setting('app.current_organization_id', true), '')::uuid
  );

-- Permission mappings are visible only for roles in the selected tenant.
ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY;
CREATE POLICY role_permissions_tenant ON role_permissions
  USING (EXISTS (
    SELECT 1 FROM roles r
    WHERE r.id = role_permissions.role_id
      AND r.organization_id = nullif(current_setting('app.current_organization_id', true), '')::uuid
  ));

-- Entitlements are visible only through a license in the selected tenant.
ALTER TABLE license_entitlements ENABLE ROW LEVEL SECURITY;
ALTER TABLE license_entitlements FORCE ROW LEVEL SECURITY;
CREATE POLICY license_entitlements_tenant ON license_entitlements
  USING (EXISTS (
    SELECT 1 FROM licenses l
    WHERE l.id = license_entitlements.license_id
      AND l.organization_id = nullif(current_setting('app.current_organization_id', true), '')::uuid
  ));

-- Tenant audit records are isolated. Platform-wide events (organization_id IS NULL)
-- remain available only to a separately authorized platform-owner service path.
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_events_tenant ON audit_events
  USING (
    organization_id = nullif(current_setting('app.current_organization_id', true), '')::uuid
    OR (
      organization_id IS NULL
      AND current_setting('app.is_platform_owner', true) = 'true'
    )
  )
  WITH CHECK (
    organization_id = nullif(current_setting('app.current_organization_id', true), '')::uuid
    OR (
      organization_id IS NULL
      AND current_setting('app.is_platform_owner', true) = 'true'
    )
  );

-- Seed permission vocabulary; role grants are provisioned per organization by application bootstrap.
INSERT INTO permissions(key, description) VALUES
 ('catalog.read','Read catalog'),('catalog.create','Create parts and assemblies'),
 ('catalog.update','Update parts and assemblies'),('catalog.archive','Archive catalog items'),
 ('documents.read','Read documents'),('documents.upload','Upload document versions'),
 ('documents.export','Export documents'),('viewer3d.view','View 3D models'),
 ('bom.read','Read assembly BOM'),('bom.update','Edit assembly BOM'),
 ('users.manage','Manage organization members'),('organization.settings','Manage organization settings');

COMMIT;
