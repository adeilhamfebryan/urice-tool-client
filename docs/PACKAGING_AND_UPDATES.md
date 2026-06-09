# Packaging And Updates

## Target Experience

The user downloads `URiceToolsClientSetup.exe`, runs it, and gets the full application. No command prompt. No manual Python install. No manual Tesseract install.

## Recommended Packaging Flow

1. Build React frontend with Vite.
2. Build Python backend into a sidecar executable with PyInstaller.
3. Bundle Tesseract OCR and language data.
4. Build Tauri app with NSIS or an Inno Setup wrapper if more installer control is needed.
5. Publish signed updater artifacts to GitHub Releases.

## Python Sidecar Build

Planned command:

```powershell
pyinstaller --onefile --name urice-engine backend/engine.py
```

Tauri expects external binaries to be available before `tauri build`. The produced binary should be copied or emitted into `backend/dist` using the sidecar naming convention required by Tauri for the target platform.

## Auto Update

Use Tauri updater with GitHub Releases. Production release work must include:

- updater signing keys
- `latest.json` generation
- release artifact upload
- version bump policy
- rollback plan

## Installer Mode

For non-technical Windows users, the preferred installer mode is passive/simple with desktop and Start Menu shortcuts. Advanced settings should live inside the app, not the installer wizard.

## Current Local Build

A local NSIS installer is generated at:

```text
src-tauri/target/release/bundle/nsis/URice Tools Client_0.1.0_x64-setup.exe
```

The matching updater signature is generated beside it as `.sig`.

For repeat local builds, run:

```powershell
.\scripts\build-release.ps1
```

The current updater key is for local development only. Before public/internal production releases, replace it with a controlled release key and store the private key outside the repository.

## Timestamped Notes

- 2026-06-09 00:45:32 WIB - Catatan kecil: updater key yang sekarang masih local development key. Untuk production/internal release sungguhan, nanti sebaiknya kita buat release key resmi dan simpan private key di tempat aman, bukan di folder project.

## Bundled OCR Assets

- 2026-06-09 01:02:32 WIB - Tesseract OCR is bundled into the Python sidecar via PyInstaller --add-data. The release installer must include `tesseract.exe`, required DLLs, `eng.traineddata`, and `ind.traineddata`, so office users only install `Setup.exe` and do not install OCR components manually.
