from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent / "config"


@lru_cache
def load_keywords() -> dict:
    with open(CONFIG_DIR / "keywords.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def load_locations() -> dict:
    with open(CONFIG_DIR / "locations.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)
