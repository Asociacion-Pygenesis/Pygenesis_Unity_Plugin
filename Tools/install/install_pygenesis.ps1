#Requires -Version 5.1
<#
.SYNOPSIS
    Instalador PyGenesis — runtime local (backend + puente + modelo opcional).
.DESCRIPTION
    Copia Tools a la carpeta de runtime elegida, crea el venv Python e instala dependencias.
    Descarga el GGUF desde Hugging Face (SuNavar/Pygenesis-Unity) salvo -SkipModelDownload.
    Los binarios llama.cpp siguen siendo descarga manual.
.PARAMETER RuntimeRoot
    Carpeta destino (defecto: %USERPROFILE%\.pygenesis).
.PARAMETER SkipModelDownload
    No descargar el GGUF desde Hugging Face (útil si ya lo tienes local).
.EXAMPLE
    .\Tools\install\install_pygenesis.ps1
    .\Tools\install\install_pygenesis.ps1 -RuntimeRoot "D:\PyGenesis"
#>
param(
    [string]$RuntimeRoot = "",
    [switch]$SkipModelDownload
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step { param([int]$n, [int]$total, [string]$msg) Write-Host "`n[$n/$total] $msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$msg) Write-Host "  OK $msg" -ForegroundColor Green }
function Write-Warn { param([string]$msg) Write-Host "  ! $msg" -ForegroundColor Yellow }

$ScriptDir = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$ToolsSrc = Join-Path $RepoRoot "Tools"
$ManifestPath = Join-Path $ScriptDir "manifest.json"

if (-not (Test-Path $ManifestPath)) {
    throw "No se encontró manifest.json en $ScriptDir"
}
$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json

if ([string]::IsNullOrWhiteSpace($RuntimeRoot)) {
    $default = $manifest.runtime.default_root -replace "%USERPROFILE%", $env:USERPROFILE
    $RuntimeRoot = $default
}
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)

Write-Host ""
Write-Host "PyGenesis Installer v$($manifest.version)" -ForegroundColor Magenta
Write-Host "Runtime: $RuntimeRoot"
Write-Host "Repo:    $RepoRoot"
Write-Host ""

$totalSteps = 5

# 1 — Python
Write-Step 1 $totalSteps "Comprobando Python 3.10+"
$python = $null
foreach ($cmd in @("python", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            if ([int]$Matches[1] -ge 3 -and [int]$Matches[2] -ge 10) {
                $python = $cmd
                Write-OK $ver
                break
            }
        }
    } catch {}
}
if (-not $python) {
    throw "Python 3.10+ no encontrado. Instálalo desde https://python.org o con: winget install Python.Python.3.12"
}

# 2 — Copiar Tools
Write-Step 2 $totalSteps "Copiando backend e inferencia a $RuntimeRoot"
$backendDst = Join-Path $RuntimeRoot "pygenesis_backend"
$inferenceDst = Join-Path $RuntimeRoot "pygenesis_inference"

$robocopyArgs = @("/E", "/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np")
& robocopy (Join-Path $ToolsSrc "pygenesis_backend") $backendDst @robocopyArgs | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy backend falló ($LASTEXITCODE)" }
& robocopy (Join-Path $ToolsSrc "pygenesis_inference") $inferenceDst @robocopyArgs | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy inference falló ($LASTEXITCODE)" }
New-Item -ItemType Directory -Force -Path (Join-Path $inferenceDst "models") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $inferenceDst "bin") | Out-Null
Write-OK "Tools copiados"

# 3 — venv + pip
Write-Step 3 $totalSteps "Entorno virtual Python"
$venv = Join-Path $backendDst ".venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    & $python -m venv $venv
}
$pip = Join-Path $venv "Scripts\pip.exe"
$pyVenv = Join-Path $venv "Scripts\python.exe"
& $pip install --upgrade pip --quiet
& $pip install -r (Join-Path $backendDst "requirements.txt") --quiet
& $pip install huggingface-hub PyYAML --quiet
Write-OK "Dependencias instaladas"

# 4 — .env
Write-Step 4 $totalSteps "Configuración backend (.env)"
$envExample = Join-Path $backendDst ".env.example"
$envFile = Join-Path $backendDst ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-OK ".env creado desde .env.example"
} else {
    Write-Warn ".env ya existía; no se sobrescribe"
}

# 5 — Modelo GGUF (Hugging Face)
Write-Step 5 $totalSteps "Modelo GGUF (Hugging Face)"
$modelPath = Join-Path $inferenceDst "models\$($manifest.model.filename)"
$modelsDir = Join-Path $inferenceDst "models"
if ($SkipModelDownload) {
    Write-Warn "Omitido (-SkipModelDownload). Coloca el GGUF en: $modelPath"
} elseif (Test-Path $modelPath) {
    Write-OK "Modelo ya presente: $modelPath"
} else {
    $hfUrl = if ($manifest.model.hf_url) { $manifest.model.hf_url } else { "https://huggingface.co/$($manifest.model.repo_id)" }
    Write-Host "  Descargando $($manifest.model.filename) (~4,7 GB) desde $($manifest.model.repo_id)..." -ForegroundColor Gray
    Write-Host "  $hfUrl" -ForegroundColor Gray
    $hfCli = Join-Path $venv "Scripts\huggingface-cli.exe"
    if (-not (Test-Path $hfCli)) { $hfCli = "huggingface-cli" }
    $hfArgs = @(
        "download", $manifest.model.repo_id, $manifest.model.filename,
        "--local-dir", $modelsDir
    )
    if ($manifest.model.revision) {
        $hfArgs += @("--revision", $manifest.model.revision)
    }
    & $hfCli @hfArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Descarga HF falló. Descarga manual: huggingface-cli download $($manifest.model.repo_id) $($manifest.model.filename) --local-dir `"$modelsDir`""
    }
    if (-not (Test-Path $modelPath)) {
        throw "Descarga completada pero no se encontró: $modelPath"
    }
    Write-OK "Modelo descargado: $modelPath"
}

# config.json para Unity
$config = @{
    version     = $manifest.version
    runtime_root = $RuntimeRoot
    backend_url  = "http://127.0.0.1:$($manifest.runtime.backend_port)"
    bridge_url   = "http://127.0.0.1:$($manifest.runtime.bridge_public_port)/v1"
    model_path   = $modelPath
} | ConvertTo-Json -Depth 4
$configPath = Join-Path $RuntimeRoot "config.json"
$config | Set-Content -Path $configPath -Encoding UTF8

Write-Host ""
Write-Host "Instalación base completada." -ForegroundColor Green
Write-Host ""
Write-Host "Siguiente:" -ForegroundColor Cyan
Write-Host "  1. Binarios llama.cpp (Vulkan): ver $inferenceDst\bin\README.txt"
Write-Host "     ZIP: llama-bXXXX-bin-win-vulkan-x64.zip desde github.com/ggml-org/llama.cpp/releases"
Write-Host "  2. GGUF en models\ (el instalador puede haberlo descargado ya)"
Write-Host "  3. En Unity: PyGenesis → Open Assistant → Start Backend"
Write-Host "     (arranca puente :$($manifest.runtime.bridge_public_port) + backend :$($manifest.runtime.backend_port))"
Write-Host "  4. PyGenesis → Chat  |  Navegador: http://127.0.0.1:$($manifest.runtime.bridge_public_port)"
Write-Host ""
Write-Host "Unity Tools root (EditorPrefs): ejecuta en consola o Setup futuro:"
Write-Host "  PyGenesisRuntimePaths.SetToolsRoot(`"$RuntimeRoot`");" -ForegroundColor Gray
Write-Host "Config guardada en: $configPath"
