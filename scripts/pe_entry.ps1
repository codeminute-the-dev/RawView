param([Parameter(Mandatory=$true)][string]$Path)
$b=[IO.File]::ReadAllBytes((Resolve-Path $Path).Path)
$pe=[BitConverter]::ToInt32($b,0x3C)
$opt=$pe+24
$magic=[BitConverter]::ToUInt16($b,$opt)
$isPlus=($magic-eq 0x20B)
if($isPlus){
  $imgBase=[BitConverter]::ToUInt64($b,$opt+24)
  $ep=[BitConverter]::ToUInt32($b,$opt+16)
  $sub=[BitConverter]::ToUInt16($b,$opt+68)
  $dllch=[BitConverter]::ToUInt16($b,$opt+70)
}else{
  $imgBase=[BitConverter]::ToUInt32($b,$opt+28)
  $ep=[BitConverter]::ToUInt32($b,$opt+16)
  $sub=[BitConverter]::ToUInt16($b,$opt+56)
  $dllch=[BitConverter]::ToUInt16($b,$opt+58)
}
$ns=[BitConverter]::ToUInt16($b,$pe+6)
$osz=[BitConverter]::ToUInt16($b,$pe+20)
$so=$pe+24+$osz
function RvaToOff([byte[]]$B,[int]$pe,[uint32]$rva){
  $opt=$pe+24;$osz=[BitConverter]::ToUInt16($B,$pe+20);$sect=$pe+24+$osz
  $ns=[BitConverter]::ToUInt16($B,$pe+6)
  for($i=0;$i -lt $ns;$i++){
    $h=$sect+40*$i
    $va=[BitConverter]::ToUInt32($B,$h+12)
    $vs=[BitConverter]::ToUInt32($B,$h+8)
    $raw=[BitConverter]::ToUInt32($B,$h+20)
    if($rva -ge $va -and $rva -lt $va+[Math]::Max($vs,1)){return [int64]($raw+($rva-$va))}
  }
  return -1
}
$epOff=RvaToOff $b $pe $ep
Write-Output "ImageBase: 0x$('{0:X}' -f $imgBase)"
Write-Output "AddressOfEntryPoint (RVA): 0x$('{0:X}' -f $ep)  fileOff: $epOff"
Write-Output "Subsystem: $sub  DllCharacteristics: 0x$('{0:X4}' -f $dllch)"
if($epOff -ge 0 -and $epOff+64 -lt $b.Length){
  $hex=($b[$epOff..($epOff+63)]|ForEach-Object{'{0:X2}'-f $_}) -join ' '
  Write-Output "First 64 bytes @ entry (file): $hex"
}
# Export Start
$dd0=if($isPlus){$opt+0x70}else{$opt+0x60}
$expRva=[BitConverter]::ToUInt32($b,$dd0)
if($expRva){
  $eo=RvaToOff $b $pe $expRva
  $noFuncs=[BitConverter]::ToUInt32($b,$eo+20)
  $addrTableRva=[BitConverter]::ToUInt32($b,$eo+28)
  $nameTableRva=[BitConverter]::ToUInt32($b,$eo+32)
  $ordTableRva=[BitConverter]::ToUInt32($b,$eo+36)
  $ato=RvaToOff $b $pe $addrTableRva
  $nto=RvaToOff $b $pe $nameTableRva
  $oto=RvaToOff $b $pe $ordTableRva
  if($noFuncs -gt 0 -and $ato -ge 0){
    $funcRva=[BitConverter]::ToUInt32($b,$ato)
    $fo=RvaToOff $b $pe $funcRva
    Write-Output "Export[0] RVA: 0x$('{0:X}' -f $funcRva) fileOff: $fo"
    if($nto -ge 0){
      $nrva=[BitConverter]::ToUInt32($b,$nto)
      $noff=RvaToOff $b $pe $nrva
      $nm='';for($j=$noff;$j -lt $b.Length -and $b[$j]-ne 0;$j++){if($b[$j]-ge32-and$b[$j]-le126){$nm+=[char]$b[$j]}}
      Write-Output "Export[0] name: $nm"
    }
  }
}
