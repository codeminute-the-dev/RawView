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

$spec = Join-Path $Root "packaging\rawview.spec"
if (-not (Test-Path $spec)) {
    Write-Error "Missing spec: $spec"
}

& $Python -m PyInstaller --noconfirm --clean $spec

$out = Join-Path $Root "dist\RawView"
if (Test-Path (Join-Path $out "RawView.exe")) {
    Write-Host "OK: $out\RawView.exe" -ForegroundColor Green
    Write-Host "Next: install Inno Setup, open installer\RawView.iss, Build > Compile (creates dist_installer\RawView-Setup-*.exe)." -ForegroundColor Yellow
} else {
    Write-Error "Build finished but RawView.exe not found under dist\RawView"
}
