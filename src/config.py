import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
BLOCKED_ROADS_PATH = DATA_DIR / "blocked_roads.json"
ROUTE_PAIRS_PATH = PROJECT_ROOT / "src" / "PRT routes" / "route_pairs.json"
GOOGLE_MAPS_API_KEY_ENV = "GOOGLE_MAPS_API_KEY"


@lru_cache(maxsize=1)
def _load_project_env() -> None:
    """Load project-local environment variables once."""
    load_dotenv(PROJECT_ROOT / ".env")


def get_google_api_key() -> Optional[str]:
    """Return configured Google Maps API key, otherwise None."""
    _load_project_env()
    api_key = os.getenv(GOOGLE_MAPS_API_KEY_ENV, "").strip()
    return api_key or None
