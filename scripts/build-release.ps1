# Build a local release of URice Tools Client.
# Requires Node.js, Rust, Visual Studio Build Tools C++, Python, and backend dependencies.

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LegacyRoot = Split-Path -Parent $ProjectRoot
$VsDevCmd = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
$KeyPath = Join-Path $ProjectRoot "src-tauri\keys\urice-tools-client.key"
$TesseractSource = Join-Path $LegacyRoot "tesseract_portable"
$TesseractExe = Join-Path $TesseractSource "tesseract.exe"
$IndData = Join-Path $TesseractSource "tessdata\ind.traineddata"
$EngData = Join-Path $TesseractSource "tessdata\eng.traineddata"

if (-not (Test-Path -LiteralPath $VsDevCmd)) {
  throw "Visual Studio Build Tools not found at $VsDevCmd"
}
if (-not (Test-Path -LiteralPath $KeyPath)) {
  throw "Updater signing key not found at $KeyPath"
}
if (-not (Test-Path -LiteralPath $TesseractExe)) {
  throw "Bundled Tesseract not found at $TesseractExe"
}
if (-not (Test-Path -LiteralPath $IndData)) {
  throw "Indonesian OCR data not found at $IndData"
}
if (-not (Test-Path -LiteralPath $EngData)) {
  throw "English OCR data not found at $EngData"
}

python -m PyInstaller --onefile --clean `
  --name urice-engine-x86_64-pc-windows-msvc `
  --distpath (Join-Path $ProjectRoot "backend\dist") `
  --workpath (Join-Path $ProjectRoot "backend\build") `
  --specpath (Join-Path $ProjectRoot "backend") `
  --add-data "$TesseractSource;tesseract_portable" `
  (Join-Path $ProjectRoot "backend\engine.py")

$env:TAURI_SIGNING_PRIVATE_KEY = Get-Content -Raw -Path $KeyPath
$env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = "urice-local-dev"

$cmd = "`"$VsDevCmd`" -arch=x64 && set `"PATH=C:\Program Files\nodejs;%USERPROFILE%\.cargo\bin;%PATH%`" && npm run tauri:build"
cmd.exe /d /s /c $cmd

