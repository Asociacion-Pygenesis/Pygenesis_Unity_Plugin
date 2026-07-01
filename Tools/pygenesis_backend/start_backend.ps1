# Backend PyGenesis. Variables opcionales: $env:PYGENESIS_REASONING, $env:OPENAI_API_KEY — ver README.md
param(
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Error "No se encontro el interprete del entorno virtual: $pythonExe"
}

Write-Host "Iniciando backend con: $pythonExe"
& $pythonExe -m uvicorn main:app --host 127.0.0.1 --port 8765

if (-not $NoPause) {
    Read-Host "Pulsa Enter para cerrar"
}
