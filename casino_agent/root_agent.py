from __future__ import annotations

from typing import Any, List, Optional
import sys
import os
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Make sibling package `casino_agent` importable even if ADK runs from another CWD
_project_root = Path(__file__).resolve().parents[1]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Reuse internal tool implementations (relative import within package)
from .tools.get_promotion_by_id import get_promotion_by_id as _get_by_id
from .tools.list_promotions_by_country import (
    list_promotions_by_country as _list_by_country,
)


def list_promotions_by_country(
    country: str,
    page: int = 1,
    limit: int = 50,
    include: Optional[List[str]] = None,
    sort: Optional[str] = None,
) -> dict[str, Any]:
    """
    Devuelve una lista paginada de promociones disponibles para un país.
    """
    # Normalize country to ISO-2 if possible (accept full country names)
    iso2 = _country_name_to_iso(country) if country else None
    if not iso2:
        return "Para continuar, por favor indíqueme su país."

    # Call the underlying tool implementation
    raw = _list_by_country(
        {
            "country": iso2,
            "page": page,
            "limit": limit,
            "include": include,
            "sort": sort,
        }
    )

    # If the tool returned an error-like structure, convert to Spanish text
    if isinstance(raw, dict) and raw.get("error"):
        return (
            raw.get("message")
            or "No pude recuperar las promociones en este momento. Inténtelo de nuevo más tarde."
        )

    # Normalize expected structure: {'data': [ { 'id':..., 'attributes': { 'title', 'startDate', 'endDate', ... } } ], ...}
    items = None
    if isinstance(raw, dict) and "data" in raw:
        items = raw.get("data")
    elif isinstance(raw, list):
        items = raw
    else:
        items = []

    if not items:
        return f"No hay promociones disponibles por el momento para {iso2}."

    # Build a human-readable Spanish summary
    currency = _country_to_currency(iso2)
    lines = [f"Promociones disponibles en {iso2} ({currency or 'moneda local'}):"]
    for it in items[:limit]:
        pid = it.get("id") if isinstance(it, dict) else None
        attrs = it.get("attributes", {}) if isinstance(it, dict) else {}
        title = attrs.get("title") or it.get("title") if isinstance(it, dict) else None
        start = attrs.get("startDate") or attrs.get("start_date")
        end = attrs.get("endDate") or attrs.get("end_date")
        short = title or "Promoción sin título"
        # If the promotion includes an amount, try to format it in the country's currency
        amount = attrs.get("amount") or attrs.get("value") or attrs.get("bonus_amount")
        amount_text = None
        if amount is not None:
            amount_text = _format_currency_value(amount, currency)
        id_tag = f"[ID {pid}] " if pid is not None else ""
        if start and end:
            if amount_text:
                lines.append(f"- {id_tag}{short} ({amount_text}) — vigencia: {start} a {end}")
            else:
                lines.append(f"- {id_tag}{short} (vigencia: {start} a {end})")
        else:
            if amount_text:
                lines.append(f"- {id_tag}{short} ({amount_text})")
            else:
                lines.append(f"- {id_tag}{short}")

    lines.append("Si desea detalles de una promoción en particular, indíqueme el ID de la promoción.")
    return "\n".join(lines)


