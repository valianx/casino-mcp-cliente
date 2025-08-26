from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

BASE = Path(__file__).parent


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_tool_schemas() -> List[Dict[str, Any]]:
    # Return tools in OpenAI/Ollama function-calling style
    list_by_country = _load_json(BASE / "list_promotions_by_country.json")
    get_by_id = _load_json(BASE / "get_promotion_by_id.json")

    return [
        {
            "type": "function",
            "function": {
                "name": "list_promotions_by_country",
                "description": list_by_country.get("description", ""),
                "parameters": list_by_country.get("parameters", {}),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_promotion_by_id",
                "description": get_by_id.get("description", ""),
                "parameters": get_by_id.get("parameters", {}),
            },
        },
    ]
