"""backend/ を sys.path に追加し、Production側の計算ロジック(app.calculation.*)を
複製せずそのまま import できるようにするための共通ブートストラップ。

benchmarksパッケージ内の他モジュールは、production呼び出しの前に必ずこれを import する。
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
