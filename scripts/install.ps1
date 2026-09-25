# Installazione di Jarvis su Windows, senza privilegi di amministratore.
# Esegui da PowerShell nella cartella del progetto:
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
# Cosa fa: crea .venv, installa le dipendenze da PyPI, scarica Chromium (Playwright)
# e i modelli voce (~500 MB, hash verificati per Kokoro). Non modifica il sistema.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$py = "py"
try { & $py -3.11 -c "import sys" } catch { $py = "python" }
$ver = if ($py -eq "py") { @("-3.11") } else { @() }

Write-Host "1/5 Ambiente virtuale .venv"
if (-not (Test-Path .venv)) { & $py @ver -m venv .venv }
$vpy = ".\.venv\Scripts\python.exe"
& $vpy -c "import sys; assert sys.version_info >= (3, 11), 'serve Python 3.11+'"
& $vpy -m pip install --upgrade pip | Out-Null

Write-Host "2/5 Dipendenze (voce locale inclusa)"
& $vpy -m pip install -e ".[voice,tts]"

Write-Host "3/5 Chromium dedicato per Playwright"
& $vpy -m playwright install chromium

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
& $vpy -m jarvis models

& $vpy -m jarvis doctor
Write-Host "Fatto. Avvio: scripts\run.bat"
