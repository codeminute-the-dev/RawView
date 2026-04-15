# Build RawView with PyInstaller (onedir). Run from repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

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

Write-Host "== RawView Windows build ==" -ForegroundColor Cyan
Write-Host "Root: $Root"

$Python = Find-PythonExe
if (-not $Python) {
    Write-Error "Python 3.11+ not found. Install Python, add it to PATH, or ensure the 'py' launcher is available."
}
Write-Host "Using Python: $Python" -ForegroundColor DarkGray

& $Python -m pip install --upgrade pip
& $Python -m pip install ".[dev]"

Write-Host "Java bridge: compile_java (set GHIDRA_INSTALL_DIR in .env or env; needs JDK javac on PATH) ..." -ForegroundColor Cyan
& $Python -m rawview.scripts.compile_java
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$javaMarker = Join-Path $Root "rawview\java\out\io\rawview\ghidra\GhidraServer.class"
if (-not (Test-Path -LiteralPath $javaMarker)) {
    Write-Warning @"
Ghidra Java bridge not compiled: rawview/java/out is missing GhidraServer.class.
Frozen RawView will not start Ghidra until you set GHIDRA_INSTALL_DIR, run:
  python -m rawview.scripts.compile_java
then rebuild. For CI/release, set RAWVIEW_REQUIRE_JAVA_CLASSES=1 before PyInstaller to fail the build instead.
"@
}

$spec = Join-Path $Root "packaging\rawview.spec"
if (-not (Test-Path $spec)) {
    Write-Error "Missing spec: $spec"
}

& $Python -m PyInstaller --noconfirm --clean $spec

$out = Join-Path $Root "dist\RawView"
if (Test-Path (Join-Path $out "RawView.exe")) {
    Write-Host "OK: $out\RawView.exe" -ForegroundColor Green
    Write-Host "Next: WiX MSI -> build-msi.bat or scripts\build-msi.ps1 (creates dist_installer\RawView-*.msi)." -ForegroundColor Yellow
} else {
    Write-Error "Build finished but RawView.exe not found under dist\RawView"
}
