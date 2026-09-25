# Architettura

## Flusso
```text
[UI web 127.0.0.1] --testo--> POST /api/command
   (Fase 2: push-to-talk → WhisperCppSTT locale → testo)
        │
        ▼
 Orchestrator ──► IntentRouter (RuleRouter, livello 1, locale, €0)
        │            └─ unknown → chiede chiarimento (livello 2/3: Fase 3)
        ▼
  plan_for(intent) → [Action…]   (max_steps)
        │
        ▼ per ogni Action
  PermissionPolicy.decide(capability)
     ├─ deny    → errore, audit
     ├─ confirm → stato «attesa_conferma», anteprima, hash legato all'azione
     └─ auto
        ▼
  Tool.run() con tool_timeout ─► ToolResult(ok, summary, verified, untrusted_text)
        │                              └─ testo esterno solo mostrato, mai eseguito
        ▼
  StepRecord + AuditLog (redatto) → build_report() → UI
   (Fase 2: TextToSpeech locale → audio)

Stop (pulsante / «fermati»): cancella i task asyncio + Tool.stop() (chiude il browser).
task_timeout avvolge tutta l'attività.
```

## Confini cloud / locale
| Componente | Dove gira | Dati verso l'esterno |
|---|---|---|
| UI, orchestratore, router, permessi, audit, vault | PC locale | nessuno |
| Browser dedicato | PC locale | le richieste web che l'utente chiede |
| STT whisper.cpp / TTS Kokoro (Fase 2) | PC locale | nessuno |
| Fish Audio TTS (Fase 3, opt-in) | cloud | testo da pronunciare |
| OmniRoute (Fase 3, opt-in) | gateway locale → provider cloud | prompt verso i provider scelti |
| Ollama (Fase 3, opzionale) | PC locale | nessuno |
| Claude Code cloud | solo sviluppo | codice della repo |

## Interfacce estendibili
- `IntentRouter.route(text) -> Intent` — `RuleRouter`; futuro `JevRouter` (solo classificazione in insieme chiuso).
- `ModelProvider.complete(messages, tools) -> ModelResponse` — `MockProvider`, `OpenAICompatibleProvider`
  (OmniRoute `/v1`, Ollama `/v1`); sempre dietro `GuardedProvider` (rotte a pagamento off, budget).
- `Tool` con `capability`, `run`, `preview`, `stop`.
- `AppAdapter.launch(argv)` — `MockAppAdapter`, `NativeAppAdapter` (Popen senza shell). Futuro: adapter di accessibilità (UI Automation su Windows, AT-SPI su Linux) e computer-use a screenshot con limiti.
- `SpeechToText` / `TextToSpeech` — mock ora; whisper.cpp, Kokoro, Fish in seguito.

## Dispositivi
Stesso codice, `config/device.toml` locale per PC (`device_id`, piattaforma, app, cartelle, permessi, limiti).
Ogni istanza controlla solo il proprio PC. Controllo remoto e sincronizzazione: Fase 4, separati.

## Stato condiviso
`Task` (in `core/state.py`) è l'unica struttura letta da UI; HUD e Cockpit futuri leggeranno la stessa
API `/api/state` e la stessa vault. Stati: in_ascolto, trascrizione, pianificazione, attesa_conferma,
esecuzione, risposta, completato, fermato, errore.

## Dipendenze (Fase 1)
fastapi, uvicorn, httpx, playwright (≥1.56); dev: pytest, pytest-asyncio. Nessun SDK cloud.
