# Arranca llama-server (interno) + proxy con filtro de citas (puerto público / Web UI)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location $Root



$ConfigPath = Join-Path $Root "model_config.yaml"

if (-not (Test-Path $ConfigPath)) {

    Write-Error "No se encontró model_config.yaml en $Root"

}



$py = Join-Path $Root "..\pygenesis_backend\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {

    $py = "python"

}



$dumpScript = Join-Path $Root "dump_launch_info.py"

$infoJson = & $py $dumpScript $ConfigPath 2>&1

if ($LASTEXITCODE -ne 0) {

    Write-Error $infoJson

}

$j = $infoJson | ConvertFrom-Json



$gguf = $j.gguf

if (-not (Test-Path $gguf)) {

    Write-Error @"

GGUF no encontrado: $gguf

Descarga pygenesis-unity-q4km.gguf desde https://huggingface.co/SuNavar/Pygenesis-Unity
o ejecuta Tools\install\install_pygenesis.ps1

"@

}



$server = $j.llama_server

if (-not (Test-Path $server)) {

    Write-Error @"

llama-server no encontrado: $server

Descarga llama-win-vulkan-x64 desde https://github.com/ggml-org/llama.cpp/releases

y coloca los binarios en Tools/pygenesis_inference/bin/ (ver bin/README.txt)

"@

}



$publicPort = [int]$j.port

$internalPort = [int]$j.internal_port

$upstream = "http://$($j.host):$internalPort"



Write-Host "[PyGenesis] llama-server interno: $upstream"

Write-Host "[PyGenesis] Web UI + API públicos: http://$($j.host):$publicPort (proxy con filtro [Fuente…])"

Write-Host "[PyGenesis] System prompt: ui_config.json (navegador) y backend bridge (plugin)"

Write-Host "[PyGenesis] Si la Web UI se comporta raro, usa «Reset to default» para recargar ui_config.json"



$serverArgs = @(

    "--model", $gguf,

    "--host", $j.host,

    "--port", $internalPort,

    "--ctx-size", $j.sampling.num_ctx,

    "--n-predict", $j.sampling.num_predict,

    "--temp", $j.sampling.temperature,

    "--top-p", $j.sampling.top_p,

    "--repeat-penalty", $j.sampling.repeat_penalty,

    "--threads", $j.threads,

    "--n-gpu-layers", $j.n_gpu_layers,

    "--chat-template", "chatml",

    "--reasoning", "off"

)



if ($j.ui_config -and (Test-Path $j.ui_config)) {

    $serverArgs += @("--ui-config-file", $j.ui_config)

}



$proxyScript = Join-Path $Root "citation_proxy.py"

$llamaProc = $null



try {

    $llamaProc = Start-Process -FilePath $server -ArgumentList $serverArgs -PassThru -WindowStyle Hidden

    Start-Sleep -Seconds 2

    if ($llamaProc.HasExited) {

        Write-Error "llama-server terminó al arrancar (código $($llamaProc.ExitCode))"

    }

    & $py $proxyScript --host $j.host --port $publicPort --upstream $upstream

}

finally {

    if ($null -ne $llamaProc -and -not $llamaProc.HasExited) {

        Stop-Process -Id $llamaProc.Id -Force -ErrorAction SilentlyContinue

    }

}


