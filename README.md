# Jarvis — assistente personale «speak to action» (Fase 1)

Assistente locale-first: ricevi un comando, lo interpreta con regole locali, agisce con strumenti
autorizzati (browser dedicato, app approvate, note in una vault Markdown), mostra cosa fa e
produce un resoconto. **Non è un sistema operativo**: «OS» è solo una metafora.

## Stato reale (leggere prima)

| Area | Stato |
|---|---|
| UI web minimale (input testo, stato, piano, conferme, log, Stop, note) | ✅ implementata e provata in cloud (headless) |
| Router a regole in italiano (livello 1) | ✅ |
| Browser dedicato Playwright: cerca, apri risultato, leggi pagina | ✅ provato **solo su un sito di prova locale** |
| Apertura app | ⚠️ in cloud solo **mock**; l'adapter nativo Windows/Linux esiste ma non è testato |
| Note/report con conferma prima del salvataggio, vault Markdown | ✅ |
| Permessi per capacità, conferme puntuali, audit con segreti oscurati, Stop, timeout, limite passi, budget | ✅ |
| Voce (push-to-talk, whisper.cpp, Kokoro, Fish Audio) | ❌ Fase 2–3, solo interfacce |
| Modelli (OmniRoute, Ollama), router Jev | ❌ Fase 3, solo interfacce/client non provato su server reale |
| Controllo dell'altro PC, sincronizzazione vault | ❌ Fase 4 |

Nessun test è stato fatto sui tuoi PC: microfono, desktop e app reali non sono provati.
Dettagli: [docs/ROADMAP.md](docs/ROADMAP.md).

## Prerequisiti
- Python 3.11+ (Windows o Linux)
- Chromium per Playwright (`python -m playwright install chromium`, ~150 MB) oppure un Chromium già presente indicato con `JARVIS_CHROMIUM_PATH`

## Sviluppo in Claude Code cloud
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q                          # 44 test, incluso Chromium headless sul sito di prova
```
In cloud Chromium è preinstallato in `/opt/pw-browsers` (Playwright 1.56). Non eseguire `playwright install`.

Avvio manuale in cloud con il sito di prova:
```bash
python -m http.server 8911 --bind 127.0.0.1 -d tests/fixtures/site &
cp config/device.example.toml config/device.toml
# in config/device.toml: search_url = "http://127.0.0.1:8911/search.html?q={q}",
#   result_selector = "a.result", allow_local_network = true, headless = true
python -m jarvis --headless        # http://127.0.0.1:8765
```

## Installazione sul PC (Fase 2, preliminare)
Vedi [docs/TEST_ON_PC.md](docs/TEST_ON_PC.md). In sintesi:

**Windows (PowerShell)**
```powershell
py -3.11 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e .
python -m playwright install chromium
copy config\device.example.toml config\device.toml   # poi modificalo
python -m jarvis
```
**Linux**
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
python -m playwright install chromium
cp config/device.example.toml config/device.toml
python -m jarvis
```
Apri `http://127.0.0.1:8765`. Nessun permesso amministratore richiesto. Jarvis rifiuta di ascoltare su indirizzi non loopback.

## Comandi supportati (Fase 1)
- `apri calcolatrice` — solo app elencate in `[apps]` di `config/device.toml`
- `cerca meteo Roma` — cerca e mostra i risultati
- `cerca e apri documentazione python` — cerca e apre il primo risultato nel browser dedicato
- `apri il sito example.com`
- `prepara una nota: …` — bozza, poi **conferma** prima di salvarla in `vault/inbox/`
- `stop` / `fermati` — ferma tutto (come il pulsante ■ Stop)

## Fermare e disinstallare
- Fermare: pulsante **■ Stop** (ferma attività e chiude il browser), poi `Ctrl+C` nel terminale.
- Disinstallare: elimina la cartella del progetto. Dati locali: `data/` (audit, profilo browser dedicato) e la vault configurata. Nessun servizio, avvio automatico o chiave di registro viene creato.

## Documentazione
[CLAUDE.md](CLAUDE.md) · [Architettura](docs/ARCHITECTURE.md) · [Roadmap](docs/ROADMAP.md) ·
[Sicurezza](docs/SECURITY.md) · [Costi](docs/COSTS.md) · [Test sul PC](docs/TEST_ON_PC.md)
