# Primo test supervisionato sul PC

Obiettivo: verificare che la Fase 1 funzioni sul tuo PC reale **prima** di aggiungere voce e altri servizi.
Fallo su un solo PC. Il secondo solo dopo aver approvato il primo.

## 0. Annota il sistema
| Voce | Portatile | Fisso |
|---|---|---|
| Sistema operativo e versione (`winver` / `lsb_release -a`) | | |
| CPU esatta (Gestione attività → Prestazioni / `lscpu`) | | |
| RAM totale / libera a riposo | | |
| Browser preferito | | |
| Python (`python --version`) | | |

## 1. Installazione
Segui il README (sezione Installazione). Nessun comando richiede privilegi di amministratore.
Crea `config/device.toml` da `config/device.example.toml` e imposta:
- `device_id` ("portatile" o "fisso")
- `app_adapter = "native"` e 1–2 app innocue in `[apps]` (es. calcolatrice, blocco note)
- lascia `headless = false` per vedere il browser dedicato

## 2. Checklist
| # | Prova | Atteso | Esito |
|---|---|---|---|
| 1 | `pytest -q` (con `pip install -e ".[dev]"`) | tutti verdi | |
| 2 | `python -m jarvis`, apri http://127.0.0.1:8765 | UI visibile, dispositivo corretto | |
| 3 | `apri calcolatrice` | l'app si apre, stato «completato» | |
| 4 | `apri regedit` (non in lista) | rifiutato, nulla si apre | |
| 5 | `cerca e apri documentazione python` | si apre una finestra Chromium **separata** con il primo risultato | |
| 6 | Se il 5 non trova risultati | annota: il selettore DuckDuckGo va aggiornato | |
| 7 | `prepara una nota: prova` → Rifiuta | nessun file creato | |
| 8 | `prepara una nota: prova` → Conferma | file in `data/vault/inbox/`, apribile con Obsidian/editor | |
| 9 | durante il 5, premi **■ Stop** | attività «fermato», finestra browser chiusa | |
| 10 | elimina la nota dalla UI | file rimosso | |
| 11 | `data/audit.jsonl` | eventi presenti, nessun segreto | |
| 12 | RAM/CPU di `python` a riposo e durante il 5 | annota i valori | |

## 3. Cosa NON si prova ancora
Microfono, trascrizione, voce, modelli, altro PC: arrivano in Fase 2–4.

## 4. Da riportarmi
Tabella del punto 0, esiti della checklist, eventuali errori copiati dal terminale (senza chiavi o dati personali).
