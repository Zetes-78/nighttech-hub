# Builds NightTechHub-Setup.exe on Windows.
# Needs: Python 3.10+ (python.org, "Add Python to PATH") and Inno Setup 6 (jrsoftware.org).
# Run from this folder:  powershell -ExecutionPolicy Bypass -File .\build.ps1
param([string]$Version = "")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== Night Tech Hub installer build ==" -ForegroundColor Cyan

# 1. Find Python
$py = $null
foreach ($c in @("python", "py -3")) {
    try { $v = & cmd /c "$c --version" 2>$null; if ($LASTEXITCODE -eq 0 -and $v -match "Python 3\.(\d+)") { if ([int]$Matches[1] -ge 10) { $py = $c; break } } } catch {}
}
if (-not $py) { throw "Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/ and tick 'Add Python to PATH'." }
Write-Host "Using $py"

# 2. Clean build environment with pinned tools
if (Test-Path .build-venv) { Remove-Item -Recurse -Force .build-venv }
& cmd /c "$py -m venv .build-venv"
$vpy = ".\.build-venv\Scripts\python.exe"
& $vpy -m pip install --quiet --upgrade pip
& $vpy -m pip install --quiet -r requirements.txt "pyinstaller>=6.11,<7"
if ($LASTEXITCODE -ne 0) { throw "Installing the build tools failed." }

# 3. Package the app (no Python needed on the target PC)
foreach ($d in @("build", "dist")) { if (Test-Path $d) { Remove-Item -Recurse -Force $d } }
& $vpy -m PyInstaller --noconfirm --clean --onedir --console `
    --name NightTechHub `
    --icon installer\NightTechHub.ico `
    --add-data "templates;templates" `
    --add-data "static;static" `
    --collect-submodules reportlab `
    launcher.py
if ($LASTEXITCODE -ne 0 -or -not (Test-Path dist\NightTechHub\NightTechHub.exe)) { throw "Packaging failed." }

# 4. Build the installer with Inno Setup
$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 was not found. Install it from https://jrsoftware.org/isdl.php (or: winget install JRSoftware.InnoSetup), then run this script again." }
if ($Version) { & $iscc "/DAppVersion=$Version" installer\NightTechHub.iss } else { & $iscc installer\NightTechHub.iss }
if ($LASTEXITCODE -ne 0) { throw "The installer build failed." }

$out = "installer\Output\NightTechHub-Setup.exe"
$hash = (Get-FileHash $out -Algorithm SHA256).Hash
"$hash  NightTechHub-Setup.exe" | Out-File -Encoding ascii "installer\Output\NightTechHub-Setup.exe.sha256.txt"
Write-Host ""
Write-Host "Done: $out" -ForegroundColor Green
Write-Host "SHA-256: $hash"
