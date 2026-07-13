"""Lucca Soul Lab — BFF (Backend For Frontend).

Wave 0: solo fondamenta. Unico ingresso per l'app Flutter — gli endpoint
applicativi del contratto (`/session/onboarding`, `/itinerary`,
`/itinerary/adapt`, `/events`, `/dashboard/flows`) arrivano nelle wave
successive del BUILD_PLAN e riusano SEMPRE gli schemi di `packages/contracts`.

`/health` non richiede alcun database attivo: in Wave 0 il BFF non si
connette ancora a Neo4j o Postgres.
"""

from __future__ import annotations

import contracts
from contracts import VisitorContext
from fastapi import FastAPI
from pydantic import BaseModel

from api import __version__
from api.settings import get_settings

app = FastAPI(title="Lucca Soul — BFF")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ContractsVersionResponse(BaseModel):
    """Conferma che il BFF importa gli schemi da `packages/contracts`
    (single source of truth) invece di ridefinirli localmente.
    `VisitorContext` è importato esplicitamente come esempio: sarà lo
    schema di richiesta di `POST /session/onboarding` nella Wave 1."""

    package: str
    types: list[str]
    example_type: str = VisitorContext.__name__


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="lucca-soul-bff",
        version=__version__,
    )


@app.get("/contracts/version", response_model=ContractsVersionResponse)
def contracts_version() -> ContractsVersionResponse:
    return ContractsVersionResponse(
        package=contracts.__name__,
        types=sorted(contracts.__all__),
    )


# Impronta esplicita: le Settings vengono lette a import-time per fallire
# in modo leggibile se la configurazione è malformata, ma nessuna variabile
# è obbligatoria in Wave 0 (vedi api/settings.py).
get_settings()
