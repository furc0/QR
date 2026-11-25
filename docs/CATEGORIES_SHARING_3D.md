# Categories, detail links and 3D models

## Categories

Categories are organization-scoped records. They can be created, renamed and deleted from the Categories section. A part may have zero or one category. Deleting a category clears `parts.category_id` for its parts and preserves the part records, revisions, BOM rows and documents.

API:
- `GET /api/categories`
- `POST /api/categories` with `{"name":"..." }`
- `PATCH /api/categories/{id}`
- `DELETE /api/categories/{id}`
- `PATCH /api/parts/{id}/category` with a category id or null

The feature module applies an additive SQLite migration at startup, so existing databases gain the categories table and nullable `parts.category_id` column without recreating the database.

## Detail page links

Each part has a stable UUID and a page at `/parts/{part_id}`. The API endpoint `GET /api/parts/{id}/share` returns the page path. The frontend turns it into an absolute URL using the configured API origin.

Opening the page requires a valid session and membership in the part's organization. The link does not bypass login or organization authorization. Unknown IDs and cross-organization API requests return not found.

## 3D model files

Supported uploads: STL, OBJ, STEP, STP. Maximum upload size: 250 MiB. Model files are stored separately from ordinary documents under `data/models/{organization_id}/{part_id}/`, with format, size and SHA-256 checksum metadata in `part_models`.

API:
- `GET /api/parts/{id}/models`
- `POST /api/parts/{id}/models` multipart field `file`
- `GET /api/models/{model_id}/download`

STL and OBJ are previewed in the detail page with locally bundled Three.js and loaders; no CDN access is required. The viewer supports orbit rotation, pan, zoom and fit-to-view. STEP/STP are retained as original CAD files and can be downloaded; native B-rep tessellation is not yet implemented. A future OpenCascade integration should tessellate STEP to GLB/glTF while preserving source STEP, units and metadata.

## Current limitations and next engineering tasks

1. Bundle Three.js locally instead of relying on CDN, for offline workstations.
2. Add OpenCascade conversion for STEP/STP to GLB/glTF, with explicit unit handling and conversion status.
3. Add viewer controls for pan, fit-to-view, axes, wireframe, section planes and model versions.
4. Add per-organization roles and granular permissions for category/model administration.
5. Add upload streaming, antivirus/content validation and storage quotas before production use.


## Engineering accuracy and file handling

- The uploaded source model is kept unchanged; the viewer is a visualization aid, not a geometry editor or a certified measurement tool.
- STL does not define physical units. OBJ files may also lack reliable unit metadata. Do not infer millimetres from the viewer scale; verify units and dimensions against the source CAD system and drawing.
- Uploads are streamed to a temporary file, capped at 250 MiB, hashed with SHA-256, and atomically moved into the model vault before the database record is committed. Failed writes remove the temporary/orphaned file.
- Model downloads are organization-authenticated and preserve the original filename. No public unauthenticated file URL is generated.
- STEP/STP upload is supported, but browser tessellation is not yet available. The source file remains downloadable; no approximate/fake mesh is displayed in its place.
