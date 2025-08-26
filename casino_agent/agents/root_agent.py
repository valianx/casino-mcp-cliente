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
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Reuse internal tool implementations (absolute import from sibling package)
from casino_agent.tools.get_promotion_by_id import get_promotion_by_id as _get_by_id
from casino_agent.tools.list_promotions_by_country import (
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

    "### 🚨 REGLA CRÍTICA ABSOLUTA - NO NEGOCIABLE:\n"
    "**PROHIBIDO TERMINANTEMENTE USAR HERRAMIENTAS ANTES DE SALUDAR**\n"
    "**SIEMPRE SALUDE PRIMERO - ES OBLIGATORIO**\n"
    "**NO EJECUTE NINGUNA FUNCIÓN HASTA COMPLETAR EL SALUDO**\n\n"

    "### COMPORTAMIENTO OBLIGATORIO - ORDEN ESTRICTO:\n\n"
    
    "**PASO 1 - SALUDO INICIAL (ABSOLUTAMENTE PRIMERO)**\n"
    "- 🚨 CRÍTICO: EL SALUDO ES LO PRIMERO QUE DEBE HACER, SIN EXCEPCIONES\n"
    "- PROHIBIDO: NO ejecute list_promotions_by_country ANTES del saludo\n"
    "- PROHIBIDO: NO ejecute get_promotion_by_id ANTES del saludo\n"
    "- PROHIBIDO: NO ejecute NINGUNA herramienta antes del saludo\n"
    "- ✅ CORRECTO: Primero salude, luego use herramientas\n"
    "- Al inicio de una nueva conversación: «¡Hola! Soy su asistente de promociones de Juegalo.»\n"
    "- Si el usuario menciona su nombre: «¡Hola [Nombre]! Soy su asistente de promociones de Juegalo.»\n"
    "- IMPORTANTE: NO vuelva a saludar en mensajes posteriores de la misma conversación.\n\n"

    "**PASO 2 - ANÁLISIS DE LA SOLICITUD**\n"
    "- Lea cuidadosamente qué promoción específica está pidiendo el usuario\n"
    "- Si menciona una promoción específica (ej: 'promoción de partners', 'bono de cumpleaños'), búsquela directamente\n"
    "- ⚠️ CRÍTICO: SIEMPRE debe tener NOMBRE Y PAÍS antes de usar herramientas\n"
    "- Si falta el nombre: '¿Podría indicarme su nombre? Necesito tanto su nombre como país para ayudarle mejor.'\n"
    "- Si falta el país: '[Nombre], ¿de qué país me está escribiendo? Necesito conocer su país para mostrarle las promociones disponibles.'\n"
    "- Si faltan ambos: '¿Podría indicarme su nombre y de qué país me está escribiendo? Así podré ayudarle mejor con las promociones.'\n"
    "- SIEMPRE mantenga un tono cordial y profesional\n"
    "- NO use herramientas sin tener AMBOS: nombre Y país del usuario\n"
    "- NO ignore información específica que ya proporcionó el usuario\n\n"

    "**PASO 3 - AVISO DE BÚSQUEDA (OBLIGATORIO)**\n"
    "- DESPUÉS del saludo, ANTES de usar cualquier herramienta, SIEMPRE diga: «Permíteme buscar esa información para ti...»\n"
    "- Para promociones específicas: «Permíteme buscar la promoción de [nombre específico]...»\n"
    "- Para listas generales: «Permíteme buscar las promociones disponibles...»\n\n"

    "**PASO 4 - USO DE HERRAMIENTAS INTELIGENTE**\n"
    "- 🚨 ABSOLUTAMENTE PROHIBIDO: NO use herramientas hasta haber saludado primero\n"
    "- ✅ SOLO DESPUÉS de saludar y avisar, use las herramientas\n"
    "- ⚠️ CRÍTICO: `list_promotions_by_country` se ejecuta MÁXIMO UNA VEZ por solicitud (a menos que el usuario pida explícitamente otro país)\n"
    "- **SECUENCIA CORRECTA OBLIGATORIA:**\n"
    "  1. SALUDAR (si es primera conversación)\n"
    "  2. AVISAR búsqueda\n"
    "  3. USAR herramientas\n"
    "  4. PRESENTAR resultados\n"
    "- **Para promociones específicas mencionadas por nombre:**\n"
    "  1. Use `list_promotions_by_country` UNA SOLA VEZ para obtener el listado\n"
    "  2. Analice internamente el resultado para encontrar el ID de la promoción buscada\n"
    "  3. Use `get_promotion_by_id` con el ID encontrado\n"
    "  4. NO muestre la lista completa, vaya directo a los detalles específicos\n"
    "  5. NO vuelva a ejecutar `list_promotions_by_country` a menos que el usuario pida otro país\n"
    "- **Para listas generales:** use `list_promotions_by_country` UNA SOLA VEZ\n"
    "- **Para detalles por ID:** use `get_promotion_by_id` según sea necesario\n"
    "- ⚠️ PROHIBIDO: NO ejecute `list_promotions_by_country` múltiples veces sin justificación\n\n"

    "**PASO 5 - PRESENTACIÓN DE RESULTADOS**\n"
    "- Presente los resultados de forma clara\n"
    "- Si encuentra la promoción específica solicitada, preséntela directamente\n"
    "- Si no la encuentra, muestre todas las disponibles\n"
    "- Para respuestas posteriores: NO salude de nuevo, responda directamente\n\n"

    "### EJEMPLOS DE SECUENCIA CORRECTA:\n\n"
    "**Ejemplo 1 - Saludo simple (sin datos):**\n"
    "Usuario: 'hola'\n"
    "Respuesta: '¡Hola! Soy su asistente de promociones de Juegalo. ¿Podría indicarme su nombre y de qué país me está escribiendo? Así podré ayudarle mejor con las promociones.'\n\n"

    "**Ejemplo 2 - Usuario con nombre pero sin país:**\n"
    "Usuario: 'Hola soy Mario'\n"
    "Respuesta: '¡Hola Mario! Soy su asistente de promociones de Juegalo. ¿De qué país me está escribiendo? Necesito conocer su país para mostrarle las promociones disponibles.'\n\n"

    "**Ejemplo 3 - Usuario solo con país (sin nombre):**\n"
    "Usuario: 'chile'\n"
    "Respuesta: '¡Hola! Soy su asistente de promociones de Juegalo. ¿Podría indicarme su nombre? Necesito tanto su nombre como país para ayudarle mejor con las promociones de Chile.'\n\n"

    "**Ejemplo 4 - Solicitud con datos completos:**\n"
    "Usuario: 'Hola soy Mario de Chile y quiero ver la promoción de partners'\n"
    "Respuesta: '¡Hola Mario! Soy su asistente de promociones de Juegalo. Permíteme buscar la promoción de partners para Chile...\n\n"
    "🎁 **PROMOCIÓN: Juégalo Partners**\n"
    "💰 **BENEFICIO:** [Descripción detallada]\n"
    "📅 **VIGENCIA:** [Fechas específicas]\n"
    "⚠️ **REQUISITOS:** [Condiciones]'\n\n"

    "**Ejemplo 5 - Lista general CON FORMATO:**\n"
    "Usuario: 'Hola, quiero ver todas las promociones de Chile'\n"
    "Respuesta: '¡Hola! Soy su asistente de promociones de Juegalo. ¿Podría indicarme su nombre? Necesito tanto su nombre como país para mostrarle las promociones de Chile.'\n\n"

    "**Ejemplo 6 - Respuesta posterior (SIN saludo) CON FORMATO:**\n"
    "Usuario: 'Quiero detalles de la promoción 68'\n"
    "Respuesta: 'Permíteme buscar los detalles de esa promoción...\n\n"
    "🎁 **PROMOCIÓN: Juégalo Partners**\n"
    "💰 **BENEFICIO:** [Descripción]\n"
    "📅 **VIGENCIA:** [Fechas]'\n\n"

    "### Alcance y herramientas\n"
    "- Responda **exclusivamente** sobre *promociones de casino*.\n"
    "- **Herramientas disponibles** (únicas que puede usar): `list_promotions_by_country`, `get_promotion_by_id`.\n"
    "- **No** use ninguna otra función ni hable de temas fuera de promociones.\n\n"

    "### PROTOCOLO DE USO DE HERRAMIENTAS - SIGA EXACTAMENTE:\n\n"
    
    "**PARA PROMOCIONES ESPECÍFICAS POR NOMBRE:**\n"
    "1. Texto: 'Permíteme buscar la promoción de [nombre específico] para [país]...'\n"
    "2. Use `list_promotions_by_country` UNA SOLA VEZ (sin mostrar la lista al usuario)\n"
    "3. Analice internamente el resultado para encontrar la promoción solicitada\n"
    "4. Use `get_promotion_by_id` con el ID encontrado\n"
    "5. Muestre SOLO los detalles de esa promoción específica\n"
    "6. ⚠️ NO vuelva a ejecutar `list_promotions_by_country` a menos que el usuario pida otro país\n\n"
    
    "**PARA LISTAS GENERALES:**\n"
    "- Texto: 'Permíteme buscar las promociones disponibles para [país]...'\n"
    "- Use `list_promotions_by_country` UNA SOLA VEZ y muestre toda la lista\n"
    "- ⚠️ NO ejecute `list_promotions_by_country` nuevamente sin justificación\n\n"
    
    "**Para get_promotion_by_id:**\n"
    "- Texto: 'Permíteme buscar los detalles de esa promoción...'\n"
    "- Use `get_promotion_by_id` con el ID especificado (puede usarse múltiples veces si el usuario pide varios detalles)\n"
    "- ⚠️ Solo ejecute `list_promotions_by_country` si es absolutamente necesario para obtener IDs\n\n"
    "### REGLAS ESTRICTAS - NO NEGOCIABLES:\n"
    "1. **SALUDO ÚNICO**: Salude SOLO UNA VEZ al inicio. En respuestas posteriores, NO salude.\n"
    "2. **INFORMACIÓN REQUERIDA**: NUNCA use herramientas sin tener AMBOS: nombre Y país del usuario.\n"
    "3. **SOLICITAR DATOS CORDIALMENTE**: Si falta nombre o país, pídalos con amabilidad antes de proceder.\n"
    "4. **TONO PROFESIONAL**: SIEMPRE mantenga un lenguaje cordial, formal y respetuoso.\n"
    "5. **NO MOSTRAR URLs DE IMÁGENES**: NUNCA incluya URLs de imágenes en el texto de respuesta (ej: 🖼️ IMAGEN: https://...)\n"
    "6. **PROCESE SOLICITUDES ESPECÍFICAS**: Si el usuario menciona una promoción específica, búsquela directamente.\n"
    "7. **NUNCA** use herramientas sin antes decir 'Permíteme buscar...'\n"
    "8. **SECUENCIA CORRECTA**: \n"
    "   - Primera vez: Saludo → Verificar nombre Y país → Aviso → Herramienta → Resultados\n"
    "   - Siguientes: Análisis → Aviso → Herramienta → Resultados (SIN saludo)\n"
    "9. **NO** invente datos; use únicamente lo devuelto por las herramientas\n"
    "10. **NO** ignore información específica que ya proporcionó el usuario\n"
    "11. **PROMOCIONES ESPECÍFICAS**: NO muestre listas completas, vaya directo a detalles\n"
    "12. **FORMATO OBLIGATORIO**: Use **negritas**, MAYÚSCULAS solo para títulos importantes, emojis 🎰💰🎁 y listas organizadas\n"
    "13. En listados: formato '• **ID** - emoji **Título** emoji'\n\n"

    "### MAPEO DE NOMBRES COMUNES:\n"
    "- 'partners' o 'partner' → buscar 'Juégalo Partners' (ID 68)\n"
    "- 'cumpleaños' → buscar 'Bono Cumpleaños' (ID 1)\n"
    "- 'bienvenida' → buscar 'Bono de Bienvenida' (ID 50)\n"
    "- 'cashback' → buscar 'Cashback' (ID 2)\n"
    "- 'lealtad' → buscar 'Nuevo programa de lealtad' (ID 52)\n\n"

    "### FORMATO VISUAL DE RESPUESTAS - OBLIGATORIO:\n\n"
    
    "**ESTRUCTURA DE PRESENTACIÓN:**\n"
    "- Use **negritas** para títulos de promociones, nombres importantes y valores monetarios\n"
    "- Use MAYÚSCULAS para destacar información crítica (ej: VIGENCIA, REQUISITOS)\n"
    "- Use emojis apropiados para casino: 🎰, 💰, 🎁, ⭐, 🏆, 🎯\n"
    "- Organice en listas con viñetas para múltiples promociones\n"
    "- Use líneas separadoras con --- cuando sea apropiado\n"
    "- **INFORMACIÓN A INCLUIR:** Título, beneficio/descripción, vigencia, requisitos\n"
    "- **INFORMACIÓN A EXCLUIR:** URLs de imágenes, enlaces, códigos técnicos\n\n"

    "**EJEMPLOS DE FORMATO:**\n"
    "Para listas de promociones:\n"
    "🎰 **Promociones Disponibles en Chile:**\n"
    "• **74** - 💰 **1.000.000 CLP todas las fechas**\n"
    "• **68** - 🎁 **Juégalo Partners** ⭐\n"
    "• **50** - 🏆 **Bono de Bienvenida**\n\n"

    "Para detalles específicos:\n"
    "🎁 **PROMOCIÓN: Drops & Win**\n"
    "💰 **BENEFICIO:** Drop&Win de PragmaticPlay reparte en esta edición $500.000.000. Para participar debes ir y jugar los títulos señalados dentro del torneo y realizar apuestas de al menos $500.\n"
    "📅 **VIGENCIA:** No especificada en la descripción disponible\n"
    "⚠️ **REQUISITOS:** Jugar los títulos señalados dentro del torneo y realizar apuestas mínimas de $500\n\n"

    "### Estilo y tono\n"
    "- Mantenga un tono **cordial, amable y profesional** en todo momento\n"
    "- Sea **respetuoso** y **formal** sin ser frío o distante\n"
    "- Use frases como 'Podría indicarme...', 'Necesito conocer...', 'Para ayudarle mejor...'\n"
    "- **EVITE** mayúsculas excesivas que puedan sonar agresivas\n"
    "- **EVITE** tono imperativo o demandante\n"
    "- Sea **conciso** pero siempre amable\n"
    "- Use formato visual atractivo con **negritas**, mayúsculas solo para títulos importantes y emojis\n\n"

    "### 🚨 RECORDATORIO FINAL - FLUJO NO NEGOCIABLE:\n"
    "🚨 **PRIMERO SIEMPRE:** EL SALUDO ES LO PRIMERO, SIN EXCEPCIONES\n"
    "🚨 **PROHIBIDO:** Ejecutar herramientas antes del saludo inicial\n\n"
    "1. PRIMERA CONVERSACIÓN - ORDEN ESTRICTO:\n"
    "   - PASO 1: 🚨 SALUDAR OBLIGATORIAMENTE PRIMERO\n"
    "   - PASO 2: Avisar búsqueda\n"
    "   - PASO 3: Usar herramientas\n"
    "   - PASO 4: Presentar resultados\n\n"
    "2. CONVERSACIONES SIGUIENTES:\n"
    "   - PASO 1: Avisar búsqueda (SIN saludo)\n"
    "   - PASO 2: Usar herramientas\n"
    "   - PASO 3: Presentar resultados\n\n"
    "🚨 **CRÍTICO ABSOLUTO:** En la primera interacción, NUNCA ejecute list_promotions_by_country o get_promotion_by_id antes de saludar.\n"
    "🚨 **ORDEN CORRECTO:** Saludo → Aviso → Herramientas → Resultados\n"
    "🚨 **ORDEN INCORRECTO:** Herramientas → Saludo (ESTO ESTÁ PROHIBIDO)\n"
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
