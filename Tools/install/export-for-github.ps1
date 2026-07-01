#Requires -Version 5.1
param(
    [string]$GitHubRemote = "https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin.git",
    [string]$Branch = "main",
    [string]$ExportDir = "",
    [string]$Version = "",
    [string]$CommitMessage = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$installManifest = Join-Path $PSScriptRoot "manifest.json"
if ([string]::IsNullOrWhiteSpace($Version) -and (Test-Path $installManifest)) {
    $Version = (Get-Content $installManifest -Raw | ConvertFrom-Json).version
}
if ([string]::IsNullOrWhiteSpace($Version)) { $Version = "0.2.0" }

if ([string]::IsNullOrWhiteSpace($CommitMessage)) {
    $CommitMessage = "release: PyGenesis v$Version (Setup, binarios Vulkan b9694, instalador)"
}

if ([string]::IsNullOrWhiteSpace($ExportDir)) {
    $ExportDir = Join-Path $env:TEMP "Pygenesis_Unity_Plugin_export"
}

$include = @(
    "Packages/com.pygenesis.plugin",
    "Tools/pygenesis_backend",
    "Tools/pygenesis_inference",
    "Tools/ollama",
    "Tools/install",
    "docs",
    "README.md",
    "LICENSE",
    "manifest.json",
    ".gitignore"
)

Write-Host "[export] Origen:   $RepoRoot"
Write-Host "[export] Destino:  $ExportDir"
Write-Host "[export] GitHub:   $GitHubRemote ($Branch)"
Write-Host "[export] Version:  $Version"
Write-Host "[export] Commit:   $CommitMessage"
Write-Host ""

if (Test-Path $ExportDir) {
    Remove-Item -Recurse -Force $ExportDir
}
New-Item -ItemType Directory -Force -Path $ExportDir | Out-Null

foreach ($rel in $include) {
    $src = Join-Path $RepoRoot $rel
    if (-not (Test-Path $src)) {
        Write-Warning "Omitido (no existe): $rel"
        continue
    }
    $dst = Join-Path $ExportDir $rel
    $parent = Split-Path $dst -Parent
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    if (Test-Path $src -PathType Container) {
        Copy-Item -Path $src -Destination $dst -Recurse -Force
    } else {
        Copy-Item -Path $src -Destination $dst -Force
    }
    Write-Host "  + $rel"
}

$prune = @(
    (Join-Path $ExportDir "Tools\pygenesis_backend\.venv"),
    (Join-Path $ExportDir "Tools\pygenesis_backend\.env"),
    (Join-Path $ExportDir "Tools\pygenesis_inference\ui_config.json"),
    (Join-Path $ExportDir "Tools\pygenesis_inference\system_prompt.txt"),
    (Join-Path $ExportDir "Tools\install\dist")
)
foreach ($p in $prune) {
    if (Test-Path $p) { Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue }
}

Get-ChildItem -Path (Join-Path $ExportDir "Tools\pygenesis_inference\models") -Filter "*.gguf" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -Path (Join-Path $ExportDir "Tools\pygenesis_inference\bin") -Include "*.exe","*.dll" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -Path (Join-Path $ExportDir "Tools\ollama\models") -Filter "*.gguf" -ErrorAction SilentlyContinue | Remove-Item -Force

Push-Location $ExportDir
try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "git no está en el PATH"
    }
    git init -b $Branch
    git add -A
    git -c user.name="Asociacion PyGenesis" -c user.email="info@pygenesis.org" commit -m $CommitMessage
    $remotes = git remote 2>$null
    if ($remotes -contains "origin") { git remote remove origin }
    git remote add origin $GitHubRemote
    git push -u origin $Branch --force
    if ($LASTEXITCODE -ne 0) { throw "git push falló (código $LASTEXITCODE)" }
    Write-Host ""
    Write-Host "[export] Push completado: $GitHubRemote ($Branch)" -ForegroundColor Green
    Write-Host "[export] https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin" -ForegroundColor Green
} finally {
    Pop-Location
}
