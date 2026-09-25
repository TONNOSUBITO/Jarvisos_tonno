# Jarvis — assistente personale «speak to action»

Parli (tenendo premuto un tasto) o scrivi un comando. Jarvis lo trascrive **sul tuo PC**, lo
interpreta, agisce con strumenti autorizzati (browser dedicato, app approvate, file in una cartella
autorizzata, note e memoria in una vault Markdown), ti mostra cosa fa, chiede conferma prima delle
azioni delicate e ti risponde anche a voce. **Non è un sistema operativo**: «OS» è una metafora.

## Stato reale

| Funzione | Stato |
|---|---|
| UI web locale: parla/scrivi, stato, piano, conferme, risultato, log, **Stop**, misure, memoria, note | ✅ provata in cloud (Chromium headless) |
| Push-to-talk (tasto o barra spaziatrice) → trascrizione locale (faster-whisper o whisper.cpp) | ✅ provata in cloud con **microfono simulato** (file audio); ❓ microfono reale da provare sul PC |
| Risposta vocale locale Kokoro (voci italiane `if_sara`, `im_nicola`) / voce del browser / Fish Audio (cloud, opt-in) | ✅ Kokoro provato in cloud; ❓ qualità d'ascolto da giudicare tu; Fish solo con mock |
| Comandi a regole in italiano (costo zero, nessuna rete) | ✅ |
| Browser dedicato: cerca, apri risultato, leggi pagina | ✅ su sito di prova; ❓ DuckDuckGo reale (in cloud bloccato dal proxy) |
| Apertura app approvate | ✅ con adapter simulato; ❓ app reali sul PC |
| File in una cartella autorizzata (elenca, leggi, crea, sposta, cestina con conferma) | ✅ |
| Memoria su richiesta («ricorda che…», «cosa ricordi», «dimentica…»), ricerca nelle note | ✅ |
| Domande libere e compiti multi-passo con un modello (Ollama locale / OmniRoute) | ✅ con modello simulato; ❓ mai collegato a un modello reale |
| Permessi per capacità, conferme monouso, anti-esfiltrazione, budget, audit | ✅ |
| Windows | ✅ test automatici verdi su Windows (GitHub Actions); ❓ installer mai eseguito su un PC Windows reale |
| Controllo dell'altro PC, sincronizzazione vault, HUD/Cockpit | ❌ volutamente rimandati (vedi [ROADMAP](docs/ROADMAP.md)) |

✅ = funziona ed è testato · ❓ = implementato, da verificare sul tuo PC · ❌ = non fatto

## Installazione

Requisiti: Python 3.11+ ([python.org](https://www.python.org/downloads/), su Windows spunta «Add to PATH»),
~1,5 GB liberi (Chromium ~150 MB, modelli voce ~500 MB, dipendenze). Nessun permesso di amministratore.

**Windows** (PowerShell nella cartella del progetto):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
scripts\run.bat
```
**Linux**:
```bash
bash scripts/install.sh
scripts/run.sh
```
L'installer crea `.venv`, installa le dipendenze, scarica Chromium e i modelli voce (Kokoro con verifica
SHA-256), crea `config/device.toml` e lancia `python -m jarvis doctor`. Si apre `http://127.0.0.1:8765`.
Il browser chiederà il permesso per il microfono: serve solo mentre tieni premuto il tasto.

Dettagli e prima prova guidata: [docs/TEST_ON_PC.md](docs/TEST_ON_PC.md).

## Cosa puoi dire
| Esempio | Cosa fa | Conferma? |
|---|---|---|
| «apri calcolatrice» | apre un'app elencata in `[apps]` | no |
| «cerca meteo Roma» | ricerca e mostra i risultati | no |
| «cerca e apri documentazione python» | apre il primo risultato nel browser dedicato | no |
| «apri il sito example.com» | apre la pagina | no |
| «prepara una nota: comprare latte» | bozza → salvataggio in `vault/inbox/` | **sì** |
| «ricorda che preferisco il caffè amaro» / «cosa ricordi» / «dimentica caffè» | memoria in `vault/memory/preferenze.md` | sì per salvare e dimenticare |
| «cerca nelle note budget» | ricerca nella vault | no |
| «elenca i file», «leggi il file appunti.txt» | solo in `work_dir` | no |
| «sposta il file a.txt in archivio», «elimina il file vecchio.txt» | sposta / mette nel cestino `.cestino-jarvis` | **sì** |
| «stop», «fermati» (o pulsante ■ / tasto Esc) | ferma tutto e chiude il browser | — |
| qualsiasi altra domanda | se hai attivato un modello: risposta o compito multi-passo; altrimenti chiede di riformulare | per le azioni delicate sì |

## Configurazione
Tutto in `config/device.toml` (uno per PC, non va su GitHub). Le voci principali:
- `[apps]`: le app che Jarvis può aprire (`nome = ["eseguibile", "argomenti"]`).
- `[device] work_dir`: l'unica cartella in cui gestisce file.
- `[permissions]`: `auto` / `confirm` / `deny` per ogni capacità. Ciò che non è elencato è negato.
- `[voice]`: motore di trascrizione e di voce (`kokoro`, `browser`, `fish`).
- `[model]` + `[[model.providers]]`: modelli per domande libere (vedi sotto). Disattivati di default.
- Chiavi (Fish, OmniRoute) solo in `.env`, mai nel TOML.

### Attivare un modello (facoltativo)
Locale e gratuito con [Ollama](https://ollama.com) (installalo dal sito ufficiale), poi `ollama pull qwen3:1.7b`:
```toml
[permissions]
"model.chat" = "auto"
[model]
enabled = true
[[model.providers]]
name = "ollama"
base_url = "http://127.0.0.1:11434/v1"
model = "qwen3:1.7b"
```
Oppure OmniRoute (gateway verso molti provider, alcuni gratuiti con quote): `base_url = "http://127.0.0.1:20128/v1"`.
Con un provider cloud, i tuoi comandi escono dal PC. File, memoria e note restano esclusi finché non imposti
`allow_private_data = true`.

## Fermare e disinstallare
- Fermare: **■ Stop** o tasto Esc (ferma attività, voce e browser), poi Ctrl+C nel terminale.
- Disinstallare: elimina la cartella del progetto (contiene `.venv`, `data/`, modelli, vault predefinita) e,
  se vuoi, la cache di Playwright (`%USERPROFILE%\AppData\Local\ms-playwright` su Windows, `~/.cache/ms-playwright` su Linux).
  Nessun servizio, avvio automatico o chiave di registro viene creato.

## Sviluppo (Claude Code cloud)
```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev,voice,tts]"
python -m jarvis models --kokoro    # facoltativo: abilita il test reale Kokoro → Whisper
pytest -q
```
In cloud Chromium è in `/opt/pw-browsers` (Playwright 1.56): non eseguire `playwright install`.

Documentazione: [CLAUDE.md](CLAUDE.md) · [Architettura](docs/ARCHITECTURE.md) · [Roadmap](docs/ROADMAP.md) ·
[Sicurezza](docs/SECURITY.md) · [Costi](docs/COSTS.md) · [Test sul PC](docs/TEST_ON_PC.md)
