# -----------------------------------------------------------------------------------------------------------
# package_handover.ps1 - build a handover archive and verify it end to end (Windows PowerShell 5.1+ / 7+)
#
# Usage:
#   powershell -NoProfile -File package_handover.ps1 -Pkg <pkg-dir> -Out <out-dir> -Name <archive-basename>
#   pwsh       -NoProfile -File package_handover.ps1 -Pkg <pkg-dir> -Out <out-dir> -Name <archive-basename>
#
# Steps (any failure exits non-zero):
#   1) regenerate MANIFEST-SHA256.txt  (LF newlines + forward slashes)
#   2) reject NUL bytes in text files
#   3) create <name>.tar.gz
#   4) extract it and verify EVERY SHA256 entry (not a sample)
#
# NOTE: This script is deliberately ASCII-only. Windows PowerShell 5.1 reads a .ps1
#       without a BOM as ANSI/GBK, so non-ASCII messages break parsing unless a BOM is
#       present - and many editors/tools strip the BOM. Keep this file ASCII, or re-add
#       the BOM after every edit and retest with powershell.exe.
# NOTE: Deliberately avoids [System.IO.Compression.ZipFile]::CreateFromDirectory, which on
#       Windows writes backslash separators and no UTF-8 flag in ZIP entries.
# -----------------------------------------------------------------------------------------------------------
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$Pkg,
  [Parameter(Mandatory = $true)][string]$Out,
  [Parameter(Mandatory = $true)][string]$Name
)

$ErrorActionPreference = 'Stop'

$pkg = (Resolve-Path -LiteralPath $Pkg).Path
if (-not (Test-Path -LiteralPath $Out)) { New-Item -ItemType Directory -Path $Out -Force | Out-Null }
$out = (Resolve-Path -LiteralPath $Out).Path
$base = Split-Path -Leaf $pkg
$archive = Join-Path $out "$Name.tar.gz"

Write-Host '== [1/4] regenerate MANIFEST-SHA256.txt (LF, forward slashes)'
$files = Get-ChildItem -LiteralPath $pkg -Recurse -File -Force |
  Where-Object { $_.Name -ne 'MANIFEST-SHA256.txt' } | Sort-Object FullName
$lines = foreach ($f in $files) {
  $rel = $f.FullName.Substring($pkg.Length + 1).Replace('\', '/')
  "$((Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower())  $rel"
}
$manifestPath = Join-Path $pkg 'MANIFEST-SHA256.txt'
# Must be LF: WriteAllLines emits CRLF on Windows, and Linux `sha256sum -c` then treats the
# trailing CR as part of the filename -> every entry reports "FAILED open or read".
$nl = [string][char]10
[System.IO.File]::WriteAllText($manifestPath, ([string]::Join($nl, $lines) + $nl),
  (New-Object System.Text.UTF8Encoding($false)))
$rawManifest = [System.IO.File]::ReadAllBytes($manifestPath)
if ($rawManifest -contains 13) { throw 'manifest contains CR - must be LF or sha256sum -c fails on Linux' }
if ($lines | Where-Object { $_ -match '\\' }) { throw 'manifest contains backslash paths - sha256sum -c fails on Linux' }
Write-Host "   OK: $($lines.Count) entries (LF, forward slashes)"

Write-Host '== [2/4] NUL byte check on text files'
$textExt = '.md', '.txt', '.sh', '.ps1', '.py', '.yml', '.yaml', '.json', '.toml', '.ini', '.cfg', '.csv', '.c', '.h', '.cpp', '.hpp', '.inl'
$nul = 0
foreach ($f in (Get-ChildItem -LiteralPath $pkg -Recurse -File -Force)) {
  if ($textExt -notcontains $f.Extension.ToLower()) { continue }
  $bytes = [System.IO.File]::ReadAllBytes($f.FullName)
  if ($bytes -contains 0) { Write-Host "   [FAIL] NUL: $($f.FullName.Substring($pkg.Length + 1))"; $nul++ }
}
if ($nul -gt 0) { throw "$nul text file(s) contain NUL bytes" }
Write-Host '   OK: no NUL bytes'

Write-Host '== [3/4] create tar.gz'
if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
tar -czf $archive -C (Split-Path -Parent $pkg) $base
if ($LASTEXITCODE -ne 0) { throw "tar failed (exit $LASTEXITCODE)" }
Write-Host "   OK: $archive"

Write-Host '== [4/4] extract and verify every entry'
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("verify-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
  tar -xzf $archive -C $tmp 2>$null
  if ($LASTEXITCODE -ne 0) { throw "tar extract failed (exit $LASTEXITCODE)" }
  $root = Join-Path $tmp $base
  $ml = [System.IO.File]::ReadAllLines((Join-Path $root 'MANIFEST-SHA256.txt'))
  $ok = 0; $bad = New-Object System.Collections.ArrayList
  foreach ($l in $ml) {
    $parts = $l -split '\s+', 2
    $target = Join-Path $root ($parts[1] -replace '/', '\')
    if (-not (Test-Path -LiteralPath $target)) { [void]$bad.Add("$($parts[1]) [missing]"); continue }
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLower() -eq $parts[0]) { $ok++ }
    else { [void]$bad.Add($parts[1]) }
  }
  $extracted = (Get-ChildItem -LiteralPath $root -Recurse -File -Force).Count
  if ($bad.Count -gt 0) { throw "verification failed for $($bad.Count) entry/entries`n$($bad | Select-Object -First 20 | Out-String)" }
  Write-Host "   OK: extracted $extracted files, SHA256 all passed ($ok/$($ml.Count))"

  $sha = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLower()
  $mb = [math]::Round((Get-Item -LiteralPath $archive).Length / 1MB, 2)
  Write-Host ''
  Write-Host '================ HANDOVER SUMMARY ================'
  Write-Host "archive : $archive"
  Write-Host "size    : $mb MB"
  Write-Host "entries : $($ml.Count) files ($extracted after extract)"
  Write-Host "SHA256  : $sha"
  Write-Host 'verify  : full SHA256 re-check after extract (FAIL=0)'
  Write-Host '=================================================='
  Write-Host 'Send this block together with the kickoff prompt.'
}
finally {
  Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
