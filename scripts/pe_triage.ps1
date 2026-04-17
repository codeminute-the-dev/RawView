<# 
  Static triage for PE binaries: run locally, paste output into Cursor for assistant RE.
  Usage: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pe_triage.ps1 -Path "C:\path\file.dll"
#>
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [int]$MaxExports = 80,
    [int]$MaxStrings = 400
)

$ErrorActionPreference = "Stop"
$bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $Path).Path)

function Get-RvaFileOffset {
    param([byte[]]$B, [int]$PeHeader, [uint32]$Rva)
    $numSect = [BitConverter]::ToUInt16($B, $PeHeader + 6)
    $optSize = [BitConverter]::ToUInt16($B, $PeHeader + 20)
    $sectOff = $PeHeader + 24 + $optSize
    for ($i = 0; $i -lt $numSect; $i++) {
        $so = $sectOff + ($i * 40)
        $virt = [BitConverter]::ToUInt32($B, $so + 12)
        $vsize = [BitConverter]::ToUInt32($B, $so + 8)
        $raw = [BitConverter]::ToUInt32($B, $so + 20)
        $rawSize = [BitConverter]::ToUInt32($B, $so + 16)
        $span = [Math]::Max([uint64]$vsize, [uint64]$rawSize)
        if ($Rva -ge $virt -and $Rva -lt ($virt + $span)) {
            return [int64]($raw + ($Rva - $virt))
        }
    }
    return -1
}

function Read-AsciiZ {
    param([byte[]]$B, [long]$Off)
    if ($Off -lt 0) { return $null }
    $sb = [System.Text.StringBuilder]::new()
    for ($p = $Off; $p -lt $B.Length; $p++) {
        if ($B[$p] -eq 0) { break }
        if ($B[$p] -ge 32 -and $B[$p] -le 126) { [void]$sb.Append([char]$B[$p]) }
        else { break }
    }
    if ($sb.Length -eq 0) { return $null }
    return $sb.ToString()
}

if ($bytes.Length -lt 0x40) { throw "File too small" }
$e_lfanew = [BitConverter]::ToInt32($bytes, 0x3C)
$pe = $e_lfanew
$sig = [Text.Encoding]::ASCII.GetString($bytes[$pe..($pe + 3)])
if ($sig -ne "PE`0`0") { throw "Not a PE file" }

$machine = [BitConverter]::ToUInt16($bytes, $pe + 4)
$numSect = [BitConverter]::ToUInt16($bytes, $pe + 6)
$timeDate = [BitConverter]::ToUInt32($bytes, $pe + 8)
$optSize = [BitConverter]::ToUInt16($bytes, $pe + 20)
$opt = $pe + 24
$magic = [BitConverter]::ToUInt16($bytes, $opt)
$isPE32Plus = ($magic -eq 0x20B)
$dd0 = if ($isPE32Plus) { $opt + 0x70 } else { $opt + 0x60 }
$exportRva = [BitConverter]::ToUInt32($bytes, $dd0)
$importRva = [BitConverter]::ToUInt32($bytes, $dd0 + 8)

$sectOff = $opt + $optSize
$sections = @()
for ($i = 0; $i -lt $numSect; $i++) {
    $so = $sectOff + ($i * 40)
    $name = ([Text.Encoding]::ASCII.GetString($bytes[$so..($so + 7)])).TrimEnd([char]0)
    $virt = [BitConverter]::ToUInt32($bytes, $so + 12)
    $vsize = [BitConverter]::ToUInt32($bytes, $so + 8)
    $raw = [BitConverter]::ToUInt32($bytes, $so + 20)
    $sections += [PSCustomObject]@{ Name = $name; VirtualAddress = $virt; VirtualSize = $vsize; PointerToRawData = $raw }
}

$imports = [System.Collections.Generic.List[string]]::new()
if ($importRva -ne 0) {
    $impOff = Get-RvaFileOffset -B $bytes -PeHeader $pe -Rva $importRva
    if ($impOff -ge 0) {
        $idx = 0
        while ($idx -lt 4096) {
            $d = $impOff + ($idx * 20)
            if ($d + 20 -gt $bytes.Length) { break }
            $nameRva = [BitConverter]::ToUInt32($bytes, $d + 12)
            $orig = [BitConverter]::ToUInt32($bytes, $d)
            if ($nameRva -eq 0 -and $orig -eq 0) { break }
            if ($nameRva -ne 0) {
                $no = Get-RvaFileOffset -B $bytes -PeHeader $pe -Rva $nameRva
                $dll = Read-AsciiZ -B $bytes -Off $no
                if ($dll) { $imports.Add($dll) }
            }
            $idx++
        }
    }
}

