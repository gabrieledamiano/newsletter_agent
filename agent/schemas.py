"""Contratto dati del Newsletter Agent.

Definisce le forme che i dati possono assumere lungo tutto il flusso:
SearchResult → ArticleContent → ArticleSummary → Newsletter.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Tipi
# ---------------------------------------------------------------------------

ArticleStatus = Literal[
    "INCLUDED",          # articolo rilevante, incluso nella newsletter
    "EXCLUDED_IRRELEVANT",  # trovato ma scartato perché fuori tema
    "EXCLUDED_DUPLICATE",   # duplicato di un articolo già selezionato
    "FETCH_FAILED",      # impossibile recuperare il contenuto
    "SEARCH_FAILED",     # la ricerca non ha prodotto risultati
]


# ---------------------------------------------------------------------------
# Modelli Pydantic
# ---------------------------------------------------------------------------

class SearchResult(BaseModel):
    """Un singolo risultato di ricerca, prima del fetch."""
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    published_date: str | None = None


class ArticleSummary(BaseModel):
    """Riassunto di un articolo prodotto dall'agente."""
    title: str
    url: str
    source: str = ""
    summary: str
    relevance_reason: str = ""
    published_date: str | None = None

    @field_validator("summary", mode="before")
    @classmethod
    def _clean_summary(cls, v: object) -> str:
        if not v or str(v).lower() in ("null", "none", "n/a"):
            return ""
        return str(v).strip()


class AgentDecision(BaseModel):
    """Output strutturato dell'agente alla fine del loop."""
    newsletter_title: str
    newsletter_intro: str = ""
    articles: list[ArticleSummary] = []
    topic: str = ""
    search_queries_used: list[str] = []
    articles_evaluated: int = 0
    articles_fetched: int = 0


class NewsletterOutput(BaseModel):
    """Record finale arricchito con metadati di processo."""
    decision: AgentDecision
    tool_calls_count: int = 0
    elapsed_s: float = 0.0
    raw_topic: str = ""
