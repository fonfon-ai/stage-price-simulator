"""pytestがbenchmarksパッケージとbackend(app.calculation)の両方を解決できるようにする。"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"

for p in (_REPO_ROOT, _BACKEND_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
