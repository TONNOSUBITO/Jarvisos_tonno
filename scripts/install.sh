#!/usr/bin/env bash
# Installazione di Jarvis su Linux, senza privilegi di amministratore.
# Leggi prima cosa fa: crea .venv nella cartella del progetto, installa le dipendenze
# da PyPI, scarica Chromium (Playwright) e i modelli voce (~500 MB, hash verificati per Kokoro).
set -euo pipefail
cd "$(dirname "$0")/.."

# Serve Python 3.11–3.13: la voce locale (kokoro-onnx) non supporta ancora 3.14.
OK='import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 13) else 1)'
PY=${PYTHON:-}
if [ -z "$PY" ]; then
  for c in python3.13 python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null && "$c" -c "$OK"; then PY=$c; break; fi
  done
fi
[ -n "$PY" ] && "$PY" -c "$OK" || { echo "Serve Python 3.11, 3.12 o 3.13 (non 3.14)"; exit 1; }

echo "1/5 Ambiente virtuale .venv"
[ -d .venv ] || "$PY" -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip >/dev/null

echo "2/5 Dipendenze (voce locale inclusa)"
pip install -e ".[voice,tts]"

echo "3/5 Chromium dedicato per Playwright (nella cache utente, non tocca il tuo browser)"
python -m playwright install chromium

echo "4/5 Configurazione"
if [ ! -f config/device.toml ]; then
  cp config/device.example.toml config/device.toml
  sed -i 's/^app_adapter = "mock"/app_adapter = "native"/; s/^tts_engine = "browser"/tts_engine = "kokoro"/' config/device.toml
  echo "   creato config/device.toml: aggiungi le tue app in [apps]"
fi
[ -f .env ] || cp .env.example .env

echo "5/5 Modelli voce"
python -m jarvis models

python -m jarvis doctor || true
echo "Fatto. Avvio: scripts/run.sh"
