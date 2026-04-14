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

$distJavaMarker = Join-Path $DistApp "_internal\rawview\java\out\io\rawview\ghidra\GhidraServer.class"
if (-not (Test-Path -LiteralPath $distJavaMarker)) {
    $hint = if ($SkipPyInstaller) {
        "You used -SkipPyInstaller but the existing dist layout has no bundled Java classes. Re-run without -SkipPyInstaller after compiling, or rebuild PyInstaller."
    } else {
        "Set GHIDRA_INSTALL_DIR to your Ghidra install root, ensure JDK javac is on PATH, then from the repo root run:  python -m rawview.scripts.compile_java`nRe-run this script so PyInstaller picks up rawview/java/out."
    }
    Write-Error @"
MSI build aborted: Ghidra Java bridge is not bundled under dist\RawView\_internal\rawview\java\out\.
$hint
"@
}

$pythonExe = Find-PythonExe
if (-not $pythonExe) {
    Write-Error "Python is required to install project deps, record pip freeze, and generate packaging/wix/License.rtf."
}

# PyInstaller already embeds these packages under _internal; there is no pip on the end-user machine.
# We still pip install from pyproject here so the build matches declared deps, then ship a freeze manifest next to RawView.exe.
Write-Host "pip: install project + dev (pyproject) ..." -ForegroundColor Cyan
Push-Location $Root
try {
    & $pythonExe -m pip install --upgrade pip
    & $pythonExe -m pip install ".[dev]"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

$freezeOut = Join-Path $DistApp "BUNDLED_PYTHON_PACKAGES.txt"
Write-Host "pip: freeze -> $freezeOut" -ForegroundColor Cyan
$header = @"
# Python packages embedded in this RawView build (PyInstaller onedir).
# Generated at MSI build time from the same environment used for pip install.
# Do not pip install on end users' PCs; RawView.exe bundles the runtime.

"@
Set-Content -LiteralPath $freezeOut -Value $header -Encoding utf8
& $pythonExe -m pip freeze | Add-Content -LiteralPath $freezeOut -Encoding utf8
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
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
