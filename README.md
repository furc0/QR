# QR — Engineering Catalogue

## Runnable local-server MVP

QR is an engineering parts and assemblies catalogue. The computer running QR is the default server and stores its SQLite database and files locally. A remote machine/VPS can host the same API; the web client can be configured to use that server.

Current application features:
- First-run administrator and organization setup; password login.
- Organization-scoped parts and assemblies, unique part codes, engineering fields and revision snapshots.
- User-managed categories; create, rename and delete. Deleting a category unassigns its parts but never deletes the parts.
- Permanent detail page URLs: `/parts/{part_id}`. The page requires a valid organization login; a URL is a locator, not an access token.
- Document upload/download API.
- 3D model upload for STL, OBJ, STEP and STP (up to 250 MB per model).
- Interactive browser preview for STL and OBJ: rotate and zoom.
- STEP/STP files are stored and downloadable, but browser preview requires a CAD conversion service (not included yet).
- Windows launchers automatically select a free port starting at 8765.

## Run on Windows

1. Install Python 3.11 or newer.
2. Clone/download this repository.
3. Double-click `run_qr.bat`, or run `./run_qr.ps1` in PowerShell.
4. Open the exact address printed in the terminal.
5. On first launch, create the administrator and organization.

Keep the terminal window open. Runtime database and uploaded files are stored in the untracked `data/` directory.

## Server placement

**Local mode:** the user's PC runs the API and stores data locally. Most catalogue and file operations work without internet.

**Remote mode:** deploy the same API on another machine and enter its HTTPS URL under Подключение. That host owns the database and file vault. Configure `QR_CORS_ORIGINS` for the browser origin. Do not expose the development server directly to the public internet.

## Important limitations

- SQLite is currently not encrypted. Do not store confidential production drawings in this prototype.
- STL/OBJ preview currently loads Three.js and its format loaders from a public CDN, so the 3D viewer needs internet access. The model files themselves are stored locally/on the configured server.
- STEP/STP upload and download are supported, but native STEP tessellation/preview is not implemented. A server-side OpenCascade conversion service is a planned next step.
- PostgreSQL adapter, SQLCipher/DPAPI, encrypted file vault, sync, licensing, QR image generation, backups/restore and production deployment hardening remain future work.
