# ==================================================================
#  add-persian-keyboard.ps1
#  Adds the Persian (Farsi) keyboard layout to the CURRENT Windows
#  user, keeping all existing layouts (English and others).
#
#  WHEN TO USE: on the computer where you physically type. If you
#  work INSIDE an RDP session (typing on the server itself), the
#  server's Windows - not your own PC - decides which languages can
#  be typed. If Persian letters do not appear in the browser while
#  typing on the server, run this script ON THE SERVER (RDP session):
#
#      powershell -ExecutionPolicy Bypass -File add-persian-keyboard.ps1
#
#  No restart is needed. Switch layouts with Win+Space or by clicking
#  the language indicator (ENG / PER) in the taskbar corner.
# ==================================================================

Write-Host "Checking installed keyboard layouts ..." -ForegroundColor Cyan

$current = Get-WinUserLanguageList
$hasFa = $false
foreach ($l in $current) {
    if ($l.LanguageTag -like "fa*") { $hasFa = $true }
}

if ($hasFa) {
    Write-Host "Persian layout is ALREADY installed. Nothing to do." -ForegroundColor Yellow
    Write-Host "Switch layouts with Win+Space (or click ENG/PER near the clock)."
    exit 0
}

Write-Host "Adding Persian (fa-IR) keyboard layout ..."
$newList = New-WinUserLanguageList -Language "fa-IR"
foreach ($l in $current) {
    # keep every existing layout (e.g. en-US)
    $newList.Add($l.LanguageTag) | Out-Null
}
Set-WinUserLanguageList $newList -Force

Write-Host ""
Write-Host "Done. Persian layout added." -ForegroundColor Green
Write-Host "Switch keyboard with Win+Space (Persian / English),"
Write-Host "then type Persian normally inside the browser."
