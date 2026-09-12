$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "No .venv found. Run .\run.ps1 first to create the virtual environment."
}

& $pythonExe -m pip install -e "$projectRoot[dev]"
& $pythonExe -m PyInstaller --noconfirm --clean --windowed --name LamarckTranslator `
    --icon (Join-Path $projectRoot "assets\LamarckTranslator-icon.ico") `
    --add-data "$(Join-Path $projectRoot 'assets\LamarckTranslator-icon.png');assets" `
    --paths (Join-Path $projectRoot "src") `
    (Join-Path $projectRoot "launcher.py")
