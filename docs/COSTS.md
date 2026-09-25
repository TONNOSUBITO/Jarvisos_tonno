# Costi

**Fase 1: €0.** Nessun servizio a pagamento, nessuna chiamata a modelli. `budget_eur = 0` di default.

## Componenti
| Componente | Tipo | Costo | Verifica |
|---|---|---|---|
| Python, FastAPI, uvicorn, httpx, Playwright, Chromium | locale, open source | 0 | — |
| whisper.cpp (Fase 2) | locale, MIT | 0 (CPU/RAM del PC) | licenza da riconfermare all'integrazione |
| Kokoro-82M (Fase 2) | locale, pesi Apache | 0 | fonte: [HF hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), 25/09/2026 |
| Ollama + modello piccolo (Fase 3) | locale | 0; qwen3:1.7b 1,4 GB, qwen3:4b 2,5 GB di download | fonte: [ollama.com/library/qwen3](https://ollama.com/library/qwen3), 25/09/2026. Velocità su Ryzen 3: **non misurata** |
| OmniRoute (Fase 3) | gateway locale MIT (`npm install -g omniroute`, porta 20128, `/v1`) | gateway gratuito; **i provider dietro hanno quote e prezzi propri** | fonte: [github.com/diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute), 25/09/2026 |
| Fish Audio TTS (Fase 3, opt-in) | cloud | `s2.1-pro`: $15 / 1M byte UTF-8; `s2.1-pro-free`: $0 (fair use); 5 richieste concorrenti sotto $100 spesi | fonte: [docs.fish.audio – Pricing & Rate Limits](https://docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits), 25/09/2026 |
| TypeSafe Jev (Fase 3, opzionale) | cloud | **non verificato su fonte ufficiale**: fonti terze riportano $0,042 / M token in input | [pydantic.dev](https://pydantic.dev/docs/ai/models/typesafe/) non riporta prezzi |

Nota: i caratteri italiani accentati occupano 2 byte UTF-8 → pesano doppio sul conteggio Fish.

## Quote non garantite
«Gratis» di OmniRoute e dei provider free dipende da quote esterne che possono cambiare o sparire.
Non è «gratis illimitato» e non equivale a un abbonamento Claude. Fish `s2.1-pro-free` è soggetto a fair use.

## Budget e fallback (Fase 3)
- `[limits] budget_eur` = tetto per processo; ogni chiamata stima il costo e viene rifiutata se lo supera.
- `[model] allow_paid = false` blocca ogni provider marcato a pagamento.
- Fallback previsto: regole locali → modello locale (Ollama, se misurato accettabile) → gateway cloud solo se abilitato.
- Contatore consumi visibile in UI: da fare quando esisterà un provider reale.
