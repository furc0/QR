"""Remove a superseded private release only if it contains exactly our files."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys

MARKER = ".qr-installed.json"


def snapshot(root):
    entries = {}
    for parent, dirs, files in os.walk(root, onerror=raise_error):
        for name in dirs + files:
            path = Path(parent, name)
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError(f"Linked path: {path}")
            key = path.relative_to(root).as_posix()
            if key == MARKER:
                continue
            if name in dirs:
                entries[key] = None
            else:
                with path.open("rb") as stream:
                    entries[key] = hashlib.file_digest(stream, "sha256").hexdigest()
    return entries


def raise_error(error):
    raise error


def managed(root):
    return (re.fullmatch(r"release-[0-9a-f]{32}", root.name)
            and not root.is_symlink()
            and not getattr(root.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


if __name__ == "__main__":
    action, folder = sys.argv[1:]
    root = Path(folder)
    if not managed(root):
        sys.exit("Unrecognized installation directory")
    marker = root / MARKER
    if action == "record":
        marker.write_text(json.dumps(snapshot(root)), encoding="utf-8")
    elif action == "clean":
        if marker.is_file() and snapshot(root) == json.loads(marker.read_text(encoding="utf-8")):
            shutil.rmtree(root)
        else:
            print(f"Keeping modified installation: {root}")
    else:
        sys.exit("Unknown action")
