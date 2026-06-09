# URice Tools Client

Production foundation for a modular Windows desktop client built with Tauri, React, and a Python OCR backend.

## Product Direction

URice Tools Client is the long-term shell for internal document tools. The first module is PO PDF Manager, which extracts Purchase Order data from scanned PDF files, lets non-technical users review OCR output, and exports clean rows to Excel.

## Stack

- Tauri v2 for the native Windows desktop shell and installer/update foundation.
- React + TypeScript for the premium interface.
- Three.js / React Three Fiber for carefully scoped 3D visual polish.
- Python sidecar for OCR, PDF processing, Excel export, and extraction rules.
- Tesseract OCR bundled at release time.
- GitHub Releases for update distribution.

## Current Status

This folder is the new scalable foundation. The old prototype remains in the parent project as reference material. The Python extraction engine has been seeded from `full-client` so the next step is integration and test hardening, not starting from zero.

## Local Setup

Prerequisites for developers:

1. Node.js LTS and npm.
2. Rust stable with Cargo.
3. Python 3.12.
4. Tauri prerequisites for Windows.

Install frontend dependencies:

```powershell
npm install
```

Install backend dependencies:

```powershell
python -m pip install -r backend/requirements.txt
```

Run backend smoke test:

```powershell
python backend/engine.py --health
```

Run Tauri dev app:

```powershell
npm run tauri:dev
```

## Release Goal

The user-facing release should be a single `Setup.exe`. Users should not install Python, Node, Rust, Tesseract, or any command-line tools manually.
## Bundled OCR Runtime

- 2026-06-09 01:02:32 WIB - Production installers are expected to bundle Tesseract OCR and the required language data inside the application package. Users should only need to download and run the setup installer; no command prompt, Python, Node.js, Rust, or Tesseract installation should be required on user machines.
