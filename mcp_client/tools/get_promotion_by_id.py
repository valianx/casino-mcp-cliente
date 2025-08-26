from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel

from ..logging import timed
from ..logging import json_log

import os
import httpx

# Reusable HTTP client
_client = httpx.Client(timeout=5.0)


class GetPromotionByIdParams(BaseModel):
    id: int
    include: list[str] | None = None


def _call_remote_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    base = os.getenv("MCP_SERVER", "http://localhost:8000").rstrip("/")
    endpoints = [
        f"{base}/tools/{tool_name}",
        f"{base}/api/tools/{tool_name}",
        f"{base}/tool/{tool_name}",
        f"{base}/api/tool/{tool_name}",
    ]
    headers = {"Content-Type": "application/json"}
    json_log("tool.remote_attempt", tool=tool_name, endpoints=endpoints)
    for url in endpoints:
        try:
            resp = _client.post(url, json={"params": params}, headers=headers)
        except Exception as e:
            json_log("tool.remote_error", tool=tool_name, url=url, error=str(e))
            continue
        json_log("tool.remote_status", tool=tool_name, url=url, status_code=resp.status_code)
        if resp.status_code == 200:
            try:
                j = resp.json()
                json_log("tool.remote_success", tool=tool_name, url=url)
                return j
            except Exception as e:
                json_log("tool.remote_error", tool=tool_name, url=url, error=f"invalid_json:{e}")
                continue
    json_log("tool.remote_unreachable", tool=tool_name, base=base)
    raise RuntimeError(f"Remote tool {tool_name} not reachable at {base}")


def _map_mock_to_strapi(item) -> Dict[str, Any]:
    # Map our simple Promotion dataclass to a Strapi-like attributes payload
    return {
        "id": item.id,
        "attributes": {
            "title": item.title,
            "subtitle": None,
            "content": item.description,
            "content_rich": f"<p>{item.description}</p>",
            "showInHome": False,
            "showInFooter": False,
            "order": None,
            "bigPromotion": False,
            "createdAt": None,
            "updatedAt": None,
            "publishedAt": None,
            "isHtml": None,
            "slug": item.slug,
            "imgHomeDesktop": None,
            "imgHomeMobile": None,
            "imgCardDesktop": None,
            "imgCardMobile": None,
            "imgPromotionDesktop": None,
            "imgPromotionMobile": None,
            "imgBigPromotion": None,
            # keep legacy fields too
            "startDate": item.startDate,
            "endDate": item.endDate,
            "country": item.country,
        },
    }


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


def _fetch_from_strapi(promotion_id: int) -> Dict[str, Any] | None:
    """
    Try to fetch full promotion record directly from Strapi REST API if configured.
    Uses STRAPI_BASE_URL and STRAPI_TOKEN environment variables when available.
    Returns a Strapi-like {'data': {...}} object or None on failure.
    """
    strapi_base = os.getenv("STRAPI_BASE_URL")
    if not strapi_base:
        return None
    strapi_base = strapi_base.rstrip("/")
    token = os.getenv("STRAPI_TOKEN")
    url = f"{strapi_base}/promotions/{promotion_id}?populate=*"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = _client.get(url, headers=headers, timeout=5.0)
        if resp.status_code == 200:
            try:
                j = resp.json()
                # Strapi returns {"data": {...}} normally
                if isinstance(j, dict) and j.get("data"):
                    return j
            except Exception:
                return None
    except Exception:
        return None
    return None


def get_promotion_by_id(params: Dict[str, Any]) -> Dict[str, Any]:
    # Coerce id to int if possible to avoid mismatches when callers pass strings
    raw_id = params.get("id")
    json_log("tool.invoked", tool="get_promotion_by_id", raw_id=raw_id)
    try:
        promotion_id = int(raw_id)
    except Exception:
        json_log("tool.invalid_input", tool="get_promotion_by_id", raw_id=raw_id)
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
            json_log("tool.remote_pre_call", tool="get_promotion_by_id", id=promotion_id)
            result = _call_remote_tool("get_promotion_by_id", p.model_dump())
            json_log("tool.remote_result", tool="get_promotion_by_id", result_type=type(result).__name__)
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
                        # Attempt to fetch full Strapi record by ID as fallback
                        strapi = _fetch_from_strapi(promotion_id)
                        if strapi:
                            json_log("tool.strapi_fallback", tool="get_promotion_by_id", id=promotion_id)
                            return strapi
                        # otherwise proceed but signal mismatch by returning no match
                        json_log("tool.mismatch", tool="get_promotion_by_id", requested=promotion_id, returned=returned_id)
                        return {"data": None, "message": "No se encontró una promoción con el ID solicitado."}
                    # IDs match
                    attrs = data.get("attributes", {})
                    if not attrs.get("content") or not attrs.get("content_rich"):
                        strapi = _fetch_from_strapi(promotion_id)
                        if strapi:
                            json_log("tool.strapi_fallback", tool="get_promotion_by_id", id=promotion_id)
                            return strapi
                    return {"data": data}
                # If data is a list, search for matching id
                if isinstance(data, list):
                    for item in data:
                        try:
                            if int(item.get("id") or 0) == promotion_id:
                                json_log("tool.found_in_list", tool="get_promotion_by_id", id=promotion_id)
                                return {"data": item}
                        except Exception:
                            continue
                    # not found in list
                    json_log("tool.not_found_in_list", tool="get_promotion_by_id", id=promotion_id)
                    return {"data": None, "message": "No se encontró una promoción con el ID solicitado."}
                # If attributes are present but missing detailed content, try Strapi directly
                attrs = result["data"].get("attributes", {})
                if not attrs.get("content") or not attrs.get("content_rich"):
                    strapi = _fetch_from_strapi(promotion_id)
                    if strapi:
                        json_log("tool.strapi_fallback", tool="get_promotion_by_id", id=promotion_id)
                        return strapi
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
            json_log("tool.remote_exception", tool="get_promotion_by_id", error=str(e))
            # fallthrough to local
            pass

    # No local mock fallback: when remote fails or the promotion isn't found, return the formal message
    json_log("tool.no_data", tool="get_promotion_by_id", id=promotion_id)
    return {"data": None, "message": "No hay promociones activas en este momento."}
