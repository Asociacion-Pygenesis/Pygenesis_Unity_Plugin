# Registra pygenesis-unity en Ollama desde el GGUF local.
# Uso (desde Tools\ollama):
#   powershell -File .\create_ollama_model.ps1

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$gguf = Join-Path $here "models\pygenesis-unity-q4km.gguf"
$modelfile = Join-Path $here "Modelfile.pygenesis-unity"

if (-not (Test-Path $modelfile)) {
    Write-Host "Generando Modelfile.pygenesis-unity..."
    python (Join-Path $here "write_modelfile_unity.py")
} else {
    # Siempre regenerar: evita tokens ChatML corruptos (p. ej. redacción accidental de im_end).
    Write-Host "Regenerando Modelfile.pygenesis-unity (tokens ChatML)..."
    python (Join-Path $here "write_modelfile_unity.py")
}

if (-not (Test-Path $gguf)) {
    Write-Error @"
No se encuentra el GGUF:
  $gguf

Copia tu modelo cuantizado a esa ruta (ver models\README.md).
"@
}

Write-Host "Creando modelo Ollama 'pygenesis-unity' desde $gguf ..."
ollama create pygenesis-unity -f $modelfile

Write-Host ""
Write-Host "Listo. Comprueba con:"
Write-Host "  ollama run pygenesis-unity `"Responde en una frase: listo`""
Write-Host ""
Write-Host "Backend (.env recomendado):"
Write-Host "  PYGENESIS_LLM_MODEL=pygenesis-unity"
Write-Host "  PYGENESIS_CHAT_PERSONA=modelfile"
Write-Host "  PYGENESIS_CHAT_DOMAIN_BLOCKS=off"
