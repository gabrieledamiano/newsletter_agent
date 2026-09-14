#!/usr/bin/env python3
"""Entrypoint da riga di comando per il Newsletter Agent."""

from __future__ import annotations

import argparse
from pathlib import Path

from agent.core import TraceEvent, process_topic
from agent.llm_client import DEFAULT_MODEL, build_backend
from agent.reporting import compute_metrics, write_artifacts


# ---------------------------------------------------------------------------
# Output colorato
# ---------------------------------------------------------------------------

COLORS = {
    "tool_call": "\033[36m",   # ciano
    "final": "\033[32m",       # verde
    "error": "\033[31m",       # rosso
    "reset": "\033[0m",
}


def _print_event(event: TraceEvent) -> None:
    c = COLORS.get(event.kind, "")
    r = COLORS["reset"]
    if event.kind == "tool_call":
        print(f"  {c}[iter {event.iteration}] "
              f"🔧 {event.name}({event.arguments}) → {event.summary}{r}")
    elif event.kind == "final":
        print(f"  {c}[iter {event.iteration}] ✅ {event.summary}{r}")
    elif event.kind == "error":
        print(f"  {c}[iter {event.iteration}] ❌ {event.summary}{r}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Newsletter Agent — genera newsletter settimanali")
    parser.add_argument("--topic", default=None, help="Argomento della newsletter")
    parser.add_argument("--input", default="data/sample_input.txt",
                        help="File con un topic per riga (usato se --topic non è specificato)")
    parser.add_argument("--output", default="output", help="Directory di output")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modello Gemini")
    parser.add_argument("--offline", action="store_true",
                        help="Usa il backend simulato, senza rete")
    args = parser.parse_args()

    # Determina il topic
    if args.topic:
        topic = args.topic
    else:
        topic = Path(args.input).read_text(encoding="utf-8").strip().splitlines()[0].strip()

    print(f"\n{'='*60}")
    print(f"  Newsletter Agent — topic: {topic}")
    print(f"  Modalità: {'offline (simulata)' if args.offline else 'online (Gemini)'}")
    print(f"{'='*60}\n")

    backend = build_backend(offline=args.offline, model=args.model)

    # Il trace viene raccolto sia dentro process_topic sia qui
    trace_events: list[TraceEvent] = []

    def collect_and_print(event: TraceEvent) -> None:
        trace_events.append(event)
        _print_event(event)

    output = process_topic(backend, topic, offline=args.offline, on_event=collect_and_print)

    # Scrittura artefatti
    paths = write_artifacts(output, trace_events, args.output)
    metrics = compute_metrics(output)

    print(f"\n{'─'*60}")
    print("  Metriche:")
    for k, v in metrics.items():
        print(f"    {k}: {v}")
    print(f"\n  Artefatti generati:")
    for name, path in paths.items():
        print(f"    {name}: {path}")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    main()
