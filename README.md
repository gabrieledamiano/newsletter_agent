# 📰 Il Generatore Autonomo di Newsletter Settimanali

Agente autonomo per l'hackathon **Build with Gemma** — Track 3, Agenti Autonomi.

Dato un argomento, cerca articoli recenti, ne valuta la rilevanza, recupera
il contenuto completo dei migliori 3 e produce una newsletter in Markdown e HTML.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # incolla la chiave da https://aistudio.google.com/apikey

# 1. Verifica senza rete (< 1 secondo)
python run_agent.py --offline

# 2. Test (tutti devono passare)
python -m pytest tests/ -v

# 3. Primo contatto col modello reale
python run_agent.py --topic "AI in medicina"

# 4. Interfaccia Streamlit
streamlit run app.py
```

## Output

| File | Contenuto |
|------|-----------|
| `output/newsletter.md` | Newsletter Markdown |
| `output/newsletter.html` | Newsletter HTML |
| `output/agent_trace.json` | Trace delle chiamate ai tool |
| `output/agent_decision.json` | Decisione strutturata dell'agente |
