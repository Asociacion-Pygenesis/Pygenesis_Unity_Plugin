#Requires -Version 5.1
<#
.SYNOPSIS
    Publica el ZIP de binarios llama.cpp en GitHub Releases (PyGenesis).
.DESCRIPTION
    1. Ejecuta build_llama_release_zip.ps1 (-UpdateManifest actualiza SHA256).
    2. Crea o actualiza el release con gh cli y sube el asset.

    Usa --repo del manifiesto (no depende del git remote local; puede ser GitLab).
    Requiere: gh autenticado en github.com con permiso de releases.
.PARAMETER Tag
    Tag del release (defecto: v0.2.0 desde llama_binaries_manifest.json).
.PARAMETER SkipBuild
    No regenerar el ZIP; usar el existente en Tools/install/dist/.
.PARAMETER Draft
    Crear el release como borrador.
.PARAMETER Repo
    Repositorio GitHub owner/name (defecto: github_repo del manifiesto).
.EXAMPLE
    .\publish_llama_release.ps1
    .\publish_llama_release.ps1 -SkipBuild
#>
param(
    [string]$Tag = "",
    [string]$Repo = "",
    [switch]$SkipBuild,
    [switch]$Draft
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$ManifestPath = Join-Path $ScriptDir "llama_binaries_manifest.json"
$llamaManifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json

$build = $llamaManifest.llama_build
$zipName = "pygenesis-llama-vulkan-win-x64-$build.zip"
$zipPath = Join-Path $ScriptDir "dist\$zipName"

if ([string]::IsNullOrWhiteSpace($Tag)) {
    $Tag = "v$($llamaManifest.pygenesis_release)"
}

if ([string]::IsNullOrWhiteSpace($Repo)) {
    $Repo = $llamaManifest.github_repo
    if ([string]::IsNullOrWhiteSpace($Repo) -and $llamaManifest.download.url -match 'github\.com/([^/]+/[^/]+)/') {
        $Repo = $Matches[1]
    }
}
if ([string]::IsNullOrWhiteSpace($Repo)) {
    throw "No se pudo determinar github_repo. Añádelo a llama_binaries_manifest.json o usa -Repo owner/name"
}

if (-not $SkipBuild) {
    $buildScript = Join-Path $ScriptDir "build_llama_release_zip.ps1"
    & $buildScript -UpdateManifest
    if ($LASTEXITCODE -ne 0) { throw "build_llama_release_zip.ps1 falló" }
}

if (-not (Test-Path $zipPath)) {
    throw "No se encontró el ZIP: $zipPath`nEjecuta build_llama_release_zip.ps1 primero."
}

$gh = $null
if (Get-Command gh -ErrorAction SilentlyContinue) {
    $gh = "gh"
} elseif (Test-Path "${env:ProgramFiles(x86)}\GitHub CLI\gh.exe") {
    $gh = "${env:ProgramFiles(x86)}\GitHub CLI\gh.exe"
} elseif (Test-Path "$env:ProgramFiles\GitHub CLI\gh.exe") {
    $gh = "$env:ProgramFiles\GitHub CLI\gh.exe"
}

if (-not $gh) {
    throw @"
GitHub CLI (gh) no está instalado o no está en PATH.
Subida manual:
  1. Abre https://github.com/$Repo/releases/new
  2. Tag: $Tag
  3. Sube: $zipPath
"@
}

$hash = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
$manifestHash = $llamaManifest.download.sha256
if (-not [string]::IsNullOrWhiteSpace($manifestHash) -and $manifestHash.ToLowerInvariant() -ne $hash) {
    throw "SHA256 del ZIP no coincide con el manifiesto.`nZIP:       $hash`nManifiesto: $manifestHash`nEjecuta build_llama_release_zip.ps1 -UpdateManifest"
}

Write-Host ""
Write-Host "Publicando release $Tag" -ForegroundColor Magenta
Write-Host "  Repo:  $Repo"
Write-Host "  Asset: $zipName ($([math]::Round((Get-Item $zipPath).Length / 1MB, 2)) MB)"
Write-Host "  SHA256: $hash"
Write-Host ""

$releaseNotes = @"
Binarios llama-server (Vulkan, Windows x64) para PyGenesis.

- Build llama.cpp: **$build**
- Archivos: $($llamaManifest.required_files.Count) (solo lo necesario para el puente PyGenesis)
- Instalación: ``PyGenesis → Setup → Descargar binarios Vulkan (automático)`` o ``install_llama_binaries.ps1``
"@

$ghArgs = @(
    "release", "create", $Tag,
    $zipPath,
    "--repo", $Repo,
    "--title", "PyGenesis llama.cpp $build (Vulkan)",
    "--notes", $releaseNotes
)
if ($Draft) {
    $ghArgs += "--draft"
}

& $gh @ghArgs
if ($LASTEXITCODE -ne 0) {
    $uploadHint = "gh release upload $Tag `"$zipPath`" --repo $Repo --clobber"
    throw "gh release create falló. ¿El tag $Tag ya existe? Prueba:`n  $uploadHint"
}

Write-Host ""
Write-Host "Release publicado." -ForegroundColor Green
Write-Host "  $($llamaManifest.download.url)"
Write-Host ""
