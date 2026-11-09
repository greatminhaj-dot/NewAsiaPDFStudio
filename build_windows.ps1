# Windows x64: creates a distributable Setup.exe (Python 3.12 and Inno Setup 6 required).
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$py = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python' }
if ($py -eq 'py') { & py -3.12 -m venv .venv } else { & python -m venv .venv }
if ($LASTEXITCODE -ne 0) { throw 'Unable to create Python 3.12 venv.' }
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip failed' }
& $python -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'Dependencies failed' }
& $python -m PyInstaller --noconfirm --clean --windowed --onedir --name NewAsiaPDFStudio --icon assets\newasia.ico --add-data 'assets;assets' --collect-all fitz app.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$isccCandidates = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
  'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw 'Portable app built in dist\NewAsiaPDFStudio, but Setup.exe requires Inno Setup 6: https://jrsoftware.org/isdl.php' }
& $iscc 'NewAsiaPDFStudio.iss'
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
Write-Host "Installer ready: $PSScriptRoot\installer_output\NewAsiaPDFStudio_Setup_3.2_Windows_x64.exe"
