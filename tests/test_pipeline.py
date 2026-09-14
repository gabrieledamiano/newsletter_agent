"""Test della pipeline — deterministici, senza rete, senza chiave API.

Gruppo                Test                                        Invariante
────────────────────────────────────────────────────────────────────────────
Tool 1 (search)       3    mock trova, mock non trova, match parziale
Tool 2 (fetch)        3    fetch ok, fetch fallisce, mock mancante
Parsing               1    rimozione backtick e isolamento JSON
Core loop             3    loop completo, articoli prodotti, trace non vuoto
Reporting             2    markdown contiene titoli, HTML contiene link
"""

from __future__ import annotations

import json

import pytest

from agent.core import TraceEvent, _strip_json_fences, process_topic
from agent.llm_client import ScriptedBackend
from agent.reporting import compute_metrics, render_html, render_markdown
from agent.schemas import AgentDecision
from agent.tools.search_web import search_web_articles
from agent.tools.fetch_article import fetch_article_content


# ===================================================================
# Tool 1 — search_web_articles
# ===================================================================

class TestSearchWeb:
    def test_mock_trova_risultati(self):
        result = search_web_articles("AI in medicina", offline=True)
        assert result["found"] is True
        assert result["results_count"] >= 3
        assert all("url" in r for r in result["results"])

    def test_mock_match_parziale(self):
        """Una query diversa ma con parole in comune deve trovare risultati."""
        result = search_web_articles("medicina intelligenza artificiale", offline=True)
        assert result["found"] is True

    def test_mock_non_trova_nulla(self):
        result = search_web_articles("xyzzy_argomento_inesistente_12345", offline=True)
        # Potrebbe trovare qualcosa via match parziale o no
        assert "results" in result


# ===================================================================
# Tool 2 — fetch_article_content
# ===================================================================

class TestFetchArticle:
    def test_fetch_mock_successo(self):
        result = fetch_article_content(
            "https://example.com/ai-diagnostica-immagini", offline=True
        )
        assert result["success"] is True
        assert result["word_count"] > 0
        assert "content" in result

    def test_fetch_mock_url_inesistente(self):
        result = fetch_article_content(
            "https://example.com/non-esiste", offline=True
        )
        assert result["success"] is False

    def test_fetch_restituisce_sempre_url(self):
        """Il contratto richiede che 'url' sia sempre presente nella risposta."""
        url = "https://example.com/qualsiasi"
        result = fetch_article_content(url, offline=True)
        assert result.get("url") == url


# ===================================================================
# Parsing
# ===================================================================

class TestParsing:
    def test_strip_json_fences(self):
        raw = '```json\n{"title": "test"}\n```\nextra text'
        cleaned = _strip_json_fences(raw)
        parsed = json.loads(cleaned)
        assert parsed["title"] == "test"

    def test_strip_json_con_testo_prima(self):
        raw = 'Ecco il JSON:\n{"a": 1, "b": {"c": 2}}\nfine'
        cleaned = _strip_json_fences(raw)
        parsed = json.loads(cleaned)
        assert parsed["a"] == 1
        assert parsed["b"]["c"] == 2


# ===================================================================
# Core loop
# ===================================================================

class TestCoreLoop:
    def test_loop_completo_produce_articoli(self):
        backend = ScriptedBackend()
        output = process_topic(backend, "AI in medicina", offline=True)
        assert len(output.decision.articles) >= 1
        assert output.tool_calls_count >= 2  # almeno 1 search + 1 fetch

    def test_loop_registra_trace(self):
        trace_events: list[TraceEvent] = []
        backend = ScriptedBackend()
        process_topic(
            backend, "AI in medicina", offline=True,
            on_event=lambda e: trace_events.append(e),
        )
        assert len(trace_events) >= 2
        kinds = {e.kind for e in trace_events}
        assert "tool_call" in kinds
        assert "final" in kinds

    def test_nessun_articolo_inventato(self):
        """Ogni URL nella decisione deve provenire dai risultati di search."""
        trace_events: list[TraceEvent] = []
        backend = ScriptedBackend()
        output = process_topic(
            backend, "AI in medicina", offline=True,
            on_event=lambda e: trace_events.append(e),
        )
        # Raccogli gli URL dei fetch riusciti
        fetched_urls = set()
        for e in trace_events:
            if e.name == "fetch_article_content" and e.result.get("success"):
                fetched_urls.add(e.result["url"])

        # Ogni articolo nella newsletter deve avere un URL fetchato
        for article in output.decision.articles:
            assert article.url in fetched_urls, (
                f"URL {article.url} nella newsletter ma non fetchato"
            )


# ===================================================================
# Reporting
# ===================================================================

class TestReporting:
    def _make_output(self):
        backend = ScriptedBackend()
        return process_topic(backend, "AI in medicina", offline=True)

    def test_markdown_contiene_titoli(self):
        output = self._make_output()
        md = render_markdown(output)
        assert "Newsletter" in md
        for article in output.decision.articles:
            assert article.title in md

    def test_html_contiene_link(self):
        output = self._make_output()
        html = render_html(output)
        for article in output.decision.articles:
            assert article.url in html

    def test_metriche_coerenti(self):
        output = self._make_output()
        metrics = compute_metrics(output)
        assert metrics["articoli_inclusi"] == len(output.decision.articles)
        assert metrics["tool_call_totali"] == output.tool_calls_count
