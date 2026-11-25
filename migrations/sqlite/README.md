# Local SQLite migrations

The database MUST be opened through a SQLCipher-compatible driver with encryption configured before schema creation. Do not create a plaintext SQLite database and then assume it is protected.

Apply `0001_local_schema.sql` inside the encrypted SQLCipher connection. The migration uses `BEGIN IMMEDIATE`, records version 1 in `local_schema_migrations`, and sets `PRAGMA user_version=1`.

The local schema is a projection, not the server's authority. It stores the data required for the selected offline workspace, plus outbox/cursors/conflicts. Local file blobs live in an encrypted vault outside SQLite; metadata stores opaque storage keys and encryption metadata.

Before every schema upgrade:
1. Close database connections.
2. Create an encrypted backup using SQLCipher's supported backup mechanism.
3. Verify backup can be opened with the recovery procedure.
4. Apply the next numbered migration in a transaction.
5. Run integrity and application-level migration checks.
6. Keep the previous backup until the new version has been used successfully.

SQLite does not provide PostgreSQL RLS. Enforce tenant context in the repository layer and use composite foreign keys; enable `PRAGMA foreign_keys=ON` on every connection.
