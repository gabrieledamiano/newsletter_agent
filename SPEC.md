# Il Generatore Autonomo di Newsletter Settimanali

## Panoramica

Un agente autonomo che, dato un argomento, cerca articoli recenti sul web,
ne valuta la rilevanza, recupera il contenuto completo dei migliori tre e
produce una newsletter strutturata in Markdown e HTML — pronta da inviare.

**Track 3 — Agenti Autonomi** | Build with Gemma Hackathon | Settembre 2026

## Il problema

Restare aggiornati su un tema specifico richiede un ciclo ripetitivo:
cercare articoli, aprirli uno per uno, valutarne la qualità, scartare i
duplicati, riassumere i contenuti rilevanti e comporli in un formato
leggibile. Sono 15-20 minuti di lavoro manuale ogni settimana — a bassa
densità decisionale ma alta ripetitività.

## Cosa produce il sistema

**Input:** un argomento testuale (es. "AI in medicina").

**Output:** quattro file in `output/`:

| File | Contenuto |
|------|-----------|
| `newsletter.md` | Newsletter in Markdown, pronta da inviare |
| `newsletter.html` | Newsletter in HTML, con stili inline |
| `agent_decision.json` | La decisione strutturata dell'agente |
| `agent_trace.json` | Sequenza di chiamate ai tool — prova di agenticità |

## Architettura

### I due tool

1. **`search_web_articles(query, max_results)`** — Cerca articoli recenti.
   Backend live: DuckDuckGo (nessuna API key aggiuntiva).
   Backend offline: dataset JSON simulato.

2. **`fetch_article_content(url)`** — Recupera il contenuto testuale di
   un articolo. Backend live: requests + trafilatura.
   Backend offline: dataset JSON simulato.

### Il reasoning loop

```
topic → search → [valutazione rilevanza] → fetch × 3 → [riassunto] → newsletter
                      ↑                                       |
                      └── riformula query se risultati scarsi ─┘
```

L'agente decide autonomamente:
- **Quale query usare** e se riformularla
- **Quali articoli fetchare** (scarta irrilevanti e duplicati)
- **Quando ha abbastanza materiale** per produrre la newsletter

### I quattro criteri di agenticità

| Criterio | Come è soddisfatto |
|----------|-------------------|
| Autonomia sul percorso | Query diverse per topic diversi; riformulazione automatica |
| Tool use reale | Il modello sceglie strumento e argomenti |
| Loop iterativo | I risultati di search condizionano i fetch successivi |
| Effetto esterno | File newsletter reali, verificabili fuori dalla conversazione |

### Indipendenza dal modello

L'architettura usa un `Protocol` Python: `GeminiBackend` e `ScriptedBackend`
sono intercambiabili. Sostituire il modello richiede una nuova classe con
due metodi, senza toccare il loop.

## Stack tecnologico

| Componente | Tecnologia | Motivazione |
|-----------|-----------|-------------|
| LLM | Gemini 2.5 Flash via google-genai | SDK attuale, API Interactions |
| Ricerca web | duckduckgo-search | Nessuna API key aggiuntiva |
| Estrazione testo | trafilatura | Stato dell'arte per article extraction |
| Validazione | Pydantic 2 | Schema rigido sull'output dell'agente |
| Interfaccia | Streamlit | Aggiornamento in tempo reale del loop |
| Test | pytest + ScriptedBackend | Deterministici, senza rete |

## Vincoli di design

- **Nessun contenuto inventato.** Ogni informazione nella newsletter
  proviene da una risposta di tool. Il modello riassume, non genera.
- **Degradazione controllata.** Se la ricerca live fallisce, il sistema
  rippiega sul mock senza interrompere il processo.
- **Separazione istruzioni/dati.** System prompt e topic in step distinti
  della history, per evitare confusione nel matching.

## Esecuzione rapida

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # incolla GEMINI_API_KEY

# Test senza rete
python run_agent.py --offline

# Test con modello reale
python run_agent.py --topic "AI in medicina"

# Interfaccia
streamlit run app.py
```

## Limiti noti

- DuckDuckGo applica rate limit severi: oltre 10-15 ricerche consecutive
  il servizio può bloccare temporaneamente.
- trafilatura non estrae contenuto da siti con paywall o JavaScript-heavy.
- Il riassunto dipende dalla qualità del modello: Gemini Flash è rapido
  ma meno preciso di Pro su testi lunghi.
- Un solo topic per esecuzione (estendibile a batch).
