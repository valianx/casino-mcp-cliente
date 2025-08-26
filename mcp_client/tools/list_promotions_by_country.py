from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

from pydantic import BaseModel, field_validator

from ..logging import timed, json_log

import os
import httpx

# Reusable HTTP client to reduce latency (keep connections alive)
_client = httpx.Client(timeout=10.0)


class ListPromotionsParams(BaseModel):
    country: str
    page: int = 1
    limit: int = 50
    include: List[str] | None = None
    sort: str | None = None

    @field_validator("country")
    @classmethod
    def iso2(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 2:
            raise ValueError("country must be ISO-2")
        return v


def _paginate(rows: List[Dict[str, Any]], page: int, limit: int) -> Tuple[List[Dict[str, Any]], int]:
    total = len(rows)
    start = (page - 1) * limit
    end = start + limit
    return rows[start:end], total


def _extract_promotions_list(obj: Any) -> Optional[List[Dict[str, Any]]]:
    """Recursively extract the promotions list, preferring a dict's 'data' list.

    The remote tools may wrap the response like:
      { 'result': [ 'TextContent(...)', { 'result': { 'data': [ ... ] } } ] }
    We should ignore wrapper entries and return the innermost list under a 'data' key.
    """
    # Helper: try to parse JSON embedded in a string
    def _try_parse_json_str(s: str) -> Optional[Any]:
        s2 = s.strip()
        # Common case: direct JSON
        if s2.startswith("{") or s2.startswith("["):
            try:
                import json as _json
                return _json.loads(s2)
            except Exception:
                return None
        # Wrapper pattern: TextContent(... text=' {json} ' ...)
        if "text='" in s2:
            start = s2.find("text='") + len("text='")
            end = s2.rfind("'")
            if start > 0 and end > start:
                inner = s2[start:end]
                try:
                    import json as _json
                    return _json.loads(inner)
                except Exception:
                    return None
        return None

    # Prioritize dict with 'data' -> list
    if isinstance(obj, dict):
        data = obj.get("data")
        if isinstance(data, list):
            return data
        # Some servers return under 'result' or 'results'
        for key in ("result", "results", "payload", "output"):
            if key in obj:
                found = _extract_promotions_list(obj[key])
                if isinstance(found, list):
                    return found
        # Fallback: search all values
        for v in obj.values():
            found = _extract_promotions_list(v)
            if isinstance(found, list):
                return found
        return None

    # If it's a list, scan elements and prefer any element that yields a 'data' list
    if isinstance(obj, list):
        for item in obj:
            # If item is a string containing JSON, try to parse
            if isinstance(item, str):
                parsed = _try_parse_json_str(item)
                if parsed is not None:
                    found = _extract_promotions_list(parsed)
                    if isinstance(found, list):
                        return found
                # keep scanning next items
                continue
            found = _extract_promotions_list(item)
            if isinstance(found, list):
                return found
        # As absolute last resort, if the list itself looks like a list of promotions (dicts with 'id')
        if obj and all(isinstance(x, dict) for x in obj):
            return obj  # unwrapped list of dicts
        return None

    # If it's a string, try to parse JSON within
    if isinstance(obj, str):
        parsed = _try_parse_json_str(obj)
        if parsed is not None:
            return _extract_promotions_list(parsed)
    return None


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
    raise RuntimeError(f"Remote tool {tool_name} not reachable at {base}")


def _fetch_from_strapi_list(country_iso2: str, page: int, limit: int) -> Dict[str, Any] | None:
    """
    Attempt to fetch promotions list directly from Strapi if configured via STRAPI_BASE_URL / STRAPI_TOKEN.
    Tries several common filter shapes to match country fields.
    Returns a normalized dict with 'data' list if found, else None.
    """
    base = os.getenv("STRAPI_BASE_URL")
    if not base:
        return None
    base = base.rstrip("/")
    token = os.getenv("STRAPI_TOKEN")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Candidate query patterns (Strapi v4):
    candidates = [
        f"{base}/promotions?populate=*&filters[country][$eq]={country_iso2}&pagination[page]={page}&pagination[pageSize]={limit}",
        f"{base}/promotions?populate=*&filters[country][code][$eq]={country_iso2}&pagination[page]={page}&pagination[pageSize]={limit}",
        f"{base}/promotions?populate=*&filters[country_iso2][$eq]={country_iso2}&pagination[page]={page}&pagination[pageSize]={limit}",
        f"{base}/promotions?populate=*&filters[country][$containsi]={country_iso2}&pagination[page]={page}&pagination[pageSize]={limit}",
    ]
    for url in candidates:
        try:
            resp = _client.get(url, headers=headers)
        except Exception as e:
            json_log("tool.strapi_error", tool="list_promotions_by_country", url=url, error=str(e))
            continue
        if resp.status_code == 200:
            try:
                j = resp.json()
            except Exception:
                continue
            data = j.get("data") if isinstance(j, dict) else None
            if isinstance(data, list) and len(data) >= 0:
                json_log("tool.strapi_success", tool="list_promotions_by_country", url=url, count=len(data))
                # pass through including pagination/meta if present
                out: Dict[str, Any] = {"data": data}
                if isinstance(j, dict):
                    if "meta" in j:
                        out["meta"] = j["meta"]
                return out
        else:
            json_log("tool.strapi_status", tool="list_promotions_by_country", url=url, status_code=resp.status_code)
    return None


def list_promotions_by_country(params: Dict[str, Any]) -> Dict[str, Any]:
    # Apply defaults to align with working curl example when caller omite include/sort
    params = dict(params)
    if params.get("include") in (None, [], ""):
        params["include"] = ["countries", "terms"]
    if not params.get("sort"):
        params["sort"] = "createdAt:desc"
    p = ListPromotionsParams(**params)
    with timed(
        "tool.call",
        tool="list_promotions_by_country",
        params={**p.model_dump(), "include": None if p.include is None else "..."},
    ):
        # Try remote MCP server first
        try:
            # Send param synonyms to maximize compatibility with remote implementations
            params_for_remote = p.model_dump()
            country = params_for_remote.get("country")
            params_for_remote.update({
                "country_code": country,
                "countryCode": country,
                "iso2": country,
                "iso2_country": country,
            })
            json_log("tool.remote_request", tool="list_promotions_by_country", payload=params_for_remote)
            result = _call_remote_tool("list_promotions_by_country", params_for_remote)
            # If remote returns Strapi-like list, pass through
            if isinstance(result, dict) and result.get("data") and isinstance(result["data"], list):
                if len(result["data"]) == 0:
                    result.setdefault("pagination", {"page": p.page, "limit": p.limit, "total": 0, "pages": 0})
                    result["message"] = "No hay promociones disponibles por el momento."
                return result
            # If remote returns a plain list or dict with 'items', try to normalize
            if isinstance(result, list):
                data_list = result
                if len(data_list) == 0:
                    return {"data": [], "pagination": {"page": p.page, "limit": p.limit, "total": 0, "pages": 0}, "message": "No hay promociones disponibles por el momento."}
                return {"data": data_list}
            if isinstance(result, dict) and result.get("items"):
                data_list = result.get("items")
                if len(data_list) == 0:
                    return {"data": [], "pagination": {"page": p.page, "limit": p.limit, "total": 0, "pages": 0}, "message": "No hay promociones disponibles por el momento."}
                return {"data": data_list}
            # Try to find any nested promotions list under typical wrapper keys
            nested = _extract_promotions_list(result)
            if nested is not None:
                return {"data": nested}
        except Exception as e:
            json_log("tool.remote_exception", tool="list_promotions_by_country", error=str(e))

        # Remote returned empty or failed: try Strapi fallback if configured
        fallback = _fetch_from_strapi_list(p.country, p.page, p.limit)
        if fallback is not None:
            return fallback

        # No data from remote nor Strapi
        return {
            "data": [],
            "pagination": {"page": p.page, "limit": p.limit, "total": 0, "pages": 0},
            "message": "No hay promociones activas en este momento.",
        }
