$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Host "未找到 .venv，正在创建虚拟环境..."
    python -m venv (Join-Path $projectRoot ".venv")
    & $pythonExe -m pip install -e $projectRoot
}

& $pythonExe -m lamarck_translator

