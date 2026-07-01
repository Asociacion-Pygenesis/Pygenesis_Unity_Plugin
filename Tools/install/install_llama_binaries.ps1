#Requires -Version 5.1
<#
.SYNOPSIS
    Descarga e instala binarios llama-server (Vulkan, Windows x64) en pygenesis_inference/bin/.
.DESCRIPTION
    Usa el ZIP pre-filtrado PyGenesis del manifiesto llama_binaries_manifest.json.
    Si la descarga principal falla, intenta el ZIP oficial de llama.cpp y copia solo los archivos requeridos.
.PARAMETER RuntimeRoot
    Carpeta runtime (pygenesis_inference/bin/ debajo). Por defecto %USERPROFILE%\.pygenesis.
.PARAMETER BinDir
    Destino explícito para bin/ (tiene prioridad sobre RuntimeRoot).
.PARAMETER ManifestPath
    Ruta al manifiesto JSON (defecto: junto a este script).
.PARAMETER Force
    Descargar aunque llama-server.exe ya exista.
.EXAMPLE
    .\install_llama_binaries.ps1
    .\install_llama_binaries.ps1 -BinDir "D:\PyGenesis\pygenesis_inference\bin"
#>
param(
    [string]$RuntimeRoot = "",
    [string]$BinDir = "",
    [string]$ManifestPath = "",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-OK   { param([string]$msg) Write-Host "  OK $msg" -ForegroundColor Green }
function Write-Warn { param([string]$msg) Write-Host "  ! $msg" -ForegroundColor Yellow }

$ScriptDir = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    $ManifestPath = Join-Path $ScriptDir "llama_binaries_manifest.json"
}
if (-not (Test-Path $ManifestPath)) {
    throw "No se encontró manifiesto: $ManifestPath"
}

$llamaManifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$required = @($llamaManifest.required_files)
if ($required.Count -eq 0) {
    throw "El manifiesto no define required_files."
}

if ([string]::IsNullOrWhiteSpace($BinDir)) {
    if ([string]::IsNullOrWhiteSpace($RuntimeRoot)) {
        $RuntimeRoot = Join-Path $env:USERPROFILE ".pygenesis"
    }
    $RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
    $BinDir = Join-Path $RuntimeRoot "pygenesis_inference\bin"
} else {
    $BinDir = [System.IO.Path]::GetFullPath($BinDir)
}

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$serverExe = Join-Path $BinDir "llama-server.exe"
if ((Test-Path $serverExe) -and -not $Force) {
    $missing = @()
    foreach ($name in $required) {
        if (-not (Test-Path (Join-Path $BinDir $name))) {
            $missing += $name
        }
    }
    if ($missing.Count -eq 0) {
        Write-Host ""
        Write-Host "Binarios llama.cpp $($llamaManifest.llama_build) ya presentes en:" -ForegroundColor Green
        Write-Host "  $BinDir"
        Write-Host ""
        & $serverExe @($llamaManifest.verify_command)
        exit 0
    }
    Write-Warn "Instalación incompleta ($($missing.Count) faltantes); continuando descarga…"
}

Write-Host ""
Write-Host "PyGenesis — binarios llama.cpp $($llamaManifest.llama_build) (Vulkan)" -ForegroundColor Magenta
Write-Host "Destino: $BinDir"
Write-Host ""

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("pygenesis_llama_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
$zipPath = Join-Path $tempRoot "llama-binaries.zip"
$extractDir = Join-Path $tempRoot "extract"

try {
    $primaryUrl = $llamaManifest.download.url
    $downloaded = $false

    if (-not [string]::IsNullOrWhiteSpace($primaryUrl)) {
        Write-Host "[1/4] Descargando ZIP PyGenesis…" -ForegroundColor Cyan
        Write-Host "  $primaryUrl" -ForegroundColor Gray
        try {
            Invoke-WebRequest -Uri $primaryUrl -OutFile $zipPath -UseBasicParsing
            $downloaded = $true
            Write-OK "Descarga completada"
        } catch {
            Write-Warn "Descarga PyGenesis falló: $($_.Exception.Message)"
        }
    }

    if (-not $downloaded -and $llamaManifest.fallback -and $llamaManifest.fallback.url) {
        $fallbackUrl = $llamaManifest.fallback.url
        Write-Host "[1/4] Descargando ZIP oficial llama.cpp (fallback)…" -ForegroundColor Cyan
        Write-Host "  $fallbackUrl" -ForegroundColor Gray
        if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
        Invoke-WebRequest -Uri $fallbackUrl -OutFile $zipPath -UseBasicParsing
        $downloaded = $true
        Write-OK "Descarga completada"
    }

    if (-not $downloaded) {
        throw @"
No se pudo descargar binarios.
Publica el release PyGenesis o añade fallback.url en llama_binaries_manifest.json.
URL principal: $primaryUrl
"@
    }

    $expectedHash = $llamaManifest.download.sha256
    if (-not [string]::IsNullOrWhiteSpace($expectedHash)) {
        Write-Host "[2/4] Verificando SHA256…" -ForegroundColor Cyan
        $actualHash = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash.ToLowerInvariant()) {
            throw "SHA256 no coincide.`nEsperado: $expectedHash`nObtenido:  $actualHash"
        }
        Write-OK "Hash verificado"
    } else {
        Write-Host "[2/4] SHA256 omitido (vacío en manifiesto)" -ForegroundColor Gray
    }

    Write-Host "[3/4] Extrayendo archivos requeridos…" -ForegroundColor Cyan
    Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

    $copied = 0
    foreach ($name in $required) {
        $found = Get-ChildItem -Path $extractDir -Recurse -File -Filter $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $found) {
            throw "No se encontró '$name' dentro del ZIP."
        }
        Copy-Item -Path $found.FullName -Destination (Join-Path $BinDir $name) -Force
        $copied++
    }
    Write-OK "$copied archivos copiados a bin/"

    Write-Host "[4/4] Comprobando llama-server…" -ForegroundColor Cyan
    $stillMissing = @()
    foreach ($name in $required) {
        if (-not (Test-Path (Join-Path $BinDir $name))) {
            $stillMissing += $name
        }
    }
    if ($stillMissing.Count -gt 0) {
        throw "Tras la instalación faltan: $($stillMissing -join ', ')"
    }

    $versionOut = & $serverExe @($llamaManifest.verify_command) 2>&1 | Out-String
    Write-OK "llama-server responde"
    if ($versionOut.Trim()) {
        Write-Host $versionOut.Trim() -ForegroundColor Gray
    }

    Write-Host ""
    Write-Host "Instalación de binarios completada." -ForegroundColor Green
    Write-Host "  $BinDir"
    Write-Host ""
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -Recurse -Force $tempRoot -ErrorAction SilentlyContinue
    }
}
