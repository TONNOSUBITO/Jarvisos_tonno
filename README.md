# Jarvis — assistente personale «speak to action»

Parli (tenendo premuto un tasto) o scrivi un comando. Jarvis lo trascrive **sul tuo PC**, lo
interpreta, agisce con strumenti autorizzati (browser dedicato, app approvate, file in una cartella
autorizzata, note e memoria in una vault Markdown), ti mostra cosa fa, chiede conferma prima delle
azioni delicate e ti risponde anche a voce. **Non è un sistema operativo**: «OS» è una metafora.

## Stato reale

| Funzione | Stato |
|---|---|
| Interfaccia HUD stile J.A.R.V.I.S.: anello centrale = tasto per parlare (colore e rotazione seguono lo stato, pulsa col livello reale del microfono), pannelli con soli dati reali (attività, risultato, RAM libera, voce, modello/provider, spesa, memoria, note), **Stop** | ✅ provata in cloud (Chromium headless) e sul portatile (comandi scritti) |
| Push-to-talk (tasto o barra spaziatrice) → trascrizione locale (faster-whisper) | ✅ provata in cloud con **microfono simulato** (file audio); ❓ microfono reale da provare sul PC |
| Risposta vocale locale Kokoro (voci italiane `if_sara`, `im_nicola`) / voce del browser | ✅ Kokoro provato in cloud; ❓ qualità d'ascolto da giudicare tu |
| Comandi a regole in italiano (costo zero, nessuna rete) | ✅ |
| Browser dedicato: cerca, apri risultato, leggi pagina | ✅ su sito di prova; ❓ DuckDuckGo reale: blocca gli IP dei datacenter (cloud e GitHub), da casa dovrebbe funzionare; se mostra un controllo anti-robot Jarvis lo dice e lascia la pagina aperta |
| Apertura app approvate | ✅ con adapter simulato; ❓ app reali sul PC |
| File in una cartella autorizzata (elenca, leggi, crea, sposta, cestina con conferma) | ✅ |
| Memoria su richiesta («ricorda che…», «cosa ricordi», «dimentica…»), ricerca nelle note | ✅ |
| Domande libere e compiti multi-passo con un modello (provider cloud con tua chiave API) | ✅ con modello simulato; ❓ mai collegato a un modello reale |
| Permessi per capacità, conferme monouso, anti-esfiltrazione, budget, audit | ✅ |
| Windows | ✅ test e installer verdi su Windows in GitHub Actions (voce reale inclusa); ❓ mai su un PC Windows reale |
| Controllo dell'altro PC, sincronizzazione vault, Cockpit multi-dispositivo | ❌ volutamente rimandati (vedi [ROADMAP](docs/ROADMAP.md)) |

✅ = funziona ed è testato · ❓ = implementato, da verificare sul tuo PC · ❌ = non fatto

## Installazione

Requisiti: Python **3.11, 3.12 o 3.13**, non 3.14, che la voce locale non supporta ancora
([python.org](https://www.python.org/downloads/): scegli 3.13 e spunta «Add to PATH»),
~1,5 GB liberi (Chromium ~150 MB, modelli voce ~500 MB, dipendenze). Nessun permesso di amministratore.

**Windows** (PowerShell nella cartella del progetto):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```
Poi doppio clic sull'icona **Jarvis** sul desktop (oppure `scripts\run.bat`).

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
| «prepara una nota: comprare latte» | anteprima → salvataggio in `vault/inbox/` | **sì** |
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
- `[voice]`: motore di trascrizione e di voce (`kokoro`, `browser`).
- `[model]` + `[[model.providers]]`: modelli per domande libere (vedi sotto). Disattivati di default.
- Chiavi (es. OmniRoute) solo in `.env`, mai nel TOML.

### Attivare un modello (facoltativo): chiavi API di uno o più provider
Serve solo per domande libere e compiti che le regole non coprono. Un modello **locale** non è praticabile su questo
hardware (misura: `qwen3:1.7b` su 2 core oltre 5 minuti per risposta), quindi si usano provider cloud.

Provider pronti in [`config/providers.example.toml`](config/providers.example.toml), in ordine di fallback
(endpoint e modelli verificati sulle documentazioni ufficiali il 25/09/2026):

| # | Provider | Variabile nel `.env` | Modello | Trattamento |
|---|---|---|---|---|
| 1 | Groq | `GROQ_API_KEY` | `openai/gpt-oss-20b` | gratuito |
| 2 | Cerebras | `CEREBRAS_API_KEY` | `qwen-3.8-27b` | gratuito |
| 3 | Gemini | `GEMINI_API_KEY` | `gemini-3.5-flash-lite` | gratuito, limiti bassi |
| 4 | Mistral | `MISTRAL_API_KEY` | `mistral-large-latest` | gratuito, limiti bassi |
| 5 | OpenRouter | `OPENROUTER_API_KEY` | `qwen/qwen3.8-27b:free` | solo modelli `:free` |
| 6 | Cohere | `COHERE_API_KEY` | `command-a-plus-05-2026` | trial |
| 7 | Together | `TOGETHER_API_KEY` | `openai/gpt-oss-120b` | `paid = true` (crediti che scadono) |
| 8 | Anthropic | `ANTHROPIC_API_KEY` | `claude-haiku-4-5-20251001` | `paid = true` |

1. Metti le chiavi che hai **solo** nel file `.env` (mai in chat, nel TOML o su GitHub). Quelle che non metti
   vengono saltate.
2. Accoda i provider alla tua configurazione (PowerShell, nella cartella di Jarvis):
   ```powershell
   Get-Content config\providers.example.toml | Add-Content config\device.toml
   ```
3. In `config\device.toml` cambia `"model.chat" = "deny"` in `"auto"` e, nella sezione `[model]`, `enabled = false`
   in `true`.
4. `python -m jarvis doctor` mostra quali chiavi sono presenti (senza stamparle). Riavvia Jarvis.

In alternativa, se usi già **OmniRoute** con le tue chiavi, basta un solo provider:
```toml
[[model.providers]]
name = "omniroute"
base_url = "http://127.0.0.1:20128/v1"
model = "auto"
```
(OmniRoute deve essere acceso; i limiti di spesa si impostano in OmniRoute, Jarvis non ne conosce i prezzi.)

Cosa sapere:
- con un provider cloud **i tuoi comandi escono dal PC**; file, memoria e note restano esclusi salvo
  `allow_private_data = true`;
- se un provider fallisce o finisce la quota, Jarvis passa al successivo;
- i provider `paid = true` restano bloccati finché non imposti `allow_paid = true` e un `budget_eur` > 0;
- l'agente usa gli strumenti di Jarvis con gli stessi permessi e conferme: la chiave dà accesso al modello, non al PC.

## Fermare e disinstallare
- Fermare: **■ Stop** o tasto Esc (ferma attività, voce e browser), poi Ctrl+C nel terminale.
- Disinstallare: elimina l'icona Jarvis dal desktop e la cartella del progetto (contiene `.venv`, `data/`, modelli, vault predefinita) e,
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
