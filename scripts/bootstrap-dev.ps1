# Developer bootstrap placeholder.
# Run after Node.js, Rust, and Python are installed.

$ErrorActionPreference = "Stop"
python -m pip install -r backend/requirements.txt
npm install
python backend/engine.py --health
