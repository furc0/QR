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

## Install on Windows with one file

Download **QR_Setup.cmd** from this release or branch (use Download raw file on GitHub) and double-click it. The program files are embedded. Internet is required on the first installation for Python and its packages. Use the **QR Album** desktop shortcut afterwards. Close the old QR server before opening a newer installer.

The installer stores its private runtime under `%LOCALAPPDATA%\QR-Album`. Existing users can retain their original database and file paths. On first installation QR checks `QR_DATA_DIR`, the installer directory and the former `C:\QR_ALBUM` layout. If several databases are found it offers a numbered choice. For a custom location, place the installer next to the existing `qr.sqlite3` file. A new catalogue defaults to `%LOCALAPPDATA%\QR-Album\data`.

Updates remove an earlier installer-managed release only after the replacement has opened the catalogue and only if the previous file inventory still matches. Original source folders and system Python installations are preserved.

To rebuild the distributable after changing runtime code, run `python installer/build.py QR_Setup.cmd`.

## Run from a source checkout on Windows

1. Update the existing project folder, or download and extract the repository ZIP for a new installation.
2. Double-click **run_qr.bat**. On the first run, internet access is required. The launcher finds Python 3.11+ or installs Python 3.13 for the current user, prepares the virtual environment and installs dependencies.
3. The default browser opens at the selected local address. Create an administrator on a new installation or sign in to the existing catalogue.
4. Keep the terminal open while using QR. After updating, stop the old server window with Ctrl+C and launch the same BAT again.

Runtime database and uploaded files are stored in the untracked `data/` directory.

### Moving QR to another computer

Do not copy the `.venv/` directory from one computer to another. Python virtual environments contain machine-specific paths to the base Python installation and are not portable. If a copied `.venv` is detected, the Windows launchers test it and recreate only that directory when its interpreter cannot start. Dependencies are then installed on the destination computer.

The launcher does not remove or recreate `data/`; the SQLite database and uploaded files remain untouched.

## Local-only detail links

Part and assembly links are generated with the loopback address `http://127.0.0.1:<port>/parts/{part_id}`. They open only on the computer running QR, while its local server is running. They are not public links and cannot be opened from another computer or phone. No tunnel (ngrok or similar) is configured by the application.

## Server placement

**Local mode:** the user's PC runs the API and stores data locally. Most catalogue and file operations work without internet.

**Remote mode:** deploy the same API on another machine and enter its HTTPS URL under Подключение. That host owns the database and file vault. Configure `QR_CORS_ORIGINS` for the browser origin. Do not expose the development server directly to the public internet.

## Important limitations

- SQLite is currently not encrypted. Do not store confidential production drawings in this prototype.
- STL/OBJ preview works offline with the bundled Three.js runtime. STEP/STP preview uses the pinned OpenCascade WebAssembly runtime after it has been installed; the first Windows launch attempts a verified 7.6 MB download. If it cannot download, QR still starts and `py install_step_runtime.py` can be run later.
- Large STEP assemblies may take significant time and browser memory to tessellate. The source CAD file is preserved unchanged.
- STL/OBJ files may not contain reliable unit metadata. Confirm units and dimensions in the source CAD system; the viewer is not a certified measuring tool.
- PostgreSQL adapter, SQLCipher/DPAPI, encrypted file vault, sync, licensing, QR image generation, backups/restore and production deployment hardening remain future work.
