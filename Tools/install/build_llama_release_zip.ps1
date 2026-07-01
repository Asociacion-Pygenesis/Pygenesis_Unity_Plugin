#Requires -Version 5.1
<#
.SYNOPSIS
    Empaqueta los binarios locales en el ZIP pre-filtrado para GitHub Releases.
.PARAMETER SourceBinDir
    Carpeta con llama-server.exe y DLL (defecto: Tools/pygenesis_inference/bin).
.PARAMETER OutputPath
    Ruta del .zip de salida (defecto: Tools/install/dist/pygenesis-llama-vulkan-win-x64-<build>.zip).
.PARAMETER UpdateManifest
    Escribe el SHA256 calculado en llama_binaries_manifest.json (Tools/install y copia del plugin).
.EXAMPLE
    .\build_llama_release_zip.ps1
    .\build_llama_release_zip.ps1 -UpdateManifest
#>
param(
    [string]$SourceBinDir = "",
    [string]$OutputPath = "",
    [switch]$UpdateManifest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Update-ManifestSha256 {
    param(
        [string]$Hash,
        [string]$ManifestPath,
        [string]$RepoRoot
    )

    $paths = @(
        $ManifestPath,
        (Join-Path $RepoRoot "Packages\com.pygenesis.plugin\Editor\llama_binaries_manifest.json")
    )

    foreach ($path in $paths) {
        if (-not (Test-Path $path)) { continue }
        $raw = Get-Content $path -Raw
        $updated = $raw -replace '"sha256"\s*:\s*"[^"]*"', ('"sha256": "' + $Hash + '"')
        if ($updated -eq $raw) {
            Write-Warning "No se pudo actualizar sha256 en $path"
            continue
        }
        Set-Content -Path $path -Value $updated -Encoding UTF8 -NoNewline
        Write-Host "  actualizado: $path" -ForegroundColor Gray
    }
}

$ScriptDir = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$ManifestPath = Join-Path $ScriptDir "llama_binaries_manifest.json"

if (-not (Test-Path $ManifestPath)) {
    throw "No se encontró $ManifestPath"
}

$llamaManifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$build = $llamaManifest.llama_build
$required = @($llamaManifest.required_files)

if ([string]::IsNullOrWhiteSpace($SourceBinDir)) {
    $SourceBinDir = Join-Path $RepoRoot "Tools\pygenesis_inference\bin"
}
$SourceBinDir = [System.IO.Path]::GetFullPath($SourceBinDir)

if (-not (Test-Path $SourceBinDir)) {
    throw "No existe la carpeta origen: $SourceBinDir"
}

$missing = @()
foreach ($name in $required) {
    if (-not (Test-Path (Join-Path $SourceBinDir $name))) {
        $missing += $name
    }
}
if ($missing.Count -gt 0) {
    throw "Faltan archivos en $SourceBinDir : $($missing -join ', ')"
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $distDir = Join-Path $ScriptDir "dist"
    New-Item -ItemType Directory -Force -Path $distDir | Out-Null
    $OutputPath = Join-Path $distDir "pygenesis-llama-vulkan-win-x64-$build.zip"
}
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)

$staging = Join-Path ([System.IO.Path]::GetTempPath()) ("pygenesis_zip_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $staging | Out-Null

try {
    foreach ($name in $required) {
        Copy-Item (Join-Path $SourceBinDir $name) (Join-Path $staging $name)
    }

    if (Test-Path $OutputPath) {
        Remove-Item -Force $OutputPath
    }

    Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $OutputPath -Force

    $hash = (Get-FileHash -Path $OutputPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $sizeMb = [math]::Round((Get-Item $OutputPath).Length / 1MB, 2)

    Write-Host ""
    Write-Host "ZIP creado:" -ForegroundColor Green
    Write-Host "  $OutputPath"
    Write-Host "  Tamaño: ${sizeMb} MB"
    Write-Host "  SHA256: $hash"
    Write-Host ""

    if ($UpdateManifest) {
        Update-ManifestSha256 -Hash $hash -ManifestPath $ManifestPath -RepoRoot $RepoRoot
        Write-Host "Manifiestos actualizados con SHA256." -ForegroundColor Green
        Write-Host ""
    } else {
        Write-Host "Tip: añade -UpdateManifest para escribir el hash en llama_binaries_manifest.json" -ForegroundColor Cyan
        Write-Host ""
    }
}
finally {
    if (Test-Path $staging) {
        Remove-Item -Recurse -Force $staging -ErrorAction SilentlyContinue
    }
}
