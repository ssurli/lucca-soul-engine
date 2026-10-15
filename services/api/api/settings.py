"""Configurazione del BFF, letta da variabili d'ambiente / `.env`.

Il codice non deve MAI sapere dove gira: l'unica differenza tra ambienti è
il CONTENUTO del `.env` (vedi `.env.example` alla radice del repo). Nessun
host è hardcoded qui, nessun `if local/cloud` nel codice.

Il `.env` è ancorato alla RADICE DEL REPO (`ENV_FILE`), non al cwd: avviare
uvicorn da un'altra cartella dà la stessa configurazione. Le variabili
d'ambiente di processo hanno comunque la precedenza sul file.

In Wave 0 tutte le variabili sono opzionali (default `None`): `/health`
deve rispondere 200 anche senza alcun database attivo. Le connessioni
reali a Neo4j/Postgres arrivano con l'Urban Knowledge Graph e il layer
transazionale nelle wave successive.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Radice del repo (services/api/api/settings.py -> parents[3]); i pacchetti sono
# installati in editable, quindi `__file__` punta al sorgente nel repo.
RADICE_REPO = Path(__file__).resolve().parents[3]
ENV_FILE = RADICE_REPO / ".env"


class Settings(BaseSettings):
    """Variabili d'ambiente condivise dai due profili (cloud/locale).

    Nessuna PII, nessuna credenziale hardcoded: tutto arriva dal `.env`.
    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Urban Knowledge Graph (Neo4j: `neo4j+s://` su Aura, `bolt://` in locale)
    neo4j_uri: str | None = Field(default=None, alias="NEO4J_URI")
    neo4j_username: str | None = Field(default=None, alias="NEO4J_USERNAME")
    neo4j_password: str | None = Field(default=None, alias="NEO4J_PASSWORD")
    neo4j_database: str | None = Field(default=None, alias="NEO4J_DATABASE")

    # Transazionale + eventi + Urban Memory + vector store pgvector
    # (Neon con `sslmode=require` in cloud, Postgres locale via Docker)
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    # Fuso IANA della CITTA' (es. `Europe/Rome`): nessun default nel codice.
    # Serve a convertire le occorrenze UTC del ledger nella DATA LOCALE
    # (`EventoPromosso.ultima_occorrenza`). Assente/non valido => fail-closed.
    city_tz: str | None = Field(default=None, alias="CITY_TZ")

    # Slug del dataset della citta' (slug minuscolo): selezione tramite il
    # registro di `graph.registro`. Assente => dataset predefinito del
    # registro; slug invalido => ValueError leggibile (nessun degrado
    # silenzioso verso un'altra citta').
    city_seed: str | None = Field(default=None, alias="CITY_SEED")


@lru_cache
def get_settings() -> Settings:
    """Cache delle Settings per evitare di ri-leggere il `.env` a ogni richiesta.

    Legge `ENV_FILE` (radice del repo) al momento della chiamata: i test
    possono puntarlo altrove con `monkeypatch.setattr(api.settings, "ENV_FILE", ...)`.
    """
    return Settings(_env_file=ENV_FILE)
