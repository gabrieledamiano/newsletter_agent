"""Produzione degli artefatti: newsletter Markdown, HTML e trace JSON.

Codice interamente deterministico, fuori dal loop dell'agente.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from agent.schemas import NewsletterOutput


# ---------------------------------------------------------------------------
# Newsletter Markdown
# ---------------------------------------------------------------------------

def render_markdown(output: NewsletterOutput) -> str:
    d = output.decision
    lines = [
        f"# {d.newsletter_title}",
        "",
        f"*Generata automaticamente il {date.today().isoformat()}*",
        "",
        d.newsletter_intro,
        "",
        "---",
        "",
    ]

    for i, article in enumerate(d.articles, 1):
        lines.append(f"## {i}. {article.title}")
        lines.append("")
        if article.source:
            lines.append(f"**Fonte:** {article.source}")
        if article.published_date:
            lines.append(f"**Data:** {article.published_date}")
        lines.append(f"**Link:** [{article.url}]({article.url})")
        lines.append("")
        lines.append(article.summary)
        lines.append("")
        lines.append("---")
        lines.append("")

    # Footer
    lines.append(f"*Newsletter generata dall'agente autonomo "
                 f"— {d.articles_fetched} articoli analizzati su "
                 f"{d.articles_evaluated} risultati di ricerca.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Newsletter HTML
# ---------------------------------------------------------------------------

def render_html(output: NewsletterOutput) -> str:
    d = output.decision
    articles_html = ""
    for i, article in enumerate(d.articles, 1):
        meta_parts = []
        if article.source:
            meta_parts.append(f"Fonte: {_esc(article.source)}")
        if article.published_date:
            meta_parts.append(f"Data: {article.published_date}")
        meta = " &middot; ".join(meta_parts)

        articles_html += f"""
        <div class="article">
            <h2>{i}. {_esc(article.title)}</h2>
            <p class="meta">{meta}</p>
            <p>{_esc(article.summary)}</p>
            <a href="{_esc(article.url)}" class="read-more">Leggi l'articolo completo →</a>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(d.newsletter_title)}</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 700px; margin: 2em auto;
         padding: 0 1em; color: #333; line-height: 1.6; }}
  h1 {{ color: #1a1a2e; border-bottom: 3px solid #e94560; padding-bottom: 0.3em; }}
  h2 {{ color: #16213e; margin-top: 1.5em; }}
  .meta {{ color: #666; font-size: 0.9em; }}
  .article {{ margin-bottom: 2em; padding-bottom: 1.5em;
              border-bottom: 1px solid #eee; }}
  .read-more {{ color: #e94560; text-decoration: none; font-weight: bold; }}
  .read-more:hover {{ text-decoration: underline; }}
  .intro {{ font-size: 1.1em; color: #444; }}
  .footer {{ margin-top: 2em; padding-top: 1em; border-top: 2px solid #eee;
             color: #888; font-size: 0.85em; }}
  .date {{ color: #888; font-size: 0.9em; }}
</style>
</head>
<body>
  <h1>{_esc(d.newsletter_title)}</h1>
  <p class="date">{date.today().isoformat()}</p>
  <p class="intro">{_esc(d.newsletter_intro)}</p>
  {articles_html}
  <div class="footer">
    <p>Newsletter generata dall'agente autonomo &mdash;
       {d.articles_fetched} articoli analizzati su
       {d.articles_evaluated} risultati di ricerca.</p>
  </div>
</body>
</html>"""


def _esc(text: str) -> str:
    """Escape HTML minimale."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# Trace JSON
# ---------------------------------------------------------------------------

def build_trace(output: NewsletterOutput, trace_events: list) -> dict:
    return {
        "topic": output.raw_topic,
        "elapsed_s": output.elapsed_s,
        "tool_calls_count": output.tool_calls_count,
        "articles_included": len(output.decision.articles),
        "trace": [
            {
                "iteration": e.iteration,
                "kind": e.kind,
                "tool": e.name,
                "arguments": e.arguments,
                "summary": e.summary,
            }
            for e in trace_events
        ],
    }


# ---------------------------------------------------------------------------
# Metriche
# ---------------------------------------------------------------------------

def compute_metrics(output: NewsletterOutput) -> dict:
    d = output.decision
    return {
        "topic": d.topic,
        "articoli_inclusi": len(d.articles),
        "articoli_fetchati": d.articles_fetched,
        "risultati_valutati": d.articles_evaluated,
        "query_usate": len(d.search_queries_used),
        "tool_call_totali": output.tool_calls_count,
        "tempo_totale_s": output.elapsed_s,
        "tempo_manuale_stimato_min": 15,  # stima: 15 min per cercare e riassumere 3 articoli a mano
    }


# ---------------------------------------------------------------------------
# Scrittura su disco
# ---------------------------------------------------------------------------

def write_artifacts(
    output: NewsletterOutput, trace_events: list, output_dir: str = "output"
) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    paths = {}

    # Newsletter Markdown
    md_path = out / "newsletter.md"
    md_path.write_text(render_markdown(output), encoding="utf-8")
    paths["md"] = md_path

    # Newsletter HTML
    html_path = out / "newsletter.html"
    html_path.write_text(render_html(output), encoding="utf-8")
    paths["html"] = html_path

    # Trace JSON
    trace_path = out / "agent_trace.json"
    trace_data = build_trace(output, trace_events)
    trace_path.write_text(
        json.dumps(trace_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    paths["trace"] = trace_path

    # Decisione grezza
    decision_path = out / "agent_decision.json"
    decision_path.write_text(
        json.dumps(output.decision.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    paths["decision"] = decision_path

    return paths
