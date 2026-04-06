"""JSON-backed mock data loader with LRU caching.

Each JSON file is loaded once and cached in memory.
"""

import json
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent


@lru_cache(maxsize=8)
def _load(name: str) -> dict:
    return json.loads((_DIR / name).read_text("utf-8"))


def get_districts() -> dict:
    return _load("districts.json")


def get_floating_population() -> dict:
    return _load("floating_population.json")


def get_estimated_sales() -> dict:
    return _load("estimated_sales.json")


def get_store_info() -> dict:
    return _load("store_info.json")


def get_population_info() -> dict:
    return _load("population_info.json")


def get_store_history() -> dict:
    return _load("store_history.json")


def get_recommendations_data() -> dict:
    return _load("recommendations.json")
