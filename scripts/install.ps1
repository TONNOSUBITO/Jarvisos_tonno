# Installazione di Jarvis su Windows, senza privilegi di amministratore.
# Esegui da PowerShell nella cartella del progetto:
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
# Cosa fa: crea .venv, installa le dipendenze da PyPI, scarica Chromium (Playwright)
# e i modelli voce (~500 MB, hash verificati per Kokoro). Non modifica il sistema.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# Usa il launcher "py -3" se presente, altrimenti "python" nel PATH.
$py = "python"; $ver = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3 -c "import sys" 2>$null
  if ($LASTEXITCODE -eq 0) { $py = "py"; $ver = @("-3") }
}
if (-not (Get-Command $py -ErrorAction SilentlyContinue)) {
  throw "Python non trovato. Installa Python 3.11+ da https://www.python.org/downloads/ (spunta 'Add to PATH')."
}
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "Fallito: $what (codice $LASTEXITCODE)" } }

Write-Host "1/5 Ambiente virtuale .venv"
if (-not (Test-Path .venv)) { & $py @ver -m venv .venv; Check "creazione .venv" }
$vpy = ".\.venv\Scripts\python.exe"
& $vpy -c "import sys; assert sys.version_info >= (3, 11), 'serve Python 3.11+'"; Check "versione Python"
& $vpy -m pip install --upgrade pip | Out-Null

Write-Host "2/5 Dipendenze (voce locale inclusa)"
& $vpy -m pip install -e ".[voice,tts]"; Check "installazione dipendenze"

Write-Host "3/5 Chromium dedicato per Playwright"
& $vpy -m playwright install chromium; Check "download Chromium"

Write-Host "4/5 Configurazione"
if (-not (Test-Path config\device.toml)) {
  (Get-Content config\device.example.toml) `
    -replace '^app_adapter = "mock"', 'app_adapter = "native"' `
    -replace '^tts_engine = "browser"', 'tts_engine = "kokoro"' `
    -replace '^# calcolatrice = \["calc.exe"\]', 'calcolatrice = ["calc.exe"]' `
    -replace '^# "blocco note" = \["notepad.exe"\]', '"blocco note" = ["notepad.exe"]' |
    Set-Content config\device.toml -Encoding UTF8
  Write-Host "   creato config\device.toml (calcolatrice e blocco note approvate)"
}
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

Write-Host "5/5 Modelli voce"
& $vpy -m jarvis models; Check "download modelli voce"

& $vpy -m jarvis doctor
Write-Host "Fatto. Avvio: scripts\run.bat"
