# Installazione di Jarvis su Windows, senza privilegi di amministratore.
# Esegui da PowerShell nella cartella del progetto:
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
# Cosa fa: crea .venv, installa le dipendenze da PyPI, scarica Chromium (Playwright)
# e i modelli voce (~500 MB, hash verificati per Kokoro). Non modifica il sistema.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# Serve Python 3.11, 3.12 o 3.13: la voce locale (kokoro-onnx) non supporta ancora 3.14.
# Cerca prima con il launcher "py" (sceglie tra più versioni installate), poi "python" nel PATH.
$okCheck = "import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 13) else 1)"
$py = $null; $ver = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
  foreach ($v in @("-3.13", "-3.12", "-3.11")) {
    & py $v -c $okCheck 2>$null
    if ($LASTEXITCODE -eq 0) { $py = "py"; $ver = @($v); break }
  }
}
if (-not $py -and (Get-Command python -ErrorAction SilentlyContinue)) {
  & python -c $okCheck 2>$null
  if ($LASTEXITCODE -eq 0) { $py = "python" }
}
if (-not $py) {
  throw "Serve Python 3.11, 3.12 o 3.13 (non 3.14). Installa Python 3.13 da https://www.python.org/downloads/ (spunta 'Add to PATH') e rilancia."
}
Write-Host "   uso: $py $ver"
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "Fallito: $what (codice $LASTEXITCODE)" } }

Write-Host "1/5 Ambiente virtuale .venv"
if (-not (Test-Path .venv)) { & $py @ver -m venv .venv; Check "creazione .venv" }
$vpy = ".\.venv\Scripts\python.exe"
& $vpy -c $okCheck; Check "versione Python della .venv (serve 3.11-3.13; elimina .venv se creata con un'altra versione)"
& $vpy -m pip install --upgrade pip | Out-Null

Write-Host "2/5 Dipendenze (voce locale inclusa)"
& $vpy -m pip install -e ".[voice,tts]"; Check "installazione dipendenze"

Write-Host "3/5 Chromium dedicato per Playwright"
& $vpy -m playwright install chromium; Check "download Chromium"

Write-Host "4/5 Configurazione"
if (-not (Test-Path config\device.toml)) {
  (Get-Content config\device.example.toml -Encoding UTF8) `
    -replace '^app_adapter = "mock"', 'app_adapter = "native"' `
    -replace '^tts_engine = "browser"', 'tts_engine = "kokoro"' `
    -replace '^# calcolatrice = \["calc.exe"\]', 'calcolatrice = ["calc.exe"]' `
    -replace '^# "blocco note" = \["notepad.exe"\]', '"blocco note" = ["notepad.exe"]' |
    Out-String | ForEach-Object {
      # UTF-8 senza BOM: Set-Content -Encoding UTF8 di PowerShell 5.1 aggiunge il BOM
      [System.IO.File]::WriteAllText((Join-Path (Get-Location) "config\device.toml"), $_, (New-Object System.Text.UTF8Encoding $false))
    }
  Write-Host "   creato config\device.toml (calcolatrice e blocco note approvate)"
}
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

Write-Host "5/5 Modelli voce"
& $vpy -m jarvis models; Check "download modelli voce"

& $vpy -m jarvis doctor
Write-Host "Fatto. Avvio: scripts\run.bat"
