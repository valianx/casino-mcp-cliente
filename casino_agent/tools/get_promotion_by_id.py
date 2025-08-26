from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel

from ..core import timed, json_log

import os
import httpx

# Reusable HTTP client
_client = httpx.Client(timeout=5.0)


class GetPromotionByIdParams(BaseModel):
    id: int
    include: list[str] | None = None


def _call_remote_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    base = os.getenv("MCP_SERVER_URL", "http://localhost:8000").rstrip("/")
    endpoints = [
        f"{base}/tools/{tool_name}",
        f"{base}/api/tools/{tool_name}",
        f"{base}/tool/{tool_name}",
        f"{base}/api/tool/{tool_name}",
    ]
    headers = {"Content-Type": "application/json"}
    json_log("info", "Tool remote attempt", tool=tool_name, endpoints=endpoints)
    for url in endpoints:
        try:
            resp = _client.post(url, json={"params": params}, headers=headers)
        except Exception as e:
            json_log("error", "Tool remote error", tool=tool_name, url=url, error=str(e))
            continue
        json_log("info", "Tool remote status", tool=tool_name, url=url, status_code=resp.status_code)
        if resp.status_code == 200:
            try:
                j = resp.json()
                json_log("info", "Tool remote success", tool=tool_name, url=url)
                return j
            except Exception as e:
                json_log("error", "Tool remote error", tool=tool_name, url=url, error=f"invalid_json:{e}")
                continue
    json_log("warning", "Tool remote unreachable", tool=tool_name, base=base)
    raise RuntimeError(f"Remote tool {tool_name} not reachable at {base}")


def _find_data(obj: Any):
    """Recursively search for a 'data' key in nested dict/list responses."""
    if isinstance(obj, dict):
        if "data" in obj:
            return obj["data"]
        for v in obj.values():
            found = _find_data(v)
            if found is not None:
                return found
    if isinstance(obj, list):
        for item in obj:
            found = _find_data(item)
            if found is not None:
                return found
    return None


def get_promotion_by_id(params: Dict[str, Any]) -> Dict[str, Any]:
    # Coerce id to int if possible to avoid mismatches when callers pass strings
    raw_id = params.get("id")
    json_log("info", "Tool invoked", tool="get_promotion_by_id", raw_id=raw_id)
    try:
        promotion_id = int(raw_id)
    except Exception:
        json_log("error", "Tool invalid input", tool="get_promotion_by_id", raw_id=raw_id)
        # return a clear, user-facing message structure
        return {"data": None, "message": "ID de promoción inválido. Proporcione un identificador numérico."}

    # Ensure params used for remote call have proper types
    params_for_call = {**params, "id": promotion_id}
    p = GetPromotionByIdParams(**params_for_call)
    with timed(
        "tool.call",
        tool="get_promotion_by_id",
        params={"id": p.id, "include": None if p.include is None else "..."},
    ):
        # Try remote first
        try:
            json_log("info", "Tool remote pre call", tool="get_promotion_by_id", id=promotion_id)
            result = _call_remote_tool("get_promotion_by_id", p.model_dump())
            json_log("info", "Tool remote result", tool="get_promotion_by_id", result_type=type(result).__name__)
            # Try to find a 'data' payload anywhere in the response (some wrappers nest it)
            data = None
            if isinstance(result, dict) or isinstance(result, list):
                data = _find_data(result)
            # If remote already returns Strapi-like shape, pass through
            if data is not None:
                # If data is a dict with attributes, check id matches requested id
                if isinstance(data, dict) and data.get("attributes"):
                    returned_id = data.get("id")
                    if returned_id is None or int(returned_id) != promotion_id:
                        # Signal mismatch by returning no match
                        json_log("warning", "Tool mismatch", tool="get_promotion_by_id", requested=promotion_id, returned=returned_id)
                        return {"data": None, "message": "No se encontró una promoción con el ID solicitado."}
                    # IDs match
                    return {"data": data}
                # If data is a list, search for matching id
                if isinstance(data, list):
                    for item in data:
                        try:
                            if int(item.get("id") or 0) == promotion_id:
                                json_log("info", "Tool found in list", tool="get_promotion_by_id", id=promotion_id)
                                return {"data": item}
                        except Exception:
                            continue
                    # not found in list
                    json_log("warning", "Tool not found in list", tool="get_promotion_by_id", id=promotion_id)
                    return {"data": None, "message": "No se encontró una promoción con el ID solicitado."}
                # Return the result as-is
                return result
            # If remote returns a plain object with attributes nested under 'data.attributes' or similar, normalize
            if isinstance(result, dict) and result.get("data"):
                # attempt to normalize structure
                data = result.get("data")
                if isinstance(data, list) and len(data) > 0:
                    # take first
                    return {"data": data[0]}
                return {"data": data}
        except Exception as e:
            json_log("error", "Tool remote exception", tool="get_promotion_by_id", error=str(e))
            # fallthrough to local
            pass

    # No local mock fallback: when remote fails or the promotion isn't found, return the formal message
    json_log("info", "Tool no data", tool="get_promotion_by_id", id=promotion_id)
    return {"data": None, "message": "No hay promociones activas en este momento."}
