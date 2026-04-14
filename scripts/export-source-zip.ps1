# Zip exactly what Git tracks (source only — no dist, no local Ghidra/JDK copies).
# Run from repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\export-source-zip.ps1
# Output: parent folder, e.g. ..\RawView-source-0.1.0.zip
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$git = "C:\Program Files\Git\bin\git.exe"
if (-not (Test-Path $git)) {
    $git = (Get-Command git -ErrorAction SilentlyContinue).Source
}
if (-not $git) {
    Write-Error "git.exe not found. Install Git for Windows or add it to PATH."
}
$ver = "0.1.0"
try {
    $meta = & $git -C $Root show HEAD:pyproject.toml 2>$null
    if ($meta -match 'version\s*=\s*"([^"]+)"') { $ver = $Matches[1] }
} catch { }
$parent = Split-Path -Parent $Root
$name = "RawView-source-$ver.zip"
$out = Join-Path $parent $name
if (Test-Path $out) { Remove-Item -LiteralPath $out -Force }
& $git -C $Root archive --format=zip HEAD -o $out
Write-Host "Wrote: $out" -ForegroundColor Green
