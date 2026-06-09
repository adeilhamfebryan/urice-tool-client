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

## GitHub Releases Auto Updater

- 2026-06-09 07:33:00 WIB - Auto updater distribution is configured to use GitHub Releases at `https://github.com/adeilhamfebryan/urice-tool-client/releases/latest/download/latest.json`.
- 2026-06-09 13:24:28 WIB - Release workflow signing secrets are loaded through `$GITHUB_ENV` before `tauri-action` runs, so multiline updater private keys stored in GitHub Actions Secrets are passed to Tauri more reliably.
- 2026-06-09 13:48:46 WIB - Settings now includes a visible manual Check for Updates button and an Auto Update Status field. The app also starts a silent update check on startup and prompts the user only when a signed release update is available.
- 2026-06-09 19:57:29 WIB - The local 0.1.0 installer was rebuilt from the updater-enabled UI and should be used as the baseline install for update testing. The next GitHub updater release target is 0.1.3 because tags 0.1.1 and 0.1.2 were already used for earlier signing-secret tests.
- 2026-06-09 20:25:29 WIB - If GitHub Releases does not yet contain `latest.json`, the app now explains that no update package is available on the server. A valid update still requires the release workflow to finish signing and publishing updater artifacts.
- 2026-06-09 20:59:37 WIB - The project now uses the newly generated updater key pair `urice.key` / `urice.key.pub`. The GitHub Actions private key secret remains `ANAK`, the password secret remains `YATIM`, and the app public key in `tauri.conf.json` must match `urice.key.pub`.
- 2026-06-09 21:32:21 WIB - Local release builds now read the updater key password from `src-tauri/keys/secret.txt` when that ignored file exists. Keep this file local only and ensure it matches the password stored in GitHub Actions secret `YATIM`.
- 2026-06-09 22:14:44 WIB - Version 0.1.5 adds visible updater progress for check/download/install/restart phases. If the installed app still shows the old version after update, confirm the progress reaches the restart phase and that Windows allows the passive NSIS updater to replace the installed app.
- 2026-06-09 23:30:23 WIB - Version 1.1.0 reads the displayed application version from the Tauri backend command `app_version`, which uses the packaged Cargo version. This removes the old frontend fallback that could keep showing `URice Tools Client v0.1.0` after an update.
- 2026-06-10 00:13:10 WIB - Version 1.1.1 separates Dashboard content from operational modules. Native Tauri/Windows dialogs remain system-styled; premium branded confirmation dialogs should be implemented as custom React modals in a later UI pass, while OS file picker/save dialogs should stay native.
- 2026-06-10 00:45:43 WIB - Version 1.1.2 is a UI polish update. The current Tauri updater still downloads the signed installer package for the target version; differential binary patch updates are not implemented in this project.
- The updater signing private key must be stored in GitHub Actions Secrets, not in the repository. This repository expects the private key secret name `ANAK` and the key password secret name `YATIM`.
- The public updater key is stored in `src-tauri/tauri.conf.json`.
- Release builds are produced by `.github/workflows/release.yml`.
- To prepare a new update, increment the app version in `package.json` and `src-tauri/tauri.conf.json`, commit the change, then push a tag such as `v0.1.1`.
- The workflow creates a draft GitHub Release with the Windows setup installer, updater signature, and `latest.json`. Publish the draft after verifying the release assets.

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

## Batch Processing Notes

- 2026-06-09 22:14:44 WIB - Batch OCR may run with limited parallel workers. Recommended default is 2 workers because each PDF can start OCR/PDF processing sidecar work; higher values can be faster but may increase CPU, RAM, and disk pressure on office laptops. Excel writing remains sequential after preview confirmation to avoid workbook corruption.

## Excel Merger Notes

- 2026-06-09 23:30:23 WIB - Excel Merger 1.1.0 starts with custom column mapping instead of hardcoded SAP/PB/PI/COM formats. Users can load workbooks, map source headers into URice standard columns, and export a normalized workbook. Real user sample files will be used later to improve automatic template detection.
