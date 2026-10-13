"""Configurazione del BFF, letta da variabili d'ambiente / `.env`.

Il codice non deve MAI sapere se gira in profilo cloud (Aura + Neon) o
locale (Neo4j Community + Postgres via `docker-compose.yml`): l'unica
differenza tra i due profili è il CONTENUTO del `.env` (vedi
`.env.example` per il profilo cloud e `.env.local.example` per quello
locale alla radice del repo). Nessun host è hardcoded qui, nessun
`if local/cloud` nel codice.

In Wave 0 tutte le variabili sono opzionali (default `None`): `/health`
deve rispondere 200 anche senza alcun database attivo. Le connessioni
reali a Neo4j/Postgres arrivano con l'Urban Knowledge Graph e il layer
transazionale nelle wave successive.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variabili d'ambiente condivise dai due profili (cloud/locale).

    Nessuna PII, nessuna credenziale hardcoded: tutto arriva dal `.env`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
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


@lru_cache
def get_settings() -> Settings:
    """Cache delle Settings per evitare di ri-leggere il `.env` a ogni richiesta."""
    return Settings()
