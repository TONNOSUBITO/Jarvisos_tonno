# Primo test supervisionato sul PC

Obiettivo: verificare sul tuo PC reale ciò che in cloud non si può provare (microfono, voce all'ascolto, app,
Windows, velocità del Ryzen 3). Fallo su **un solo PC**; il secondo solo dopo aver approvato il primo.
Tempo stimato: 30–45 minuti, più i download (~700 MB).

## Il tuo hardware: Ryzen 3 3200U
2 core / 4 thread, 15 W (portatile), grafica Vega 3 integrata, 16 GB RAM. Cosa aspettarsi (**stime**, da misurare):
- trascrizione `base`: ok; **non** passare a `small` (circa 3× più lento);
- voce Kokoro: più lenta del cloud; se `prima_risposta_audio_ms` supera ~4000, usa `tts_engine = "browser"`;
- la GPU integrata non viene usata: tutto gira su CPU; tieni il portatile **collegato alla corrente**
  (a batteria la CPU rallenta);
- modello locale facoltativo: prova `qwen3:1.7b`; `qwen3:4b` sta in RAM ma sarà probabilmente lento.

## 0. Annota il sistema
Esegui `python -m jarvis doctor` dopo l'installazione: stampa sistema, CPU, thread e RAM.

| Voce | Portatile | Fisso |
|---|---|---|
| Output di `doctor` (righe «Sistema») | | |
| CPU esatta (Gestione attività → Prestazioni / `lscpu`) | | |
| Browser in cui apri Jarvis | | |

## 1. Installazione
Installa **Python 3.13** (non 3.14) da python.org spuntando «Add to PATH». L'installer lo cerca da solo.
Segui il README (sezione Installazione). Nessun comando richiede privilegi di amministratore.
Poi apri `config/device.toml` e controlla:
- `device_id` ("portatile" o "fisso");
- `[apps]`: su Windows l'installer approva calcolatrice e blocco note; su Linux aggiungile a mano;
- `work_dir`: crea una cartella di prova (es. `Documenti/JarvisProva`) con 2–3 file finti e indicala qui.

## 2. Checklist funzionale
| # | Prova | Atteso | Esito |
|---|---|---|---|
| 1 | `scripts\run.bat` / `scripts/run.sh` | si apre la UI, badge «voce→testo: faster-whisper», «risposta vocale: kokoro (locale)» | |
| 2 | Scrivi «apri calcolatrice» | si apre la calcolatrice e Jarvis lo dice a voce | |
| 3 | Scrivi «apri regedit» | rifiutato, non si apre nulla | |
| 4 | Tieni premuto 🎤, di' «apri blocco note», rilascia | il browser chiede il microfono (la prima volta), poi si apre l'app | |
| 5 | Barra spaziatrice tenuta premuta: «cerca e apri meteo Roma» | si apre una finestra Chromium **separata** con il primo risultato | |
| 6 | Se il 5 dice «Nessun risultato» | annotalo: il selettore di DuckDuckGo va aggiornato | |
| 7 | «prepara una nota: comprare il latte» → Rifiuta | nessun file creato | |
| 8 | Stessa nota → Conferma | file in `data/vault/inbox/`, visibile nella UI, apribile con Obsidian | |
| 9 | «ricorda che preferisco il caffè amaro» → Conferma, poi «cosa ricordi» | la risposta contiene il caffè | |
| 10 | «elenca i file», «leggi il file <nome>» | elenca/legge solo la cartella di prova | |
| 11 | «elimina il file <nome>» → Conferma | il file finisce in `.cestino-jarvis/` dentro la cartella | |
| 12 | Durante il 5 premi **■ Stop** (o Esc) | attività «fermato», voce interrotta, browser chiuso | |
| 13 | Guarda `data/audit.jsonl` | eventi presenti, nessuna password/chiave, nessun audio | |

## 3. Voce e velocità (la parte che conta)
Ripeti 10 comandi vocali diversi (lista suggerita sotto). Per ciascuno annota dalla riga «Misure» della UI:

| # | Frase detta | Testo trascritto | Corretto? | `stt_ms` | `prima_risposta_audio_ms` |
|---|---|---|---|---|---|
| 1 | apri calcolatrice | | | | |
| 2 | apri blocco note | | | | |
| 3 | cerca meteo Milano | | | | |
| 4 | cerca e apri notizie di oggi | | | | |
| 5 | prepara una nota: chiamare il dentista | | | | |
| 6 | ricorda che il mio colore preferito è il blu | | | | |
| 7 | cosa ricordi | | | | |
| 8 | elenca i file | | | | |
| 9 | cerca nelle note dentista | | | | |
| 10 | fermati | | | | |

Poi, con Jarvis acceso e fermo, annota la RAM usata dal processo `python` (Gestione attività / `top`).

Come leggere i numeri:
- `prima_risposta_audio_ms` sopra ~4000 in modo costante → prova `tts_engine = "browser"` (più rapido, qualità inferiore);
- `stt_ms` sopra ~3000 → resta su `base`, non passare a `small`;
- più di 2 frasi su 10 trascritte male → annota quali: si correggono con regole più tolleranti.

## 4. Voce italiana
Ascolta 2–3 risposte con `tts_voice = "if_sara"` e poi con `"im_nicola"` (riavvia dopo la modifica).
Valuta pronuncia e naturalezza da 1 a 5.

## 5. Cosa NON si prova ancora
Modelli (domande libere), altro PC, sincronizzazione, controllo remoto.
Se vuoi provare un modello locale: README → «Attivare un modello», poi chiedi a Jarvis «spiegami cos'è un Ryzen»
e annota `model_ms`.

## 6. Da riportarmi
Tabelle dei punti 0, 2, 3 e 4, eventuali errori copiati dal terminale (senza chiavi o dati personali).
