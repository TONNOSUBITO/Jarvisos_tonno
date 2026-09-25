# Roadmap

Legenda: ✅ implementato e testato in cloud · 🧪 implementato, NON testato su hardware reale · 🎭 mock · ❌ mancante

## Fase 1 — MVP dimostrabile in cloud (questa consegna)
| Elemento | Stato |
|---|---|
| UI minimale: input testo, stato, piano, risultato, resoconto, log, Stop, conferme, elenco/cancella note | ✅ (Chromium headless) |
| Pulsante «Parla» | ❌ presente ma disabilitato (Fase 2) |
| Router deterministico italiano | ✅ |
| Ricerca + apertura primo risultato + lettura pagina (Playwright) | ✅ su sito di prova locale; 🧪 su DuckDuckGo (selettore `a.result__a` non verificato: in cloud Chromium rifiuta la CA del proxy) |
| Apertura app approvate | 🎭 in cloud; 🧪 `NativeAppAdapter` |
| Bozza nota + conferma + salvataggio in vault | ✅ |
| Permessi per capacità, conferma legata all'hash, audit redatto | ✅ |
| Stop globale e per attività, timeout attività/tool/conferma, limite passi | ✅ |
| BudgetMeter + rotte a pagamento disattivate | ✅ (unit test, nessun provider reale collegato) |
| Skill loader + skill demo | ✅ |
| Test automatici | ✅ 44 test |

**Criterio di completamento:** `pytest -q` verde; `python -m jarvis` avviabile; flusso UI end-to-end provato headless. Soddisfatto.

## Fase 2 — prova supervisionata sul PC (da fare con te)
- ❌ guida adattata all'OS reale (in attesa di OS e CPU esatti)
- ❌ push-to-talk (tasto in UI + scorciatoia globale), cattura audio locale
- ❌ `WhisperCppSTT` con modello multilingue `base` (poi `small` se la CPU regge); confronto opzionale faster-whisper int8
- ❌ `KokoroTTS` locale (voci italiane: 1 femminile, 1 maschile — qualità da ascoltare)
- ❌ `NativeAppAdapter` provato su app reali; verifica finestra aperta
- ❌ misure: fine frase → testo, → primo audio, RAM/CPU, % comandi riusciti su un set definito

## Fase 3 — modelli e memoria
- ❌ OmniRoute: verificare endpoint reale, tool calling, streaming, fallback; collegare `GuardedProvider`
- ❌ Ollama con modello piccolo (candidati: qwen3:1.7b 1,4 GB, qwen3:4b 2,5 GB) — misurare prima
- ❌ livello 2 (risposta) e 3 (agente con tool) per intenti `unknown`
- ❌ memoria durevole con consenso (preferenze), ricerca nella vault
- ❌ confronto RuleRouter vs Jev (costo, latenza totale, accuratezza) prima di un eventuale `JevRouter`
- ❌ Fish Audio opt-in

## Fase 4 — controllo più ampio e secondo PC
- ❌ adapter accessibilità (Windows UI Automation, Linux AT-SPI), computer-use a screenshot con limiti
- ❌ secondo PC con config propria
- ❌ sincronizzazione vault (es. Syncthing) con guida conflitti/backup
- ❌ controllo remoto via rete privata (es. Tailscale) con autenticazione e conferma sul dispositivo bersaglio
- ❌ HUD / Cockpit sullo stesso stato
