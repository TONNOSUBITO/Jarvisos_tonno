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
| Microfono sempre acceso | push-to-talk: il flusso audio si apre alla pressione e si chiude al rilascio; nessuna parola di attivazione |
| Registrazioni conservate | l'audio resta in memoria per la trascrizione e viene scartato; nel registro finisce solo il testo del comando (max 500 caratteri) |
| Modello che agisce da solo | il modello propone soltanto: ogni chiamata passa da `Orchestrator._execute` (permessi, conferme, `max_steps`, timeout, audit); strumenti inesistenti o argomenti non validi vengono rifiutati |
| Prompt injection verso il modello | risultati dei tool racchiusi tra `<<<DATO_NON_FIDATO>>>` e istruzioni di sistema esplicite; una conferma rifiutata ferma l'agente |
| Esfiltrazione di dati privati | tool con dati privati (file, memoria, note) invisibili al modello salvo `allow_private_data`; dopo averli letti, `web.*` richiede conferma con URL completo in anteprima |
| File di segreti | `files.read` rifiuta `.env`, chiavi, `*password*`, `*token*`, `cookies*` ecc.; memoria e vault rifiutano testo che sembra un segreto |
| Cancellazioni irreversibili | `files.delete` sposta in `.cestino-jarvis/` nella stessa cartella; nessuna sovrascrittura in `files.write`/`files.move` |
| File operazioni fuori dalla cartella | `work_dir` unica, percorsi risolti e confinati, cestino non raggiungibile dai comandi |
| Comandi verso Jev (TypeSafe) | opt-in (`[router] engine`), solo per comandi che le regole non capiscono; serve chiave e `budget_eur` > 0; Jev sceglie solo tra opzioni chiuse (intenti, app approvate) e le azioni passano dagli stessi permessi |
| Skill malevole | nessuna importazione di skill di terzi: si creano a mano o con conferma sull'anteprima completa; rifiutano testo che sembra un segreto; ciò che descrivono passa comunque da `_execute` |
| Modelli voce manomessi | `jarvis models` verifica SHA-256 dei file Kokoro (hash registrati al primo download del 25/09/2026 dalla release ufficiale) |

## Permessi
Tre livelli per capacità e per dispositivo (`config/device.toml`): `auto`, `confirm`, `deny`.
Capacità non elencate = `deny`. Default:
- `auto`: app approvate, ricerca e lettura web, elenco memoria, ricerca note, elenco/lettura file in `work_dir`;
- `confirm`: salvataggio nota, «ricorda», «dimentica», creazione/spostamento/cestino file;
- `deny`: modelli (`model.chat`), shell (`shell.exec`, non modificabile).

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
- Hash dei modelli Kokoro: registrati da me al primo download (fiducia al primo uso), non pubblicati dall'autore.
- Whisper viene scaricato da Hugging Face tramite le librerie, senza hash fissato da Jarvis.
- Un modello locale piccolo può seguire comunque istruzioni malevole presenti nei dati: i permessi restano l'ultima difesa.
- `check_url` risolve il DNS prima della navigazione; un rebinding tra controllo e navigazione resta teoricamente possibile (mitigato dal ricontrollo dell'URL finale).
