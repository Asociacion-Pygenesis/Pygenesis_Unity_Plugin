# Ejemplo: servidor OpenAI-compatible (vLLM) apuntando a la carpeta PygenesisAI del repo.
# Requisitos: vLLM instalado, GPU y stack compatibles con Qwen3.5 (ver documentación de vLLM).
# Uso: ejecutar desde Tools/pygenesis_backend o ajustar la ruta del modelo.

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$modelPath = Resolve-Path (Join-Path $here "..\..\PygenesisAI")

Write-Host "Model path: $modelPath"
Write-Host "Ejemplo de arranque (ajusta puerto / flags según tu instalación de vLLM):"
Write-Host ""
Write-Host @"
python -m vllm.entrypoints.openai.api_server ``
  --model `"$modelPath`" ``
  --served-model-name pygenesis-ai ``
  --host 127.0.0.1 --port 8000 ``
  --trust-remote-code
"@