def get_promotion_by_id(id: int, include: Optional[List[str]] = None, country: Optional[str] = None) -> dict[str, Any]:
    """Devuelve los detalles de una promoción por su ID.

    Este wrapper exige que se confirme el `country` antes de realizar la llamada.
    Si falta, devuelve un mensaje para que el modelo pida el país al usuario.
    """
    iso2 = _country_name_to_iso(country) if country else None
    if not iso2:
        return "Antes de obtener una promoción por ID, por favor confirme el país del usuario."

    raw = _get_by_id({"id": id, "include": include, "country": iso2})

    # Handle error-like responses
    if isinstance(raw, dict) and raw.get("error"):
        return raw.get("message") or "No pude obtener la promoción solicitada."

    # Accept Strapi-like pass-through: {'data': { 'id':..., 'attributes': {...} }}
    data = None
    if isinstance(raw, dict) and "data" in raw:
        data = raw.get("data")
    elif isinstance(raw, dict) and raw.get("id"):
        data = raw

    if not data:
        return "No se encontró la promoción solicitada."

    attrs = data.get("attributes", {}) if isinstance(data, dict) else {}
    title = attrs.get("title") or data.get("title")
    summary = attrs.get("summary") or attrs.get("description") or ""
    content = attrs.get("content") or attrs.get("content_rich") or ""
    start = attrs.get("startDate") or attrs.get("start_date")
    end = attrs.get("endDate") or attrs.get("end_date")

    parts = [f"Detalle de la promoción (ID: {data.get('id') if isinstance(data, dict) else id}):"]
    if title:
        parts.append(f"Título: {title}")
    if start or end:
        parts.append(f"Vigencia: {start or '—'} a {end or '—'}")
    if summary:
        parts.append(f"Resumen: {summary}")
    if content:
        parts.append(f"Detalles: {content}")
    # If the promotion contains amounts, format them according to the country
    currency = _country_to_currency(iso2 if 'iso2' in locals() else None)
    amount = attrs.get("amount") or attrs.get("value") or attrs.get("bonus_amount")
    if amount is not None:
        parts.append(f"Monto/bono: {_format_currency_value(amount, currency)}")

    return "\n".join(parts)


def _extract_iso2(text: str) -> Optional[str]:
    if not text:
        return None
    import re
    m = re.search(r"\b([A-Za-z]{2})\b", text)
    return m.group(1).upper() if m else None


def _format_name(name: str) -> str:
    """Format a raw name so each given name/lastname part starts with uppercase followed by lowercase.

    Handles hyphenated names (e.g., 'ana-maria' -> 'Ana-Maria').
    """
    if not name:
        return ""
    parts = [p for p in name.strip().split() if p]
    formatted_parts: list[str] = []
    for p in parts:
        subparts = p.split('-')
        formatted_sub = '-'.join(sp.capitalize() for sp in subparts if sp)
        formatted_parts.append(formatted_sub)
    return ' '.join(formatted_parts)


# Small mapping of common country names to ISO-2 codes (extend as needed)
COUNTRY_MAP: dict[str, str] = {
    "chile": "CL",
    "argentina": "AR",
    "méxico": "MX",
    "mexico": "MX",
    "españa": "ES",
    "spain": "ES",
    "estados unidos": "US",
    "estados unidos de america": "US",
    "estados unidos de américa": "US",
    "usa": "US",
}


def _country_name_to_iso(text: str) -> Optional[str]:
    """Try to map a free-text country name to an ISO-2 code using COUNTRY_MAP.

    Returns the ISO-2 uppercase code or None if not found.
    """
    if not text:
        return None
    t = text.strip().lower()
    # direct substring match
    for name, iso in COUNTRY_MAP.items():
        if name in t:
            return iso
    # check word-level matches
    import re
    for w in re.findall(r"[\wÀ-ÿ]+", t):
        if w in COUNTRY_MAP:
            return COUNTRY_MAP[w]
    # fallback: try extracting a 2-letter code
    return _extract_iso2(text)


