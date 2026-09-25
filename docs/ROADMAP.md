# Roadmap

Legenda: ✅ implementato e testato in cloud · 🧪 implementato, NON testato su hardware reale · 🎭 mock · ❌ mancante

## Fase 1 — MVP ✅
UI, router a regole, browser Playwright, app (mock), note con conferma, permessi, audit, Stop, timeout, limiti.

## Fase 2 — voce e uso sul PC
| Elemento | Stato |
|---|---|
| Push-to-talk in UI (tasto / barra spaziatrice), microfono acceso solo durante la pressione | ✅ con microfono simulato di Chromium; 🧪 microfono reale |
| Audio solo in memoria, mai su disco; limite di durata e dimensione | ✅ |
| STT locale faster-whisper `base` int8 (default) | ✅ trascrizione reale in cloud |
| STT locale whisper.cpp (`pywhispercpp`) | ✅ provato a mano in cloud; nessun test automatico |
| TTS locale Kokoro (`kokoro-onnx`, voci `if_sara` / `im_nicola`) | ✅ sintesi reale in cloud; 🧪 qualità all'ascolto |
| TTS del browser (speechSynthesis) come fallback | 🧪 dipende dalle voci italiane installate nel sistema |
| TTS Fish Audio opt-in (`s2.1-pro-free`, permesso `tts.cloud`) | 🎭 formato richiesta verificato su docs ufficiali, mai chiamato davvero |
| Precaricamento modelli all'avvio | ✅ |
| Misure reali: `stt_ms`, `audio_s`, `prima_risposta_audio_ms`, `model_ms` in UI e audit | ✅ |
| `NativeAppAdapter` (Popen senza shell) | 🧪 |
| Installer Linux | ✅ eseguito su un clone pulito in cloud |
| Installer Windows | 🧪 script non eseguito; **CI su Windows verde** il 25/09/2026 (installazione dipendenze voce, Chromium, 80 test, doctor) |
| `jarvis doctor`, `jarvis models` (hash SHA-256) | ✅ |
| Scorciatoia push-to-talk globale (fuori dal browser) | ❌ richiede hook di tastiera di sistema: rimandata |

**Misure in cloud (4 thread x86, nessuna GPU; NON il tuo Ryzen 3):** comando di 3,5 s → trascrizione 585 ms
a modelli caldi; dalla fine della frase all'inizio della risposta vocale 2,1 s. A freddo (primo comando senza
precaricamento) 7,2 s. Frase di prova «Cerca e apri documentazione» trascritta «Cerca i apri documentazioni»:
il router ora tollera queste varianti. I nomi inglesi («Python») vengono trascritti male.

## Fase 3 — modelli e memoria
| Elemento | Stato |
|---|---|
| Livello 2 (risposta del modello) e 3 (agente con tool) per richieste non coperte dalle regole | ✅ con provider simulato |
| Tool proposti dal modello → stessi permessi, conferme, limiti, audit | ✅ |
| Risultati dei tool al modello racchiusi come dato non fidato | ✅ |
| Tool negati o con dati privati nascosti al modello | ✅ |
| Anti-esfiltrazione: dopo letture private, le azioni web richiedono conferma | ✅ |
| Catena di fallback, rotte a pagamento disattivate, budget con blocco | ✅ |
| Client OpenAI-compatibile (Ollama `/v1`, OmniRoute `/v1`) | 🎭 mai collegato a un server reale |
| Memoria su richiesta con conferma, elenco, oblio, modifica a mano | ✅ |
| Ricerca nelle note, modifica ed eliminazione note da UI | ✅ |
| Router Jev (TypeSafe) | ❌ nessuna API ufficiale trovata con prezzo verificabile; resta l'interfaccia `IntentRouter` |
| Confronto tra router su un set di frasi | ❌ ha senso solo con un secondo router reale |

## Fase 4 — controllo più ampio e secondo PC
| Elemento | Stato |
|---|---|
| File in cartella autorizzata: elenca, leggi (auto); crea, sposta, cestina (conferma) | ✅ |
| Adapter di accessibilità (UI Automation / AT-SPI), computer-use a screenshot | ❌ dopo i test sul PC |
| Secondo PC | ❌ stesso installer con `device_id` diverso, **dopo** l'approvazione del primo |
| Sincronizzazione vault (es. Syncthing) | ❌ |
| Controllo remoto via rete privata con autenticazione | ❌ volutamente non fatto prima dei test di sicurezza sul PC |
| HUD / Cockpit sullo stesso stato | ❌ dopo i test funzionali |
