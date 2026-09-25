# Sicurezza

## Modello delle minacce
| Minaccia | Mitigazione (Fase 1) |
|---|---|
| Altro sito aperto nel browser chiama l'API locale (CSRF) | token di sessione casuale nell'header `X-Jarvis-Token`, generato a ogni avvio |
| DNS rebinding verso 127.0.0.1 | `TrustedHostMiddleware`: solo `127.0.0.1`, `localhost`, `[::1]` |
| Esposizione in rete | `python -m jarvis` rifiuta host non loopback; nessuna porta pubblica |
| Prompt injection da pagine web / file | il testo esterno è `untrusted_text`: mostrato nel log con etichetta, mai passato al router né usato come argomento di un altro tool (test `test_prompt_injection_in_page_is_not_executed`) |
| Browser usato per raggiungere servizi locali (SSRF) | `check_url`: solo http/https, blocco loopback/rete privata/link-local salvo `allow_local_network`, allowlist domini opzionale, ricontrollo dopo redirect |
| Esecuzione di comandi arbitrari | nessun tool shell; `shell.exec` forzato a `deny`; app solo da allowlist, `Popen` senza shell |
| Azioni irreversibili silenziose | capacità `confirm` con anteprima; conferma legata a hash (task, tool, argomenti), monouso, con scadenza |
| Loop dell'agente | `max_steps`, `tool_timeout_s`, `task_timeout_s`, nessun retry automatico |
| Spesa incontrollata | `budget_eur = 0` di default, rotte a pagamento disattivate (`GuardedProvider`) |
| Segreti in log/vault | `redact()` su tutto l'audit; la vault rifiuta contenuti che sembrano segreti |
| Profilo browser personale | profilo dedicato in `data/browser-profile`, download disattivati |
| Path traversal nella vault | percorsi risolti e confinati alla radice, solo `.md` |

## Permessi
Tre livelli per capacità e per dispositivo (`config/device.toml`): `auto`, `confirm`, `deny`.
Capacità non elencate = `deny`. Default: app approvate, ricerca e lettura web, bozze = `auto`; salvataggio nota = `confirm`; modelli e shell = `deny`.

Da Fase 3–4, **sempre `confirm`**: invio email/messaggi, pubblicazione, acquisti, download/esecuzione, installazioni,
spostamento/cancellazione di molti file, uso di credenziali, modifica permessi o impostazioni importanti,
qualsiasi azione sull'altro PC. CAPTCHA, pagamenti e MFA: sempre intervento umano.

**Modalità avanzata** (comandi di sistema non predefiniti): non implementata. Se progettata, dovrà essere
temporanea (scadenza), attivata esplicitamente in UI, con ogni comando in anteprima + conferma e audit.

## Audit
`data/audit.jsonl`: inizio/fine attività, passi, negazioni, rifiuti. Segreti oscurati. Nessuna trascrizione
audio (non esiste ancora) e nessun contenuto completo delle pagine. Locale, non sincronizzato.

## Segreti
Solo in `.env` o nel gestore credenziali del sistema; `.env`, `config/device.toml`, `data/`, `vault/` sono in `.gitignore`.
Mai in chat, commit o vault.

## Backup e rollback
- Codice: git (branch + PR, nessun merge automatico). Rollback = checkout della versione precedente.
- Vault: cartella Markdown; backup con copia/Syncthing versionato (Fase 4). Jarvis non sovrascrive note esistenti.
- Disinstallazione: eliminare la cartella; nessun servizio o modifica di sistema.

## Limiti noti
- Il token è visibile a chi ha accesso al desktop locale: Jarvis non protegge da un utente/malware già sul PC.
- La rilevazione dei segreti è a pattern: può sbagliare in entrambi i sensi.
- `check_url` risolve il DNS prima della navigazione; un rebinding tra controllo e navigazione resta teoricamente possibile (mitigato dal ricontrollo dell'URL finale).
