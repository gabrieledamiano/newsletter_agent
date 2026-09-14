"""Tool 2 — Recupera e estrae il contenuto testuale di un articolo da un URL.

Backend live: requests + trafilatura (stato dell'arte per l'estrazione di articoli).
Backend offline: dataset JSON in data/mock_articles.json.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

MOCK_PATH = Path(__file__).resolve().parents[2] / "data" / "mock_articles.json"
TIMEOUT_S = 10
MAX_CONTENT_CHARS = 1500  # Tronca articoli troppo lunghi per il contesto LLM


# ---------------------------------------------------------------------------
# Dichiarazione mostrata al modello
# ---------------------------------------------------------------------------

TOOL_DECLARATION = {
    "type": "function",
    "name": "fetch_article_content",
    "description": (
        "Recupera il contenuto testuale completo di un articolo dato il suo URL. "
        "Usare SOLO su URL ottenuti da search_web_articles, mai su URL inventati. "
        "Restituisce titolo, testo dell'articolo e conteggio parole."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL completo dell'articolo da recuperare.",
            },
        },
        "required": ["url"],
    },
}


# ---------------------------------------------------------------------------
# Punto di ingresso
# ---------------------------------------------------------------------------

def fetch_article_content(
    url: str,
    *,
    offline: bool = False,
) -> dict:
    """Pre: url non vuoto. Post: dict con chiave 'success' sempre presente."""
    if offline:
        return _fetch_mock(url)

    try:
        return _fetch_live(url)
    except Exception as exc:
        fallback = _fetch_mock(url)
        if fallback["success"]:
            fallback["degraded_from_live"] = type(exc).__name__
            return fallback
        return {
            "success": False,
            "reason": f"fetch_failed: {type(exc).__name__}: {exc}",
            "url": url,
        }


# ---------------------------------------------------------------------------
# Backend live — requests + trafilatura
# ---------------------------------------------------------------------------

def _fetch_live(url: str) -> dict:
    import requests
    import trafilatura

    response = requests.get(url, timeout=TIMEOUT_S, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    })
    response.raise_for_status()

    extracted = trafilatura.extract(
        response.text,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )

    if not extracted:
        return {
            "success": False,
            "reason": "no_extractable_content",
            "url": url,
        }

    # Tronca se troppo lungo
    content = extracted[:MAX_CONTENT_CHARS]
    if len(extracted) > MAX_CONTENT_CHARS:
        content += "\n[... contenuto troncato ...]"

    return {
        "success": True,
        "title": _extract_title(response.text) or url,
        "content": content,
        "word_count": len(content.split()),
        "language": _guess_language(content),
        "url": url,
    }


def _extract_title(html: str) -> str | None:
    """Estrae il tag <title> con parsing minimale."""
    import re
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


def _guess_language(text: str) -> str:
    """Euristica minimale sulla lingua — non serve precisione."""
    italian_markers = {"della", "nella", "sono", "questo", "anche", "degli", "delle"}
    words = set(text.lower().split()[:100])
    return "it" if len(words & italian_markers) >= 2 else "en"


# ---------------------------------------------------------------------------
# Backend offline — mock JSON
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_mock() -> dict:
    with MOCK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)["articles"]


def _fetch_mock(url: str) -> dict:
    articles = _load_mock()
    if url in articles:
        article = articles[url]
        return {
            "success": True,
            "title": article["title"],
            "content": article["content"],
            "word_count": article["word_count"],
            "language": article.get("language", "it"),
            "url": url,
        }
    return {
        "success": False,
        "reason": "url_not_in_mock_dataset",
        "url": url,
    }
