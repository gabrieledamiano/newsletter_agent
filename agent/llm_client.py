"""Astrazione sul modello: due backend intercambiabili via Protocol.

GeminiBackend — chiama l'API Gemini reale.
ScriptedBackend — simulatore deterministico per test e modalità offline.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEFAULT_MODEL = os.getenv("GEMINI_MODEL")


# ---------------------------------------------------------------------------
# Strutture dati normalizzate
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMTurn:
    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str | None = None
    history_steps: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Protocol — l'interfaccia che rende i backend intercambiabili
# ---------------------------------------------------------------------------

class LLMBackend(Protocol):
    def step(self, history: list[dict], tools: list[dict]) -> LLMTurn: ...
    def complete_text(self, prompt: str) -> str: ...
    
    
## AGGIUNTA ROSARIO 
# Possibile fix : la struct ToolCall sopra si aspetta come campo
# Arguments un dict[str, any]
# Gemma potrebbe invece generare un stringa
# Questa funzioen ci serve a forza il mapping e la usiamo ovunque ci sia il comando ToolCall
def _coerce_args(raw) -> dict:
    if isinstance(raw,str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return{}
    return raw or {}


# ---------------------------------------------------------------------------
# GeminiBackend — backend reale
# ---------------------------------------------------------------------------

class GeminiBackend:
    
    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        from google import genai
        
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        if not key:
            raise RuntimeError(
                "Nessuna API key trovata. Imposta GEMINI_API_KEY nel file .env"
            )
            
        self._client = genai.Client(api_key=key)
        self.model = model

    def step(self, history: list[dict], tools: list[dict]) -> LLMTurn:
        
        interaction = self._client.interactions.create(
            model=self.model, store=False, input=history, tools=tools,
        )
        
        history_steps = [step.model_dump() for step in interaction.steps]
        
        calls = [
            # ROSARIO: Usiamo la funzione Helper per forza i parametri in un dictionary
            ToolCall(id=step.id, name=step.name, arguments=_coerce_args(step.arguments))
            for step in interaction.steps
            if step.type == "function_call"
        ]
        
        return LLMTurn(
            tool_calls=calls,
            text=getattr(interaction, "output_text", None),
            history_steps=history_steps,
        )

    

    def complete_text(self, prompt: str) -> str:
        
        interaction = self._client.interactions.create(
            model=self.model, store=False,
            input=[{"type": "user_input",
                    "content": [{"type": "text", "text": prompt}]}],
        )
        
        return getattr(interaction, "output_text", "") or ""

# ---------------------------------------------------------------------------
# ScriptedBackend — simulatore deterministico
# ---------------------------------------------------------------------------

class ScriptedBackend:
    """Policy fissa che percorre la traiettoria attesa:
    search → (evaluate & pick 3) → fetch × 3 → decisione finale.

    NON è l'agente: esercita gli stessi percorsi di codice senza rete.
    """

    def __init__(self, max_search_retries: int = 1):
        self.max_search_retries = max_search_retries

    def step(self, history: list[dict], tools: list[dict]) -> LLMTurn:
        topic = _extract_topic(history)
        results = _collect_results(history)

        searches = [r for name, r in results if name == "search_web_articles"]
        fetches = [r for name, r in results if name == "fetch_article_content"]

        # Mossa 1: cerca
        if not searches:
            return _make_tool_call(
                "search_web_articles", {"query": topic, "max_results": 5}
            )

        last_search = searches[-1]

        # Se la ricerca ha fallito e possiamo ritentare, riformula
        if not last_search.get("found") and len(searches) <= self.max_search_retries:
            return _make_tool_call(
                "search_web_articles",
                {"query": f"novità {topic} 2026", "max_results": 5},
            )

        # Mossa 2-4: fetch dei primi 3 articoli rilevanti
        if last_search.get("found"):
            search_results = last_search.get("results", [])
            # Filtra articoli irrilevanti (euristica: scarta se nessuna parola
            # del topic compare nel titolo o snippet)
            topic_words = set(topic.lower().split())
            relevant = [
                r for r in search_results
                if topic_words & set(
                    (r.get("title", "") + " " + r.get("snippet", "")).lower().split()
                )
            ]
            # Se il filtro è troppo aggressivo, allarga ai risultati grezzi
            # (il modello reale fa questo ragionamento in modo molto migliore)
            if len(relevant) < 3:
                relevant = search_results

            # Quanti ne abbiamo già fetchati?
            fetched_urls = {r.get("url") for _, r in results if _ == "fetch_article_content"}
            to_fetch = [r for r in relevant[:3] if r["url"] not in fetched_urls]

            if to_fetch:
                return _make_tool_call(
                    "fetch_article_content", {"url": to_fetch[0]["url"]}
                )

        # Mossa finale: produci la decisione
        return _make_final_decision(topic, searches, fetches, results)

    def complete_text(self, prompt: str) -> str:
        # Non usato dal loop, solo placeholder
        return "{}"


def _extract_topic(history: list[dict]) -> str:
    """Estrae il topic dall'ultimo step user_input."""
    for step in reversed(history):
        if step.get("type") == "user_input":
            texts = [
                part["text"]
                for part in step.get("content", [])
                if part.get("type") == "text"
            ]
            if texts:
                text = texts[-1] if len(texts) > 1 else texts[0]
                match = re.search(r"ARGOMENTO:\s*(.+)", text)
                if match:
                    return match.group(1).strip()
    return "argomento generico"


