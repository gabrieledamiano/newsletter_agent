from ddgs import DDGS
import json

def test_duckduckgo(query: str, max_results: int = 10):
    print(f"🔍 Avvio ricerca su DuckDuckGo per la query: '{query}'...")
    
    try:
        # Inizializza il client di DuckDuckGo
        with DDGS() as ddgs:
            # ddgs.text() è la funzione per la ricerca web testuale
            results = list(ddgs.text(query, max_results=max_results))
            
        if not results:
            print("❌ Zero risultati! DuckDuckGo ha restituito una lista vuota.")
        else:
            print(f"✅ Trovati {len(results)} risultati!\n")
            # Stampiamo i risultati formattati bene
            print(json.dumps(results, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"⚠️ Si è verificato un errore di connessione/libreria: {e}")

if __name__ == "__main__":
    # Testiamo la query che hai suggerito
    test_duckduckgo("AI Medical")