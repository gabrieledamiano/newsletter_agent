"""Interfaccia Streamlit per il Newsletter Agent."""

from __future__ import annotations

import streamlit as st

from agent.core import TraceEvent, process_topic
from agent.llm_client import build_backend
from agent.reporting import compute_metrics, render_html, render_markdown, write_artifacts

st.set_page_config(page_title="Newsletter Agent", page_icon="📰", layout="wide")

st.title("📰 Generatore Autonomo di Newsletter")
st.caption("Un agente che cerca, valuta e riassume articoli recenti su qualsiasi argomento.")

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

col_input, col_config = st.columns([3, 1])

with col_input:
    topic = st.text_input(
        "Argomento della newsletter",
        value="AI in medicina",
        placeholder="es. intelligenza artificiale in medicina, energie rinnovabili, ...",
    )

with col_config:
    offline = st.checkbox("Modalità offline (simulata)", value=False)

run = st.button("🚀 Genera newsletter", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Elaborazione
# ---------------------------------------------------------------------------

if run and topic.strip():
    backend = build_backend(offline=offline)

    st.subheader("🔄 Reasoning loop dell'agente")

    trace_container = st.container()
    trace_events: list[TraceEvent] = []

    def render_event(event: TraceEvent, box=trace_container) -> None:
        trace_events.append(event)
        if event.kind == "tool_call":
            box.markdown(
                f"**Iter {event.iteration}** — 🔧 `{event.name}` "
                f"`{event.arguments}` → {event.summary}"
            )
        elif event.kind == "final":
            box.markdown(f"**Iter {event.iteration}** — ✅ {event.summary}")
        elif event.kind == "error":
            box.error(f"Iter {event.iteration} — ❌ {event.summary}")

    with st.spinner("L'agente sta lavorando..."):
        output = process_topic(
            backend, topic.strip(), offline=offline, on_event=render_event
        )

    # ---------------------------------------------------------------------------
    # Metriche
    # ---------------------------------------------------------------------------

    st.subheader("📊 Metriche")
    metrics = compute_metrics(output)

    cols = st.columns(5)
    cols[0].metric("Articoli inclusi", metrics["articoli_inclusi"])
    cols[1].metric("Articoli fetchati", metrics["articoli_fetchati"])
    cols[2].metric("Risultati valutati", metrics["risultati_valutati"])
    cols[3].metric("Tool call totali", metrics["tool_call_totali"])
    cols[4].metric(
        "Tempo", f"{metrics['tempo_totale_s']}s",
        delta=f"-{metrics['tempo_manuale_stimato_min']} min manuali",
        delta_color="inverse",
    )

    # ---------------------------------------------------------------------------
    # Newsletter
    # ---------------------------------------------------------------------------

    st.subheader("📰 Newsletter generata")

    tab_html, tab_md = st.tabs(["HTML", "Markdown"])

    md_content = render_markdown(output)
    html_content = render_html(output)

    with tab_html:
        st.components.v1.html(html_content, height=800, scrolling=True)

    with tab_md:
        st.markdown(md_content)

    # ---------------------------------------------------------------------------
    # Download
    # ---------------------------------------------------------------------------

    st.subheader("📥 Download")
    paths = write_artifacts(output, trace_events)

    col_dl1, col_dl2, col_dl3, col_dl4 = st.columns(4)
    col_dl1.download_button(
        "📄 newsletter.md",
        paths["md"].read_bytes(),
        file_name="newsletter.md",
        mime="text/markdown",
    )
    col_dl2.download_button(
        "🌐 newsletter.html",
        paths["html"].read_bytes(),
        file_name="newsletter.html",
        mime="text/html",
    )
    col_dl3.download_button(
        "🔍 agent_trace.json",
        paths["trace"].read_bytes(),
        file_name="agent_trace.json",
        mime="application/json",
    )
    col_dl4.download_button(
        "📋 agent_decision.json",
        paths["decision"].read_bytes(),
        file_name="agent_decision.json",
        mime="application/json",
    )