$exports = [System.Collections.Generic.List[string]]::new()
if ($exportRva -ne 0) {
    $eo = Get-RvaFileOffset -B $bytes -PeHeader $pe -Rva $exportRva
    if ($eo -ge 0) {
        $noNames = [BitConverter]::ToUInt32($bytes, $eo + 24)
        if ($noNames -gt 0 -and $noNames -lt 100000) {
            $namesTableRva = [BitConverter]::ToUInt32($bytes, $eo + 32)
            $namesOff = Get-RvaFileOffset -B $bytes -PeHeader $pe -Rva $namesTableRva
            if ($namesOff -ge 0) {
                $lim = [Math]::Min($MaxExports, $noNames)
                for ($i = 0; $i -lt $lim; $i++) {
                    $nrva = [BitConverter]::ToUInt32($bytes, $namesOff + (4 * $i))
                    $noff = Get-RvaFileOffset -B $bytes -PeHeader $pe -Rva $nrva
                    $nm = Read-AsciiZ -B $bytes -Off $noff
                    if ($nm) { $exports.Add($nm) }
                }
            }
        }
    }
}

# ASCII runs length >= 5
$ascii = [System.Collections.Generic.List[string]]::new()
$i = 0
$n = $bytes.Length
while ($i -lt $n) {
    if ($bytes[$i] -ge 32 -and $bytes[$i] -le 126) {
        $start = $i
        while ($i -lt $n -and $bytes[$i] -ge 32 -and $bytes[$i] -le 126) { $i++ }
        $len = $i - $start
        if ($len -ge 5) {
            $ascii.Add([Text.Encoding]::ASCII.GetString($bytes, $start, $len))
        }
    }
    else { $i++ }
}
$uniq = $ascii | Sort-Object -Unique
$patterns = @(
    @{ Name = "http_url"; Re = 'https?://[^\s\x00-\x1f]{6,}' }
    @{ Name = "roblox"; Re = '(?i)roblox' }
    @{ Name = "paths"; Re = '(?i)[a-z]:\\[^\x00-\x1f]{4,}' }
    @{ Name = "dll_ref"; Re = '(?i)[a-z0-9_\-]+\.dll' }
    @{ Name = "crypto_tls"; Re = '(?i)(tls|ssl|encrypt|decrypt|certificate|x509|aes|rsa|ecdsa|curl|openssl)' }
    @{ Name = "lua_luau"; Re = '(?i)(luau|luaL_|lua_|\.lua)' }
)
$buckets = @{}
foreach ($p in $patterns) {
    $hits = $uniq | Where-Object { $_ -match $p.Re } | Select-Object -First ([Math]::Floor($MaxStrings / $patterns.Count))
    $buckets[$p.Name] = @($hits)
}

Write-Output "## PE triage: $Path"
Write-Output ""
Write-Output "### Size"
Write-Output "- Length: $($bytes.Length) bytes"
Write-Output ""
Write-Output "### COFF / optional"
Write-Output "- Machine: 0x$('{0:X4}' -f $machine)  PE32+: $isPE32Plus"
Write-Output "- TimeDateStamp: $timeDate"
Write-Output "- Sections: $numSect"
Write-Output ""
Write-Output "### Sections"
$sections | Format-Table -AutoSize | Out-String | Write-Output
Write-Output "### Import DLLs"
$imports | Sort-Object -Unique | ForEach-Object { Write-Output "- $_" }
Write-Output ""
Write-Output "### Export symbols (first $($exports.Count))"
$exports | ForEach-Object { Write-Output "- $_" }
Write-Output ""
Write-Output "### Filtered strings (sample)"
foreach ($k in $buckets.Keys | Sort-Object) {
    Write-Output ""
    Write-Output "#### $k"
    foreach ($h in $buckets[$k]) { Write-Output "- $h" }
}