def _parse_name_and_country(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract a probable (name, iso2) pair from free text.

    Heuristics:
    - If a known country name appears, map it to ISO and treat the rest as name.
    - If a 2-letter code is found, map it and take remaining token(s) as name.
    - Otherwise, return (first_word, None) assuming it's a name.
    """
    if not text:
        return None, None
    import re
    iso = _country_name_to_iso(text)
    if iso:
        # remove the first matched country substring
        lowered = text.lower()
        for name in COUNTRY_MAP:
            if name in lowered:
                candidate = re.sub(re.escape(name), "", lowered, flags=re.IGNORECASE).strip()
                break
        else:
            candidate = re.sub(r"\b[A-Za-z]{2}\b", "", text).strip()
        # clean common prefixes
        candidate = re.sub(r"\b(me llamo|soy|mi nombre es|mi nombre)\b", "", candidate, flags=re.I).strip(" ,")
        # pick first token as name (allow single given name)
        m = re.search(r"([A-Za-zÀ-ÿ-]+)", candidate)
        name = m.group(1) if m else None
        return name, iso

    # try to extract iso2 code directly
    iso2 = _extract_iso2(text)
    if iso2:
        candidate = re.sub(r"\b" + re.escape(iso2) + r"\b", "", text, flags=re.I).strip()
        m = re.search(r"([A-Za-zÀ-ÿ-]+)", candidate)
        name = m.group(1) if m else None
        return name, iso2

    # fallback: assume the first token is the name
    m = re.search(r"([A-Za-zÀ-ÿ-]+)", text)
    return (m.group(1) if m else None, None)


# Map country ISO to common currency codes
COUNTRY_CURRENCY: dict[str, str] = {
    "CL": "CLP",
    "AR": "ARS",
    "MX": "MXN",
    "ES": "EUR",
    "US": "USD",
}


def _country_to_currency(iso2: Optional[str]) -> Optional[str]:
    if not iso2:
        return None
    return COUNTRY_CURRENCY.get(iso2.upper())


def _format_currency_value(value: Any, currency: Optional[str]) -> str:
    """Format a numeric value into a human-friendly string with thousands separators.

    Uses '.' as thousands separator and ',' as decimal separator (Spanish-style). Returns
    a string like '543.000 CLP' or '500 USD'. If value is non-numeric, returns it unchanged with currency appended.
    """
    if currency is None:
        currency = ""
    try:
        # Try to coerce to float
        v = float(str(value).replace(".", "").replace(",", "."))
    except Exception:
        s = str(value).strip()
        return f"{s} {currency}".strip()

    # Decide if integer
    if abs(v - int(v)) < 0.001:
        iv = int(round(v))
        # format with dot as thousands separator
        s = f"{iv:,}".replace(",", ".")
        return f"{s} {currency}".strip()
    else:
        s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{s} {currency}".strip()


def _greeting_for_country(iso2: str) -> str:
    """Return a time-aware greeting for the given ISO2 country code.

    Uses a small built-in mapping from country to a representative timezone.
    Falls back to UTC if unknown.
    """
    try:
        from datetime import datetime
        import zoneinfo
    except Exception:
        # Fallback simple greeting
        return "Buenos días"

    tz_map = {
        "CL": "America/Santiago",
        "AR": "America/Argentina/Buenos_Aires",
        "MX": "America/Mexico_City",
        "ES": "Europe/Madrid",
        "US": "America/New_York",
    }
    tz_name = tz_map.get(iso2.upper(), "UTC")
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
        now = datetime.now(tz)
        hour = now.hour
        if 5 <= hour <= 11:
            return "Buenos días"
        if 12 <= hour <= 19:
            return "Buenas tardes"
        return "Buenas noches"
    except Exception:
        return "Buenos días"


def _response(*args, **kwargs) -> str:
    """Fallback para evitar errores cuando el modelo intenta llamar 'response'."""
    return "Por favor responda directamente sin usar herramientas para saludos o conversación general."


INSTRUCTION = (
    "Usted es el **Agente ayuda Juegalo**, especializado en *promociones de casino*. "
    "Su objetivo es asistir de forma clara, cordial y profesional, usando únicamente las herramientas disponibles.\n\n"

    "### Flujo de Conversación Detallado\n"
    "1. **Saludo Inicial**: Al primer contacto, salude amablemente y pida **únicamente el nombre** del usuario. No pida el país aún.\n"
    "   - *Ejemplo*: «¡Hola! Soy su asistente de promociones. Para comenzar, ¿me podría indicar su nombre?»\n"
    "2. **Confirmación y Pregunta Abierta**: Una vez que el usuario proporcione su nombre, salúdelo de vuelta usando su nombre (formateado con mayúscula inicial) y pregúntele qué necesita. No asuma que quiere ver promociones todavía.\n"
    "   - *Ejemplo*: «Un gusto, Mario. ¿En qué puedo ayudarle hoy?»\n"
    "3. **Solicitud de País (Condicional)**: **Solamente si** el usuario pide explícitamente ver, listar o consultar promociones, pídale su país de residencia para poder usar la herramienta.\n"
    "   - *Ejemplo*: «Claro. Para poder mostrarle las promociones, por favor, indíqueme su país.»\n"
    "4. **Uso de Herramientas**: Una vez que tenga el país, utilice la herramienta `list_promotions_by_country`. Al presentar los resultados, use el saludo apropiado para la zona horaria del país (Buenos días/tardes/noches). **Este saludo solo se debe usar una vez en toda la conversación**. En respuestas posteriores, no salude de nuevo.\n"
    "   - *Ejemplo*: «Buenas tardes, Mario. Estas son las promociones disponibles para ti en Chile (CLP): ...»\n"
    "5. **Detalles de Promoción**: Si el usuario pide detalles de una promoción (por ID o por nombre), use la herramienta `get_promotion_by_id`.\n"
    "6. **Pregunta de Cierre**: Después de listar las promociones, pregunte de forma abierta por el siguiente paso. **Use esta frase exacta**: «Indíqueme de cuál promoción necesita detalles.»\n\n"

    "### Alcance y herramientas\n"
    "- Responda **exclusivamente** sobre *promociones de casino*.\n"
    "- **Herramientas disponibles** (únicas que puede usar): `list_promotions_by_country`, `get_promotion_by_id`.\n"
    "- **No** use ninguna otra función ni hable de temas fuera de promociones.\n\n"

    "### Estrategia de uso de herramientas\n"
    "- **NO** use `list_promotions_by_country` hasta que el usuario haya pedido ver promociones y haya proporcionado su país.\n"
    "- Cuando el usuario pida detalles de una promoción, identifíquela por su **ID** o por su **nombre** (p. ej., si dice «dime más sobre el bono de bienvenida», busque el ID correspondiente en el listado previo y úselo con `get_promotion_by_id`).\n"
    "- En listados, incluya siempre el **ID** y el **título** de cada promoción (p. ej., «- 11 - Bono de Bienvenida»).\n\n"
    "### Estilo y tono\n"
    "- Mantenga un tono **natural y formal**.\n"
    "- Sea **conciso** y claro.\n\n"

    "### Restricciones\n"
    "- **NO** invente datos; use únicamente lo devuelto por las herramientas.\n"
    "- **NO** cambie el tema fuera de promociones.\n"
)


def create_agent() -> LlmAgent:
    # Get model name from environment variables
    model_name = os.getenv("MODEL", "gpt-5-nano")
    
    # Configure OpenAI model via LiteLLM
    openai_api_base = os.getenv("OPENAI_API_BASE")  # optional
    if openai_api_base:
        model = LiteLlm(
            model=f"openai/{model_name}",
            api_base=openai_api_base,
            timeout=300
        )
    else:
        model = LiteLlm(
            model=f"openai/{model_name}",
            timeout=300
        )

    # Create tools using FunctionTool
    get_promotion_tool = FunctionTool(get_promotion_by_id)
    list_promotions_tool = FunctionTool(list_promotions_by_country)

    return LlmAgent(
        model=model,
        name="Agente_ayuda_Juegalo",
        description=(
            "Agente que responde preguntas sobre promociones de casino utilizando herramientas dedicadas."
        ),
        instruction=INSTRUCTION,
        tools=[
            get_promotion_tool,
            list_promotions_tool
        ],
    )


# ADK busca un símbolo accesible; exportamos una instancia y una fábrica
root_agent: LlmAgent = create_agent()
