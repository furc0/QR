from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "web" / "vendor" / "occt" / "occt-import-js.wasm"
SOURCE_URL = (
    "https://raw.githubusercontent.com/kovacsv/occt-import-js/"
    "41e470890ae0f9dc69ac50ffd5fc73e03576f4eb/dist/occt-import-js.wasm"
)
EXPECTED_SIZE = 7_604_031
EXPECTED_GIT_BLOB_SHA1 = "29458885e6b030850d352cff33ab0c22a7e36c35"
MAX_DOWNLOAD_SIZE = 16 * 1024 * 1024


def git_blob_sha1_bytes(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def git_blob_sha1_file(path: Path) -> str:
    size = path.stat().st_size
    digest = hashlib.sha1(f"blob {size}\0".encode("ascii"))
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_step_runtime(target: Path = TARGET) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size == EXPECTED_SIZE:
        if git_blob_sha1_file(target) == EXPECTED_GIT_BLOB_SHA1:
            print("STEP/STP viewer runtime is already installed.")
            return True

    temporary = target.with_name(target.name + ".download")
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "QR-Engineering-Catalogue/0.2"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            total = 0
            with temporary.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_SIZE:
                        raise ValueError("STEP runtime download exceeds the safety limit")
                    output.write(chunk)

        if total != EXPECTED_SIZE:
            raise ValueError(f"Unexpected STEP runtime size: {total} bytes")
        if git_blob_sha1_file(temporary) != EXPECTED_GIT_BLOB_SHA1:
            raise ValueError("STEP runtime checksum does not match the pinned upstream file")

        os.replace(temporary, target)
        print("STEP/STP viewer runtime installed and checksum verified.")
        return True
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        print(
            "STEP/STP preview is not installed. QR will still start; "
            "STL/OBJ preview remains available. "
            f"To retry, run install_step_runtime.py when internet is available. ({exc})"
        )
        return False


if __name__ == "__main__":
    ensure_step_runtime()
