# Architettura

## Flusso
```text
[UI web 127.0.0.1]
  ├─ testo ─────────────────────────────► POST /api/command
  └─ tieni premuto 🎤 → PCM → WAV 16 kHz ► POST /api/voice (solo in memoria)
                                              │
                                              ▼
 Orchestrator ── stato «trascrizione» → SpeechToText locale (faster-whisper)
        │
        ▼
  IntentRouter (RuleRouter, livello 1, locale, €0)
        ├─ intento noto → plan_for(intent) → [Action…]
        └─ unknown ──► Agent (livelli 2/3, solo se model.chat ≠ deny)
                         FallbackProvider → GuardedProvider (paid off, budget) → Ollama/OmniRoute /v1
                         il modello PROPONE tool_calls ────┐
        ▼                                                  ▼
  Orchestrator._execute(task, tool, args)   ← unico punto per regole e agente
     max_steps · PermissionPolicy (auto/confirm/deny) · taint anti-esfiltrazione
     confirm → «attesa_conferma», anteprima, hash monouso
     Tool.run() con tool_timeout → ToolResult(ok, summary, verified, untrusted_text)
        ▼
  StepRecord + AuditLog (redatto) → build_report() → UI
        ▼
  UI → POST /api/tts → Kokoro locale | 204 → speechSynthesis del browser
     → POST /api/tasks/{id}/metric (prima_risposta_audio_ms)

Stop (pulsante / Esc / «fermati»): cancella i task asyncio, ferma la voce, Tool.stop() chiude il browser.
task_timeout avvolge l'intera attività, trascrizione inclusa.
```

## Moduli
| Modulo | Contenuto |
|---|---|
| `core/orchestrator.py` | ciclo di vita delle attività, permessi, conferme, limiti, taint |
| `core/agent.py` | livelli 2–3: messaggi, schemi dei tool visibili, dato non fidato |
| `core/state.py`, `core/report.py` | stato osservabile, resoconto |
| `routing/router.py` | regole italiane, tolleranti alle trascrizioni |
| `providers/base.py` | `ModelProvider`, OpenAI-compatibile, `GuardedProvider`, `FallbackProvider`, `BudgetMeter` |
| `audio/` | decodifica WAV, STT, TTS |
| `tools/` | browser, app, note, memoria, file, permessi, audit |
| `memory/vault.py` | vault Markdown: scrittura senza sovrascrittura, ricerca, modifica, eliminazione |
| `server.py`, `web/index.html` | API locale con token e UI |
| `tools_cli.py` | `jarvis doctor`, `jarvis models` |

## Confini cloud / locale
| Componente | Dove gira | Dati verso l'esterno |
|---|---|---|
| UI, orchestratore, router, permessi, audit, vault | PC locale | nessuno |
| Browser dedicato | PC locale | le richieste web che l'utente chiede |
| STT faster-whisper, TTS Kokoro | PC locale | nessuno (download una tantum dei modelli) |
| OmniRoute (opt-in) | gateway locale → provider cloud | comandi e risultati dei tool verso i provider scelti (dati privati esclusi salvo `allow_private_data`) |
| Ollama (opzionale) | PC locale | nessuno |
| Claude Code cloud | solo sviluppo | codice della repo |

## Interfacce estendibili
- `IntentRouter.route(text) -> Intent` — `RuleRouter`; futuro `JevRouter` (solo classificazione in insieme chiuso).
- `ModelProvider.complete(messages, tools) -> ModelResponse` — `MockProvider`, `OpenAICompatibleProvider`
  (OmniRoute `/v1`, Ollama `/v1`); sempre dietro `GuardedProvider` (rotte a pagamento off, budget).
- `Tool` con `capability`, `run`, `preview`, `stop`.
- `AppAdapter.launch(argv)` — `MockAppAdapter`, `NativeAppAdapter` (Popen senza shell). Futuro: adapter di accessibilità (UI Automation su Windows, AT-SPI su Linux) e computer-use a screenshot con limiti.
- `SpeechToText` / `TextToSpeech` — `FasterWhisperSTT`, `KokoroTTS`, mock per i test.

## Dispositivi
Stesso codice, `config/device.toml` locale per PC (`device_id`, piattaforma, app, cartelle, permessi, limiti).
Ogni istanza controlla solo il proprio PC. Controllo remoto e sincronizzazione: Fase 4, separati.

## Stato condiviso
`Task` (in `core/state.py`) è l'unica struttura letta da UI; HUD e Cockpit futuri leggeranno la stessa
API `/api/state` e la stessa vault. Stati: in_ascolto, trascrizione, pianificazione, attesa_conferma,
esecuzione, risposta, completato, fermato, errore.

## Dipendenze
Base: fastapi, uvicorn, httpx, playwright (≥1.56), numpy. Extra: `voice` (faster-whisper), `tts` (kokoro-onnx), `dev` (pytest, pytest-asyncio). Nessun SDK cloud: i modelli si usano via HTTP
OpenAI-compatibile.
