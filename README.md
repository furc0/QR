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

## Public access from the internet with ngrok (Windows)

The QR server listens on a local loopback address. To let another person open a part or assembly card, create an HTTPS tunnel to the exact port printed by QR:

1. Start QR with \`run_qr.bat\` and keep its console window open. Note the port in the line \`QR is starting at http://127.0.0.1:PORT\`.
2. Install ngrok and connect your ngrok account using the official ngrok instructions.
3. Open a **second** PowerShell window and run (replace \`PORT\` with the actual QR port):

   \`\`\`powershell
   ngrok http PORT
   \`\`\`

4. Copy the HTTPS forwarding address shown by ngrok, for example \`https://example.ngrok-free.app\`.
5. In QR, open **Подключение**, paste the address into **Публичный адрес для ссылок (ngrok)**, and click **Сохранить публичный адрес**.
6. Open a part or assembly card and copy its link. The generated link will use the public ngrok address, not \`127.0.0.1\` or \`localhost\`.

Keep both QR and ngrok console windows running while the link is in use. On the free ngrok plan the public hostname may change when the tunnel restarts; update the public address in QR and copy fresh links after that. Anyone opening a card still needs an account in the organization and must sign in.

**Security:** ngrok makes the QR login page reachable from the internet. The current MVP stores data in unencrypted SQLite and is not hardened for confidential production drawings. Use only test/non-sensitive data until encryption, HTTPS deployment hardening, backups and access controls are completed. Never share an ngrok authentication token.

## Server placement

**Local mode:** the user's PC runs the API and stores data locally. Most catalogue and file operations work without internet.

**Remote mode:** deploy the same API on another machine and enter its HTTPS URL under Подключение. That host owns the database and file vault. Configure `QR_CORS_ORIGINS` for the browser origin. Do not expose the development server directly to the public internet.

## Important limitations

- SQLite is currently not encrypted. Do not store confidential production drawings in this prototype.
- STL/OBJ preview works offline with the bundled Three.js runtime. STEP/STP preview uses the pinned OpenCascade WebAssembly runtime after it has been installed; the first Windows launch attempts a verified 7.6 MB download. If it cannot download, QR still starts and `py install_step_runtime.py` can be run later.
- Large STEP assemblies may take significant time and browser memory to tessellate. The source CAD file is preserved unchanged.
- STL/OBJ files may not contain reliable unit metadata. Confirm units and dimensions in the source CAD system; the viewer is not a certified measuring tool.
- PostgreSQL adapter, SQLCipher/DPAPI, encrypted file vault, sync, licensing, QR image generation, backups/restore and production deployment hardening remain future work.
