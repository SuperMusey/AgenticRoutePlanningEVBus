"""
MCP tools: read downloaded news articles and inspect blocked_roads.json.

Workflow:
  1. read_news_file(file_path)        — client receives raw article text
  2. client classifies + extracts     — using classify_disruption / extract_disruption_data prompts
  3. save_blocked_roads(...)          — in route_tools, persists polyline to blocked_roads.json
  4. load_blocked_roads()             — inspect current saved disruption (optional)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from src.config import BLOCKED_ROADS_PATH

logger = logging.getLogger(__name__)


def register(mcp) -> None:
    @mcp.tool()
    def read_news_file(file_path: str) -> Dict[str, Any]:
        """
        Read a downloaded news article or traffic bulletin from a local file.

        Supports plain text (.txt), HTML (.html/.htm), and JSON (.json) files.
        Returns the raw content for the client to classify and extract using
        the classify_disruption and extract_disruption_data prompts.

        Args:
            file_path: Absolute or relative path to the downloaded news file.
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return {"success": False, "file_path": file_path, "error": "File not found"}

            content = path.read_text(encoding="utf-8", errors="replace")
            return {
                "success": True,
                "file_path": str(path.resolve()),
                "file_name": path.name,
                "content": content,
            }
        except Exception as e:
            logger.error("read_news_file failed for %s: %s", file_path, e)
            return {"success": False, "file_path": file_path, "error": str(e)}

    @mcp.tool()
    def load_blocked_roads() -> Dict[str, Any]:
        """
        Load the current blocked roads data from blocked_roads.json.

        Returns the saved route name and coordinates in the same format as
        route_pairs.json: { "routes": [{ "road_name": [[lat, lng], ...] }] }
        """
        try:
            if not BLOCKED_ROADS_PATH.exists():
                return {
                    "success": False,
                    "error": "No blocked roads data found. Call save_blocked_roads first.",
                }
            with open(BLOCKED_ROADS_PATH, "r") as f:
                data = json.load(f)
            return {"success": True, "data": data}
        except Exception as e:
            logger.error("load_blocked_roads failed: %s", e)
            return {"success": False, "error": str(e)}
