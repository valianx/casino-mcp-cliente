from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Promotion:
    id: int
    country: str
    title: str
    slug: str
    startDate: str
    endDate: Optional[str]
    description: str


MOCK_PROMOTIONS: List[Promotion] = [
    Promotion(
        id=101,
        country="CL",
        title="Bono de Bienvenida 100%",
        slug="bienvenida-100",
        startDate="2025-01-01",
        endDate="2025-12-31",
        description="Duplica tu primer depósito hasta $100.000 CLP.",
    ),
    Promotion(
        id=123,
        country="AR",
        title="Giros Gratis Semanales",
        slug="giros-semanales",
        startDate="2025-03-01",
        endDate=None,
        description="Recibe 20 giros gratis cada semana en slots seleccionados.",
    ),
    Promotion(
        id=124,
        country="CL",
        title="Cashback 10% Fin de Semana",
        slug="cashback-10-fin-semana",
        startDate="2025-06-01",
        endDate=None,
        description="Recupera el 10% de tus pérdidas netas los sábados y domingos.",
    ),
]
