# QR — Engineering Catalogue

## First runnable MVP

The first implementation slice includes first-run administrator and organization setup, password login, organization-scoped parts/assemblies, part codes unique per organization, basic engineering fields, assembly BOM rows with quantity and cycle checks, file upload/download (100 MB per file in this MVP), revision snapshots, and configurable remote API endpoint.

## Run on Windows

1. Install Python 3.11 or newer.
2. Clone/download this repository.
3. Double-click `run_qr.bat`, or run `./run_qr.ps1` in PowerShell.
4. Open http://127.0.0.1:8765.
5. On first launch, create the administrator and organization.

Keep the terminal window open. Runtime database and uploaded files are stored in the untracked `data/` directory.

## Server placement

**Local mode:** the user's PC runs the API and stores data locally. It works without internet.

**Remote mode:** deploy the same API on another machine and enter its HTTPS URL under Подключение. That host owns the database and file vault. Configure `QR_CORS_ORIGINS` for the browser origin. Do not expose the development server directly to the public internet.

The current MVP uses ordinary SQLite without database encryption. The production target remains SQLCipher + DPAPI for local storage and PostgreSQL/private object storage on a hardened VPS. PostgreSQL adapter, encryption, sync, licensing, QR generation, 3D viewer, backup/restore and production deployment hardening are not yet implemented. Do not store confidential production drawings in this prototype.
