#!/usr/bin/env bash
# Installazione di Jarvis su Linux, senza privilegi di amministratore.
# Leggi prima cosa fa: crea .venv nella cartella del progetto, installa le dipendenze
# da PyPI, scarica Chromium (Playwright) e i modelli voce (~500 MB, hash verificati per Kokoro).
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
"$PY" -c 'import sys; assert sys.version_info >= (3, 11), "serve Python 3.11+"'

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
