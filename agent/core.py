"""Il reasoning loop del Newsletter Agent.

Unico punto di contatto tra il modello e i tool.
Non importa Gemini, non importa i singoli tool.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Callable

from pydantic import ValidationError

from agent.llm_client import LLMTurn, ToolCall
from agent.prompts import AGENT_SYSTEM_PROMPT, TOPIC_TEMPLATE
from agent.schemas import AgentDecision, NewsletterOutput
from agent.tools.registry import TOOL_DECLARATIONS, execute_tool


MAX_ITERATIONS = 10  # budget più alto del Librarian: qui servono ~5 tool call minime


# ---------------------------------------------------------------------------
# Strutture di trace
# ---------------------------------------------------------------------------

@dataclass
class TraceEvent:
    iteration: int
    kind: str  # "tool_call" | "final" | "error"
    name: str = ""
    arguments: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)
    summary: str = ""


# ---------------------------------------------------------------------------
# Il loop principale
# ---------------------------------------------------------------------------

def process_topic(
    backend,
    topic: str,
    *,
    offline: bool = False,
    max_iterations: int = MAX_ITERATIONS,
    on_event: Callable[[TraceEvent], None] | None = None,
) -> NewsletterOutput:
    """Esegue il reasoning loop su un singolo topic.

    Post: restituisce SEMPRE un NewsletterOutput, anche in caso di errore totale.
    """
    t0 = time.time()
    trace: list[TraceEvent] = []
    tool_calls_count = 0

    # Separazione istruzioni / dati in due step distinti
    # (lezione dal bug 19.3 del Librarian)
    topic_payload = TOPIC_TEMPLATE.replace("{topic}", topic)

    history: list[dict] = [
        {"type": "user_input",
         "content": [{"type": "text", "text": AGENT_SYSTEM_PROMPT}]},
        {"type": "user_input",
         "content": [{"type": "text", "text": topic_payload}]},
    ]

    decision: AgentDecision | None = None

    for iteration in range(1, max_iterations + 1):
        
        # TIMER DEBUG DELL'ITERAZIONE COMPLETA        
        t_step = time.time()

        try:
            turn = backend.step(history, TOOL_DECLARATIONS)
        except Exception as exc:
            evt = TraceEvent(
                iteration=iteration, kind="error",
                summary=f"Errore backend: {type(exc).__name__}: {exc}",
            )
            trace.append(evt)
            if on_event:
                on_event(evt)
            break

        print(f"[TIMING] iter {iteration} — backend.step: {time.time() - t_step:.1f}s")
        
        history.extend(turn.history_steps)

        if turn.tool_calls:
            for call in turn.tool_calls:
                
                #TIMER DEBUG DELLA CHIAMATA DEL TOOL
                t_tool = time.time()
                result = execute_tool(call.name, call.arguments, offline=offline)
                print(f"[TIMING] {call.name}: {time.time() - t_tool:.1f}s")
                
                tool_calls_count += 1

                summary = _summarize_result(call.name, result)
                evt = TraceEvent(
                    iteration=iteration, kind="tool_call",
                    name=call.name, arguments=call.arguments,
                    result=result, summary=summary,
                )
                trace.append(evt)
                if on_event:
                    on_event(evt)

                history.append(_function_result_step(call, result))
            continue

        # Nessun tool call → il modello ha finito, parse della decisione
        decision = _parse_decision(turn.text)
        evt = TraceEvent(
            iteration=iteration, kind="final",
            summary=f"Decisione: {len(decision.articles) if decision else 0} articoli",
        )
        trace.append(evt)
        if on_event:
            on_event(evt)
        break

    elapsed = round(time.time() - t0, 2)

    if decision is None:
        decision = AgentDecision(
            newsletter_title=f"Newsletter: {topic} [ERRORE]",
            newsletter_intro="L'agente non ha prodotto un output valido.",
            topic=topic,
        )

    return NewsletterOutput(
        decision=decision,
        tool_calls_count=tool_calls_count,
        elapsed_s=elapsed,
        raw_topic=topic,
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _function_result_step(call: ToolCall, result: dict) -> dict:
    return {
        "type": "function_result",
        "name": call.name,
        "call_id": call.id,
        "result": [{"type": "text",
                     "text": json.dumps(result, ensure_ascii=False)}],
    }


def _summarize_result(name: str, result: dict) -> str:
    """Riassunto leggibile di un risultato di tool, per il trace."""
    if name == "search_web_articles":
        count = result.get("results_count", 0)
        found = result.get("found", False)
        return f"{'Trovati' if found else 'Nessun risultato'} — {count} risultati"
    if name == "fetch_article_content":
        if result.get("success"):
            title = result.get("title", "?")
            wc = result.get("word_count", 0)
            return f"Recuperato: {title} ({wc} parole)"
        return f"Fetch fallito: {result.get('reason', '?')}"
    return str(result)[:100]


def _parse_decision(text: str | None) -> AgentDecision | None:
    """Parsing difensivo dell'output JSON del modello."""
    if not text:
        return None
    cleaned = _strip_json_fences(text)
    try:
        payload = json.loads(cleaned)
        return AgentDecision(**payload)
    except (json.JSONDecodeError, TypeError, ValidationError):
        return None


def _strip_json_fences(text: str) -> str:
    """Rimuove i delimitatori Markdown e isola il primo oggetto JSON bilanciato."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start = cleaned.find("{")
    if start == -1:
        return cleaned
    depth = 0
    for idx in range(start, len(cleaned)):
        if cleaned[idx] == "{":
            depth += 1
        elif cleaned[idx] == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : idx + 1]
    return cleaned[start:]
