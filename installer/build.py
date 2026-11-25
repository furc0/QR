"""Build QR_Setup.cmd using only Python's standard library."""
import base64
import hashlib
import io
from pathlib import Path
import sys
import textwrap
import zipfile

ROOT = Path(__file__).resolve().parents[1]
files = [
    "run_qr.ps1", "install_step_runtime.py", "requirements-runtime.txt",
    "THIRD_PARTY_NOTICES.md", "installer/inventory.py",
    "web/index.html", "web/app.js", "web/style.css",
    "web/vendor/occt/LICENSE.txt", "web/vendor/occt/occt-import-js.js",
    "web/vendor/three/LICENSE.txt", "web/vendor/three/three.min.js",
    "web/vendor/three/OBJLoader.js", "web/vendor/three/STLLoader.js",
]
files += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "server/qr_server").glob("*.py"))]
archive = io.BytesIO()
with zipfile.ZipFile(archive, "w") as z:
    for name in sorted(files):
        info = zipfile.ZipInfo(name)
        z.writestr(info, (ROOT / name).read_bytes().replace(b"\r\n", b"\n"), compress_type=zipfile.ZIP_DEFLATED)
payload = archive.getvalue()
header = """@echo off
setlocal DisableDelayedExpansion
set "QR_INSTALLER=%~f0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText($env:QR_INSTALLER); $body=($s -split '(?m)^:QR_SCRIPT\\r?$')[1]; & ([ScriptBlock]::Create(($body -split '(?m)^:QR_PAYLOAD\\r?$')[0]))"
set "rc=%errorlevel%"
if not "%rc%"=="0" pause
exit /b %rc%
:QR_SCRIPT
"""
ps = (ROOT / "installer/install.ps1").read_text().replace("__SHA256__", hashlib.sha256(payload).hexdigest())
encoded = "\n".join(textwrap.wrap(base64.b64encode(payload).decode("ascii"), 112))
output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("QR_Setup.cmd")
output.write_bytes((header + ps + "\n:QR_PAYLOAD\n" + encoded + "\n").replace("\n", "\r\n").encode("ascii"))
