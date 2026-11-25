import os
import tempfile
from pathlib import Path

os.environ["QR_DATA_DIR"] = str(Path(tempfile.mkdtemp(prefix="qr-runtime-tests-")))
