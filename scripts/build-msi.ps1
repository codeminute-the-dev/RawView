# Build PyInstaller layout, then compile a per-user MSI with WiX Toolset 3.11+.
# Prereq: https://wixtoolset.org/docs/wix3/ (install "WiX Toolset Build Tools" and ensure bin is on PATH,
#          or set WIX to the install root, e.g. C:\Program Files (x86)\WiX Toolset v3.14\)
#
# Usage (repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\build-msi.ps1
param(
    [switch]$SkipPyInstaller
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$packagingWix = Join-Path $Root "packaging\wix"
$DistApp = Join-Path $Root "dist\RawView"
$OutDir = Join-Path $Root "dist_installer"
$HarvestWxs = Join-Path $packagingWix "_Harvest.wxs"
$ObjDir = Join-Path $packagingWix "obj"

function Test-UsablePythonExe([string]$Exe) {
    if (-not $Exe) { return $false }
    if ($Exe -match '\\WindowsApps\\') { return $false }
    if (-not (Test-Path -LiteralPath $Exe)) { return $false }
    & $Exe -c "import sys" *> $null
    return $LASTEXITCODE -eq 0
}

function Find-PythonExe {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($ver in @("3.12", "3.11", "3")) {
            try {
                $exe = (& py "-$ver" -c "import sys; print(sys.executable)" 2>$null)
                $exe = ($exe | Out-String).Trim()
                if (Test-UsablePythonExe $exe) { return $exe }
            } catch { }
        }
    }
    foreach ($p in @(
            "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
            "C:\Python312\python.exe",
            "C:\Python311\python.exe"
        )) {
        if (Test-UsablePythonExe $p) { return $p }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $c = (Get-Command python).Source
        if (Test-UsablePythonExe $c) { return $c }
    }
    return $null
}

function Find-WixBin {
    if ($env:WIX) {
        $b = Join-Path $env:WIX.TrimEnd("\") "bin"
        if (Test-Path (Join-Path $b "heat.exe")) { return $b }
    }
    foreach ($ver in @("3.14", "3.13", "3.12", "3.11")) {
        $b = Join-Path ${env:ProgramFiles(x86)} "WiX Toolset v$ver\bin"
        if (Test-Path (Join-Path $b "heat.exe")) { return $b }
    }
    return $null
}

Write-Host "== RawView MSI build ==" -ForegroundColor Cyan
Write-Host "Root: $Root"

if (-not $SkipPyInstaller) {
    & (Join-Path $Root "scripts\build-windows.ps1")
}

if (-not (Test-Path (Join-Path $DistApp "RawView.exe"))) {
    Write-Error "Missing dist\RawView\RawView.exe - run PyInstaller first (omit -SkipPyInstaller)."
}

$pythonExe = Find-PythonExe
if (-not $pythonExe) {
    Write-Error "Python is required to generate packaging/wix/License.rtf from the repository LICENSE file."
}
$genLic = Join-Path $Root "packaging\scripts\generate_license_rtf.py"
Write-Host "License.rtf: generate from LICENSE ..." -ForegroundColor Cyan
& $pythonExe $genLic --root $Root
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$bin = Find-WixBin
if (-not $bin) {
    Write-Error @"
WiX Toolset 3.x 'bin' folder not found.
Install from https://github.com/wixtoolset/wix3/releases (e.g. wix314.exe) or WiX builds page,
then either add ...\WiX Toolset v3.14\bin to PATH or set environment variable WIX to the toolkit root.
"@
}

$heat = Join-Path $bin "heat.exe"
$candle = Join-Path $bin "candle.exe"
$light = Join-Path $bin "light.exe"

Write-Host "Using WiX: $bin" -ForegroundColor DarkGray

if (Test-Path $ObjDir) { Remove-Item -Recurse -Force $ObjDir }
New-Item -ItemType Directory -Path $ObjDir | Out-Null
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

Write-Host "Heat: harvesting dist\RawView ..." -ForegroundColor Cyan
& $heat dir $DistApp `
    -cg Harvested `
    -dr INSTALLFOLDER `
    -gg `
    -sfrag `
    -srd `
    -scom `
    -sreg `
    -var var.SourceDir `
    -out $HarvestWxs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$productWxs = Join-Path $packagingWix "Product.wxs"
$sourceDirFull = (Resolve-Path $DistApp).Path

Push-Location $packagingWix
try {
    Write-Host "Candle ..." -ForegroundColor Cyan
    & $candle -nologo -arch x64 `
        "-dSourceDir=$sourceDirFull" `
        -out ($ObjDir + "\") `
        $productWxs `
        $HarvestWxs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $msiName = "RawView-0.1.0.msi"
    $msiPath = Join-Path $OutDir $msiName
    Write-Host "Light -> $msiPath" -ForegroundColor Cyan
    # ICE38: per-user profile installs normally need HKCU registry KeyPaths; Heat emits file KeyPaths.
    # ICE91: per-user dirs vs ALLUSERS (expected for this layout).
    & $light -nologo `
        -ext WixUIExtension `
        -cultures:en-us `
        -sice:ICE38 `
        -sice:ICE64 `
        -sice:ICE91 `
        -out $msiPath `
        (Join-Path $ObjDir "Product.wixobj") `
        (Join-Path $ObjDir "_Harvest.wixobj")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

Write-Host "Done: $msiPath" -ForegroundColor Green
