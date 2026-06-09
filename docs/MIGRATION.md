# Migration From Prototype

## Keep

- PO extraction rules that work on real samples.
- OCR fallback strategy.
- Position-aware parsing ideas.
- Preview, correction, export workflow.
- Output Excel columns already accepted by users.

## Replace

- Monolithic CustomTkinter app structure.
- One-file prototype packaging model.
- UI state mixed with extraction state.
- Ad hoc history/settings storage.

## Immediate Next Steps

1. Make the sidecar callable from Tauri using `tauri-plugin-shell` or native commands.
2. Add automated extraction tests using the existing sample PDFs.
3. Add SQLite history and confidence/error flags.
4. Build the real correction table UI.
5. Add release pipeline and updater signing.
