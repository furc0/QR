import sqlite3
import sys
from pathlib import Path

migration = Path(sys.argv[1])
db = sqlite3.connect(":memory:")
db.execute("PRAGMA foreign_keys = ON")
db.executescript(migration.read_text(encoding="utf-8"))

assert db.execute("PRAGMA user_version").fetchone()[0] == 1
assert db.execute("PRAGMA foreign_key_check").fetchall() == []

# Tenant-scoped code uniqueness: duplicate across tenants is valid.
db.execute("INSERT INTO local_organizations(id,name) VALUES('org-a','A'),('org-b','B')")
db.execute("""INSERT INTO local_parts
(id,organization_id,part_code,title,kind,status,local_updated_at)
VALUES
('asm-a','org-a','ASM-1','Assembly A','assembly','draft','2026-01-01T00:00:00Z'),
('part-a','org-a','P-1','Part A','part','draft','2026-01-01T00:00:00Z'),
('part-b','org-b','P-1','Part B','part','draft','2026-01-01T00:00:00Z')""")

# Revision FK must point to the same part; deferred current revision is satisfied.
db.execute("""INSERT INTO local_part_revisions
(id,organization_id,part_id,revision_number,snapshot_json,created_by,created_at)
VALUES('rev-part-a','org-a','part-a',1,'{}','user','2026-01-01T00:00:00Z')""")
db.execute("UPDATE local_parts SET current_revision_id='rev-part-a' WHERE id='part-a'")

# Document version composite FK and part-document link must be valid.
db.execute("""INSERT INTO local_documents(id,organization_id,original_filename)
VALUES('doc-a','org-a','drawing.pdf')""")
db.execute("""INSERT INTO local_document_versions
(id,organization_id,document_id,version_number,storage_key,checksum_sha256,size_bytes,encryption_metadata_json,scan_status,created_at)
VALUES('docv-a','org-a','doc-a',1,'opaque/a','abc',10,'{}','clean','2026-01-01T00:00:00Z')""")
db.execute("""INSERT INTO local_part_documents(organization_id,part_id,document_version_id,document_role)
VALUES('org-a','part-a','docv-a','drawing')""")

# A BOM revision cannot belong to a different component.
try:
    db.execute("""INSERT INTO local_bom_items
    (id,organization_id,assembly_part_id,component_part_id,component_revision_id,quantity,unit_code,local_updated_at)
    VALUES('bom-bad','org-a','asm-a','asm-a','rev-part-a','1','pcs','2026-01-01T00:00:00Z')""")
except sqlite3.IntegrityError:
    pass
else:
    raise AssertionError("BOM accepted a revision belonging to another component")

assert db.execute("PRAGMA foreign_key_check").fetchall() == []
print("SQLite schema integration checks passed")
