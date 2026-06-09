# Build Python sidecar placeholder.
# The exact sidecar filename must be aligned with Tauri target naming before release.

$ErrorActionPreference = "Stop"
python -m PyInstaller --onefile --name urice-engine backend/engine.py
