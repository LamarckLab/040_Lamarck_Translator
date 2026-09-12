$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Host "No .venv found, creating the virtual environment..."
    python -m venv (Join-Path $projectRoot ".venv")
    & $pythonExe -m pip install -e $projectRoot
}

& $pythonExe -m lamarck_translator

