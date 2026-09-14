"""Dispatcher: lega il nome dichiarato al modello alla funzione Python reale."""

from __future__ import annotations

from typing import Callable

from agent.tools import search_web, fetch_article

TOOL_DECLARATIONS: list[dict] = [
    search_web.TOOL_DECLARATION,
    fetch_article.TOOL_DECLARATION,
]

_HANDLERS: dict[str, Callable[..., dict]] = {
    "search_web_articles": search_web.search_web_articles,
    "fetch_article_content": fetch_article.fetch_article_content,
}


def execute_tool(name: str, arguments: dict | None, *, offline: bool = False) -> dict:
    """Dispatch difensivo: tre livelli di protezione contro un modello che sbaglia."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"tool sconosciuto: {name}", "available": list(_HANDLERS)}

    kwargs = dict(arguments or {})

    # Il flag offline viene iniettato dal codice, non dal modello
    if name in ("search_web_articles", "fetch_article_content"):
        kwargs["offline"] = offline

    try:
        return handler(**kwargs)
    except TypeError as exc:
        return {"error": f"argomenti non validi per {name}: {exc}"}
    except Exception as exc:
        return {"error": f"errore interno in {name}: {type(exc).__name__}: {exc}"}
