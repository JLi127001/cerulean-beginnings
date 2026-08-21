from __future__ import annotations

import json
from pathlib import Path

from core.models import BuildData


def load_build_data(path: str | Path) -> BuildData:
    """Parse a build JSON file into validated in-memory objects.

    Swappable: a future SQLite-backed loader just needs to return a
    BuildData with the same shape, and nothing downstream in core/ changes.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return BuildData.model_validate(raw)
