# Architecture

## High-Level Shape

URice Tools Client is a desktop shell with module-based tools.

- React owns the visible product experience.
- Tauri owns native Windows integration, installer packaging, secure permissions, file dialogs, and updater.
- Python owns heavy document processing and OCR.

## Module Boundary

The first module is `PO PDF Manager`. Future modules should follow the same pattern:

- Frontend route/component under `src/modules/<module-name>`.
- Backend command or service under `backend/urice_engine`.
- Shared app shell features stay outside modules.

## Python Sidecar Contract

The sidecar must expose stable commands that can be called by Tauri:

- `--health`
- `--extract <pdf>`
- future: `--export-excel <payload>`
- future: `--batch <folder>`

Responses are JSON. The frontend should never parse OCR logs as business data.

## Data Locations

Installed app files belong under Program Files. User data belongs under AppData or user-selected document folders.

Recommended:

- `%APPDATA%\URice Tools Client\settings.json`
- `%APPDATA%\URice Tools Client\history.sqlite`
- `%APPDATA%\URice Tools Client\logs\`

## UI Principle

3D and animation are used for orientation, branding, and progress feedback. Core work areas such as tables, review forms, and export screens must stay dense, readable, and predictable for non-technical operators.