def _collect_results(history: list[dict]) -> list[tuple[str, dict]]:
    """Raccoglie tutti i risultati di tool dalla history."""
    out = []
    for step in history:
        if step.get("type") == "function_result":
            name = step.get("name", "")
            text = ""
            for part in step.get("result", []):
                if part.get("type") == "text":
                    text = part["text"]
                    break
            try:
                out.append((name, json.loads(text)))
            except (json.JSONDecodeError, TypeError):
                out.append((name, {}))
    return out


def _make_tool_call(name: str, arguments: dict) -> LLMTurn:
    call_id = f"call_{name}_{len(arguments)}"
    return LLMTurn(
        tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)],
        history_steps=[{
            "type": "function_call",
            "id": call_id,
            "name": name,
            "arguments": arguments,
        }],
    )


def _make_final_decision(
    topic: str,
    searches: list[dict],
    fetches: list[tuple],  # non usato direttamente, i dati sono in results
    results: list[tuple[str, dict]],
) -> LLMTurn:
    """Costruisce la decisione finale dal materiale raccolto."""
    articles = []
    fetch_results = [r for name, r in results if name == "fetch_article_content"]

    for fr in fetch_results:
        if fr.get("success"):
            content = fr.get("content", "")
            # Riassunto simulato: prime 2 frasi
            sentences = [s.strip() for s in content.split(".") if s.strip()]
            summary = ". ".join(sentences[:3]) + "." if sentences else "Contenuto non disponibile."
            articles.append({
                "title": fr.get("title", ""),
                "url": fr.get("url", ""),
                "source": "",
                "summary": summary,
                "relevance_reason": f"Articolo pertinente al tema '{topic}'",
                "published_date": None,
            })

    queries_used = []
    for name, r in results:
        if name == "search_web_articles":
            queries_used.append(topic)

    decision = {
        "newsletter_title": f"Newsletter settimanale: {topic}",
        "newsletter_intro": (
            f"Questa settimana abbiamo selezionato {len(articles)} articoli "
            f"sul tema '{topic}', analizzando le novità più rilevanti."
        ),
        "articles": articles,
        "topic": topic,
        "search_queries_used": queries_used or [topic],
        "articles_evaluated": sum(
            r.get("results_count", 0)
            for name, r in results if name == "search_web_articles"
        ),
        "articles_fetched": len(fetch_results),
    }

    text = json.dumps(decision, ensure_ascii=False)
    return LLMTurn(
        text=text,
        history_steps=[{
            "type": "model_output",
            "content": [{"type": "text", "text": text}],
        }],
    )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_backend(
    *, offline: bool = False, model: str = DEFAULT_MODEL
) -> LLMBackend:
    if offline:
        # Scripted Backend sarebbe il modello simulato in offline
        return ScriptedBackend()
    
    #A noi interessa usare questo, ovvero il modello tramite api-key
    return GeminiBackend(model=model)
