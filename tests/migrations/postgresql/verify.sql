-- Integration checks for migrations/postgresql/0001_initial_schema.sql
\set ON_ERROR_STOP on

CREATE ROLE qr_runtime NOLOGIN;
GRANT USAGE ON SCHEMA public TO qr_runtime;
GRANT SELECT ON memberships, parts TO qr_runtime;

INSERT INTO users(id,email_normalized,display_name) VALUES
 ('00000000-0000-0000-0000-000000000001','user1@example.test','User One'),
 ('00000000-0000-0000-0000-000000000002','user2@example.test','User Two');
INSERT INTO organizations(id,name,slug) VALUES
 ('10000000-0000-0000-0000-000000000001','Org A','org-a'),
 ('10000000-0000-0000-0000-000000000002','Org B','org-b');
INSERT INTO memberships(id,organization_id,user_id,status) VALUES
 ('20000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000001','active'),
 ('20000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000001','active'),
 ('20000000-0000-0000-0000-000000000003','10000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000002','active');

INSERT INTO parts(id,organization_id,part_code,title,kind,status,created_by) VALUES
 ('30000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','ASM-1','Assembly 1','assembly','draft','00000000-0000-0000-0000-000000000001'),
 ('30000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000001','ASM-2','Assembly 2','assembly','draft','00000000-0000-0000-0000-000000000001'),
 ('30000000-0000-0000-0000-000000000003','10000000-0000-0000-0000-000000000001','P-1','Part 1','part','draft','00000000-0000-0000-0000-000000000001'),
 ('30000000-0000-0000-0000-000000000004','10000000-0000-0000-0000-000000000002','P-1','Other tenant Part 1','part','draft','00000000-0000-0000-0000-000000000002');

INSERT INTO part_revisions(id,organization_id,part_id,revision_number,snapshot_json,created_by) VALUES
 ('40000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000003',1,'{}','00000000-0000-0000-0000-000000000001');

-- Same code in different tenants is allowed; same code within one tenant is not.
DO $$
BEGIN
  BEGIN
    INSERT INTO parts(id,organization_id,part_code,title,created_by)
    VALUES ('30000000-0000-0000-0000-000000000005','10000000-0000-0000-0000-000000000001','P-1','Duplicate','00000000-0000-0000-0000-000000000001');
    RAISE EXCEPTION 'expected tenant-local part_code uniqueness violation';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
END $$;

-- Correct component revision accepted.
INSERT INTO bom_items(id,organization_id,assembly_part_id,component_part_id,component_revision_id,quantity,unit_code)
VALUES ('50000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001',
        '30000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000003',
        '40000000-0000-0000-0000-000000000001',1,'pcs');

-- Cross-tenant BOM link must fail.
DO $$
BEGIN
  BEGIN
    INSERT INTO bom_items(id,organization_id,assembly_part_id,component_part_id,quantity,unit_code)
    VALUES ('50000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000001',
            '30000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000004',1,'pcs');
    RAISE EXCEPTION 'expected cross-tenant foreign key violation';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
END $$;

-- A revision belonging to another component must fail.
DO $$
BEGIN
  BEGIN
    INSERT INTO bom_items(id,organization_id,assembly_part_id,component_part_id,component_revision_id,quantity,unit_code)
    VALUES ('50000000-0000-0000-0000-000000000003','10000000-0000-0000-0000-000000000001',
            '30000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000002',
            '40000000-0000-0000-0000-000000000001',1,'pcs');
    RAISE EXCEPTION 'expected component revision ownership violation';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
END $$;

-- A nested assembly cycle must fail.
DO $$
BEGIN
  BEGIN
    INSERT INTO bom_items(id,organization_id,assembly_part_id,component_part_id,quantity,unit_code)
    VALUES ('50000000-0000-0000-0000-000000000004','10000000-0000-0000-0000-000000000001',
            '30000000-0000-0000-0000-000000000002','30000000-0000-0000-0000-000000000001',1,'pcs');
    RAISE EXCEPTION 'expected assembly cycle violation';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
END $$;

-- Runtime role can discover only its own memberships before choosing a tenant.
SET ROLE qr_runtime;
SET app.current_user_id = '00000000-0000-0000-0000-000000000001';
DO $$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM memberships;
  IF n <> 2 THEN RAISE EXCEPTION 'membership self-discovery expected 2 rows, got %', n; END IF;
END $$;

-- Once a tenant is selected, catalog rows are isolated.
SET app.current_organization_id = '10000000-0000-0000-0000-000000000001';
DO $$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM parts;
  IF n <> 3 THEN RAISE EXCEPTION 'tenant RLS expected 3 parts, got %', n; END IF;
END $$;
RESET ROLE;

SELECT 'PostgreSQL migration integration checks passed' AS result;
