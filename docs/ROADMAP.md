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
| TTS locale Kokoro (`kokoro-onnx`, voci `if_sara` / `im_nicola`) | ✅ sintesi reale in cloud; 🧪 qualità all'ascolto |
| TTS del browser (speechSynthesis) come fallback | 🧪 dipende dalle voci italiane installate nel sistema |
| Alternative rimosse (ponytail): whisper.cpp, Fish Audio, loader skill, tool bozza separato | ❌ tolte: nessun uso reale; riaggiungere solo se servono |
| Precaricamento modelli all'avvio | ✅ |
| Risposta vocale a frasi: la prima frase si sintetizza e parte subito, le successive si preparano mentre parla; Stop svuota la coda | ✅ in Chromium con API simulate; 🧪 guadagno reale sul Ryzen non misurato |
| Misure reali: `stt_ms`, `audio_s`, `prima_risposta_audio_ms`, `model_ms` in UI e audit | ✅ |
| `NativeAppAdapter` (Popen senza shell) | 🧪 |
| Installer Linux | ✅ eseguito su un clone pulito in cloud |
| Installer Windows | ✅ `install.ps1` eseguito in CI su Windows pulito (PowerShell 5.1, Python 3.13): dipendenze, Chromium, modelli verificati, config; poi test voce reale Kokoro → Whisper verde. 🧪 mai su un PC reale |
| `jarvis doctor`, `jarvis models` (hash SHA-256) | ✅ |
| Scorciatoia push-to-talk globale (fuori dal browser) | ❌ richiede hook di tastiera di sistema: rimandata |

**Misure in cloud (4 thread x86, nessuna GPU; NON il tuo Ryzen 3):** comando di 3,5 s → trascrizione 585 ms
a modelli caldi; dalla fine della frase all'inizio della risposta vocale 2,1 s. A freddo (primo comando senza
precaricamento) 7,2 s. Frase di prova «Cerca e apri documentazione» trascritta «Cerca i apri documentazioni»:
il router ora tollera queste varianti. I nomi inglesi («Python») vengono trascritti male.

**Misure in cloud limitate a 2 core** (per avvicinarsi al Ryzen 3 3200U: 2 core / 4 thread, 15 W; resta una
CPU diversa, NON è un benchmark del tuo PC), frase di 3,8 s:
| Componente | Tempo | Nota |
|---|---|---|
| Whisper `base` int8 | 0,76 s | trascrizione corretta |
| Kokoro fp32 (`kokoro-v1.0.onnx`) | 1,01 s (RTF 0,27) | scelto |
| Kokoro int8 (`kokoro-v1.0.int8.onnx`) | 6,43 s (RTF 1,68) | **scartato**: più piccolo ma 6× più lento su questa CPU |

**E2E voce su Windows (GitHub Actions `windows-latest`, 25/09/2026)**: UI reale + microfono simulato di Chromium,
frase «Cerca e apri documentazione» → trascritta correttamente, eseguita; `stt_ms` 1003, `prima_risposta_audio_ms` 3963.

## Fase 3 — modelli e memoria
| Elemento | Stato |
|---|---|
| Livello 2 (risposta del modello) e 3 (agente con tool) per richieste non coperte dalle regole | ✅ con provider simulato |
| Tool proposti dal modello → stessi permessi, conferme, limiti, audit | ✅ |
| Risultati dei tool al modello racchiusi come dato non fidato | ✅ |
| Tool negati o con dati privati nascosti al modello | ✅ |
| Anti-esfiltrazione: dopo letture private, le azioni web richiedono conferma | ✅ |
| Catena di fallback, rotte a pagamento disattivate, budget con blocco | ✅ |
| OmniRoute locale come primo provider (`auto`), modello reale mostrato nell'HUD, `doctor` controlla che risponda, gateway spento → provider successivo in ≤3 s | ✅ con server simulato; 🧪 mai provato con OmniRoute reale |
| Client OpenAI-compatibile | 🧪 provato contro Ollama 0.12.3 reale con `qwen3:1.7b` su 2 core: ogni richiesta oltre 5 min (timeout del server) → modello locale **non praticabile** sul 3200U. 14 provider cloud d'esempio con chiave dell'utente: endpoint verificati sulle documentazioni, mai chiamati |
| Memoria su richiesta con conferma, elenco, oblio, modifica a mano | ✅ |
| Preferenze in memoria passate al modello (`share_memory`, opt-in), task contaminato → web con conferma | ✅ con modello simulato |
| Ricerca nelle note, modifica ed eliminazione note da UI | ✅ |
| Router Jev (TypeSafe): dopo le regole, sceglie l'intento (e l'app tra quelle approvate) con soglia di confidenza | 🎭 con API simulata (`httpx.MockTransport`); API e prezzi verificati su docs.typesafe.ai; mai chiamato davvero, accuratezza e latenza sull'italiano non misurate |
| Skill personali (`vault/skills/<nome>/SKILL.md`, formato agentskills.io come Hermes): crea con conferma, elenca, leggi; l'agente le usa | ✅ |
| Confronto tra router su un set di frasi | ❌ ha senso solo con un secondo router reale |

## Fase 4 — controllo più ampio e secondo PC
| Elemento | Stato |
|---|---|
| File in cartella autorizzata: elenca, leggi (auto); crea, sposta, cestina (conferma) | ✅ |
| Adapter di accessibilità (UI Automation / AT-SPI), computer-use a screenshot | ❌ dopo i test sul PC |
| Secondo PC | ❌ stesso installer con `device_id` diverso, **dopo** l'approvazione del primo |
| Sincronizzazione vault (es. Syncthing) | ❌ |
| Controllo remoto via rete privata con autenticazione | ❌ volutamente non fatto prima dei test di sicurezza sul PC |
| HUD sullo stesso stato (`jarvis/web/index.html`) | ✅ SVG + CSS, nessuna libreria; solo dati reali da `/api/state` e `/api/info` (RAM libera, provider). Misura in Chromium: thread principale ~0,8% (polling), animazioni sul compositor e in pausa dopo 30 s di inattività; `prefers-reduced-motion` rispettato |
| Cockpit multi-dispositivo | ❌ dopo il secondo PC |
