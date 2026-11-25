# QR Agent Instructions

- QR is an engineering parts catalogue with assemblies, BOM, drawings, files and revision history.
- Scope every business query and write to the authenticated user's organization membership.
- Part codes are unique inside an organization; users may belong to multiple organizations.
- QR locators are never authorization. Require authentication and object access checks.
- Never overwrite document versions; each upload creates a new version.
- Do not claim encryption, PostgreSQL, synchronization, licensing or production security exists unless implemented and tested.
- Keep credentials, database files, uploads and runtime data out of Git.
- Add numbered migrations; never edit an applied migration.
- The user's PC is the default local server. A remote host is an optional alternative endpoint.
- Report exact test results and disclose anything not tested.

## Current MVP limitations
The first runnable slice uses ordinary (unencrypted) SQLite and a local file vault. It is a prototype, not safe for confidential production drawings. Remote API endpoint selection is supported by the UI; PostgreSQL, TLS deployment, sync, encrypted storage and production hardening remain future work.
