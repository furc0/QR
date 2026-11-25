# Third-party notices

QR bundles the following browser-side visualization libraries:

- **Three.js r128** — MIT License. Source: https://github.com/mrdoob/three.js/tree/r128. License: `web/vendor/three/LICENSE.txt`.
- **occt-import-js** — LGPL-2.1. Upstream commit: `41e470890ae0f9dc69ac50ffd5fc73e03576f4eb`. Source: https://github.com/kovacsv/occt-import-js. License: `web/vendor/occt/LICENSE.txt`.

The OpenCascade WebAssembly binary is not committed to this repository. `install_step_runtime.py` downloads it from the pinned upstream commit and verifies the exact Git blob SHA-1 and byte size before installation. This keeps the repository smaller while avoiding an unverified floating download.
