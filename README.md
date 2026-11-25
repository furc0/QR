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
- Interactive browser preview for STL and OBJ with orbit, pan, zoom and fit-to-view. STL/OBJ unit metadata may be missing; the viewer is not a certified measuring tool. Three.js and its loaders are bundled locally, so preview works without internet access.
- STEP/STP files can be uploaded, downloaded and previewed through the pinned OpenCascade WebAssembly importer. The first Windows launch attempts to download the pinned 7.6 MB WASM runtime and verifies its Git blob SHA-1; QR still starts if the download is unavailable.
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
- STL/OBJ preview uses bundled Three.js and works offline. STEP/STP preview works after the pinned OpenCascade WASM runtime is installed; the original CAD file remains unchanged.
- STEP/STP preview uses OpenCascade WebAssembly in the browser. The first Windows launch attempts to download the pinned 7.6 MB runtime and verifies its Git blob SHA-1.
- PostgreSQL adapter, SQLCipher/DPAPI, encrypted file vault, sync, licensing, QR image generation, backups/restore and production deployment hardening remain future work.
