# Costi

**Configurazione predefinita: €0.** Voce locale, nessun modello, nessun servizio a pagamento, `budget_eur = 0`.
Si spende solo se abiliti tu un provider marcato `paid = true` **e** `allow_paid = true` **e** alzi `budget_eur`.

## Componenti
| Componente | Tipo | Costo | Verifica |
|---|---|---|---|
| Python, FastAPI, uvicorn, httpx, Playwright, Chromium | locale, open source | 0 | — |
| faster-whisper 1.2.1 (default STT) | locale, MIT | 0; modello `base` ~145 MB | licenza da PyPI, 25/09/2026 |
| kokoro-onnx 0.6.1 | locale, MIT (codice) + Apache 2.0 (modello) | 0; 325 MB + 28 MB (esiste variante int8 da 114 MB, non ancora usata) | [github.com/thewh1teagle/kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx), 25/09/2026 |
| Kokoro-82M (Fase 2) | locale, pesi Apache | 0 | fonte: [HF hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), 25/09/2026 |
| Ollama + modello piccolo | locale | 0, ma sul 3200U **troppo lento** (qwen3:1.7b >5 min/risposta su 2 core in cloud); qwen3:1.7b 1,4 GB, qwen3:4b 2,5 GB di download | fonte: [ollama.com/library/qwen3](https://ollama.com/library/qwen3), 25/09/2026. Velocità su Ryzen 3: **non misurata** |
| OmniRoute (Fase 3) | gateway locale MIT (`npm install -g omniroute`, porta 20128, `/v1`) | gateway gratuito; **i provider dietro hanno quote e prezzi propri** | fonte: [github.com/diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute), 25/09/2026 |
| TypeSafe Jev (router opzionale, `[router] engine = "rules+jev"`) | cloud | $0,042 per milione di token in input, output gratis; ~300 token a comando non capito dalle regole | [docs.typesafe.ai/models](https://docs.typesafe.ai/models), 26/09/2026 |


## Quote non garantite
«Gratis» di OmniRoute e dei provider free dipende da quote esterne che possono cambiare o sparire.
Non è «gratis illimitato» e non equivale a un abbonamento Claude.

## Budget e fallback
- `[limits] budget_eur` = tetto per processo; ogni chiamata stima il costo e viene rifiutata se lo supera.
- `[model] allow_paid = false` blocca ogni provider marcato a pagamento.
- Ordine: regole locali (gratis, sempre prima) → provider cloud nell'ordine di `[[model.providers]]`, solo se abilitati.
- Groq, Cerebras, Gemini, Mistral, OpenRouter (`:free`), Cohere (trial) e Hugging Face (crediti mensili) hanno piani gratuiti con limiti: verifica i termini attuali sul loro sito.
- NVIDIA (crediti non verificati), Together (crediti che scadono), Anthropic, DeepSeek, Fireworks, OpenAI (`gpt-6-luna` 0,1/0,5 $ per M token) e xAI (`grok-4.3` da 1,25/2,50 $ per M token) sono marcati `paid = true` in `config/providers.example.toml`.
- Contatore spesa in UI (`spesa: x / limite €`), calcolato dai token restituiti dal provider × i prezzi che imposti in `[[model.providers]]`. Se il provider non restituisce i token, la spesa risulta 0: non è una garanzia.
- Un provider `paid = true` viene bloccato appena la spesa raggiunge il limite.
