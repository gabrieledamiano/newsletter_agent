"""Tool 1 — Cerca articoli recenti sul web.

Backend live: duckduckgo-search (nessuna API key aggiuntiva).
Backend offline: dataset JSON in data/mock_search_results.json.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from functools import lru_cache

MOCK_PATH = Path(__file__).resolve().parents[2] / "data" / "mock_search_results.json"


#ROSARIO: Aggiunto controllo d'isteresi sulle chiamate successive
#Evitiamo che chiamate frequenti vengano bloccate dal server duckduckgosearch
# AI CAPITO COMO FUNZIONEEEEEE

#Intervallo di tempo tra le due chiamate successive
min_intervallo_seconds= 0.3

#Variabile di stato per tenere conto di quando è avvenuta
#la precedente chiamata
_call_precedente_ts = 0.0 

# AGGIORNATO PACCHETTO
from ddgs import DDGS
import time

def _Isteresi() -> None:
    """Garantisce almeno un intervallo tra due chiamate consecutive al server DDGS."""
    
    global _call_precedente_ts
    
    elapsed = time.monotonic() - _call_precedente_ts
    
    wait = min_intervallo_seconds - elapsed
    
    if wait > 0:
        # se non è ancora passato l'intervallo
        time.sleep(wait)
        
    # Se è passato resettiamo, impostando il nuovo valore di _call_precedente
    _call_precedente_ts = time.monotonic()



# ---------------------------------------------------------------------------
# Dichiarazione mostrata al modello
# ---------------------------------------------------------------------------

TOOL_DECLARATION = {
    "type": "function",
    "name": "search_web_articles",
    "description": (
        "Cerca articoli recenti sul web relativi a un argomento. "
        "Restituisce titolo, URL, snippet e fonte dei risultati trovati. "
        "Chiamare con una query specifica e in lingua appropriata al tema. "
        "Se i risultati non sono pertinenti, riformulare la query e ritentare UNA SOLA volta."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Query di ricerca. Usare parole chiave specifiche, non frasi generiche.",
            },
            "max_results": {
                "type": "integer",
                "description": "Numero massimo di risultati (default 5, max 10).",
            },
        },
        "required": ["query"],
    },
}


# ---------------------------------------------------------------------------
# Punto di ingresso
# ---------------------------------------------------------------------------

# def search_web_articles(
#     query: str,
#     max_results: int = 5,
#     *,
#     offline: bool = False,
# ) -> dict:
#     """Pre: query non vuota. Post: dict con chiave 'results' sempre presente."""
#     max_results = min(max(max_results, 1), 10)

#     if offline:
#         return _search_mock(query, max_results)

#     try:
#         return _search_live(query, max_results)
#     except Exception as exc:
#         fallback = _search_mock(query, max_results)
#         fallback["degraded_from_live"] = type(exc).__name__
#         return fallback

def search_web_articles(
    query: str,
    max_results: int = 5,
    *,
    offline: bool = False,
) -> dict:
    """Pre: query non vuota. Post: dict con chiave 'results' sempre presente."""
    max_results = min(max(max_results, 1), 10)

    # Se l'utente ha spuntato la casella "Modalità Offline" nella UI
    if offline:
        return _search_mock(query, max_results)

    # Modalità Live
    try:
        return _search_live(query, max_results)
    except Exception as exc:
        # Invece di usare il mock, diciamo apertamente all'agente che c'è un errore
        return {
            "found": False,
            "results": [],
            "results_count": 0,
            "error_message": f"Errore API DuckDuckGo ({type(exc).__name__}): Riprovare più tardi o cambiare tool.",
            "source": "live_error"
        }



# ---------------------------------------------------------------------------
# Backend live — DuckDuckGo
# ---------------------------------------------------------------------------

# def _search_live(query: str, max_results: int) -> dict:
#     from duckduckgo_search import DDGS

#     with DDGS() as ddgs:
#         raw = list(ddgs.text(query, max_results=max_results))

#     if not raw:
#         return {"found": False, "results": [], "results_count": 0, "source": "duckduckgo"}

#     results = []
#     for item in raw:
#         results.append({
#             "title": item.get("title", ""),
#             "url": item.get("href", ""),
#             "snippet": item.get("body", ""),
#             "source": _extract_domain(item.get("href", "")),
#             "published_date": None,
#         })

#     return {
#         "found": True,
#         "results": results,
#         "results_count": len(results),
#         "source": "duckduckgo",
#     }

# ---------------------------------------------------------------------------
# Backend live — DuckDuckGo (con isteresi/cache e debug)
# ---------------------------------------------------------------------------

def _search_live(query: str, max_results: int) -> dict:
    from ddgs import DDGS

    clean_query = query.strip().lower()
    print(f"[DEBUG search_web] 🌐 Esecuzione chiamata LIVE su DuckDuckGo per la query: '{clean_query}'")

    try:
        _Isteresi()

        print(f"[DEBUG search_web] ➡️  INPUT → query={clean_query!r} max_results={max_results!r} "
              f"(tipi: {type(clean_query).__name__}, {type(max_results).__name__})")

        with DDGS() as ddgs:
            raw = list(ddgs.text(clean_query, max_results=max_results))

    except Exception as e:
        print(f"[DEBUG search_web] ⚠️ Eccezione di rete catturata: {type(e).__name__}: {e}")
        raise e

    print(f"[DEBUG search_web] ⬅️  RAW → {len(raw)} elementi, tipo: {type(raw).__name__}")

    if not raw:
        print("[DEBUG search_web] ⚠️  Lista vuota — possibile rate limit o query senza match")
        return {"found": False, "results": [], "results_count": 0, "source": "duckduckgo"}

    print(f"[DEBUG search_web] 🔑 CHIAVI primo elemento: {list(raw[0].keys())}")
    for i, item in enumerate(raw):
        print(f"[DEBUG search_web]   [{i}] {str(item)[:200]}")

    print(f"[DEBUG search_web] ✅ Trovati {len(raw)} risultati per '{clean_query}'")

    results = []
    for item in raw:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("href", ""),
            "snippet": item.get("body", ""),
            "source": _extract_domain(item.get("href", "")),
            "published_date": None,
        })

    return {
        "found": True,
        "results": results,
        "results_count": len(results),
        "source": "duckduckgo",
    }


def _extract_domain(url: str) -> str:
    """https://www.example.com/path → example.com"""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        return host.removeprefix("www.")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Backend offline — mock JSON
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_mock() -> dict:
    with MOCK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)["queries"]


def _search_mock(query: str, max_results: int) -> dict:
    queries = _load_mock()

    # Match esatto sulla query
    if query in queries:
        results = queries[query][:max_results]
        return {
            "found": bool(results),
            "results": results,
            "results_count": len(results),
            "source": "mock",
        }

    # Match parziale: cerca la query mock che ha più parole in comune
    query_words = set(query.lower().split())
    best_key, best_overlap = None, 0
    for key in queries:
        overlap = len(query_words & set(key.lower().split()))
        if overlap > best_overlap:
            best_key, best_overlap = key, overlap

    if best_key and best_overlap > 0:
        results = queries[best_key][:max_results]
        return {
            "found": bool(results),
            "results": results,
            "results_count": len(results),
            "source": "mock",
        }

    return {"found": False, "results": [], "results_count": 0, "source": "mock"}
