use serde::Serialize;
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::Emitter;
use tauri::Manager;
#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[derive(Serialize)]
struct EngineHealthFallback {
    ok: bool,
    engine: String,
    version: String,
    tesseract_configured: bool,
}

fn sidecar_candidates() -> Vec<PathBuf> {
    let mut candidates = Vec::new();

    if let Ok(current_exe) = std::env::current_exe() {
        if let Some(dir) = current_exe.parent() {
            candidates.push(dir.join("urice-engine.exe"));
            candidates.push(dir.join("urice-engine-x86_64-pc-windows-msvc.exe"));
        }
    }

    candidates.push(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..\\backend\\dist\\urice-engine-x86_64-pc-windows-msvc.exe"));
    candidates.push(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..\\backend\\dist\\urice-engine.exe"));

    candidates
}

fn sidecar_path() -> Result<PathBuf, String> {
    sidecar_candidates()
        .into_iter()
        .find(|path| path.exists())
        .ok_or_else(|| "Python sidecar executable was not found. Build backend sidecar first.".to_string())
}

fn run_sidecar(args: &[&str]) -> Result<Value, String> {
    let path = sidecar_path()?;
    let mut command = Command::new(&path);
    command.args(args);
    #[cfg(target_os = "windows")]
    command.creation_flags(0x08000000);

    let output = command.output()
        .map_err(|error| format!("Failed to run sidecar at {}: {error}", path.display()))?;

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

    if !output.status.success() {
        return Err(if stderr.is_empty() {
            format!("Sidecar exited with status {}", output.status)
        } else {
            stderr
        });
    }

    serde_json::from_str(&stdout).map_err(|error| {
        format!(
            "Sidecar returned invalid JSON: {error}. Output: {}",
            if stdout.is_empty() { "<empty>" } else { &stdout }
        )
    })
}

#[tauri::command]
async fn engine_health() -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || engine_health_blocking()).await.map_err(|error| format!("Engine task failed: {error}"))?
}

fn engine_health_blocking() -> Result<Value, String> {
    match run_sidecar(&["--health"]) {
        Ok(value) => Ok(value),
        Err(error) => Ok(serde_json::to_value(EngineHealthFallback {
            ok: false,
            engine: format!("urice-python-sidecar ({error})"),
            version: env!("CARGO_PKG_VERSION").to_string(),
            tesseract_configured: false,
        })
        .expect("fallback health response should serialize")),
    }
}

#[tauri::command]
async fn extract_pdf(path: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || extract_pdf_blocking(path)).await.map_err(|error| format!("Extraction task failed: {error}"))?
}

fn extract_pdf_blocking(path: String) -> Result<Value, String> {
    if path.trim().is_empty() {
        return Err("No PDF path selected.".to_string());
    }

    run_sidecar(&["--extract", &path])
}

#[tauri::command]
async fn process_pdf(path: String, output_folder: String, source_archive_folder: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || process_pdf_blocking(path, output_folder, source_archive_folder)).await.map_err(|error| format!("Process task failed: {error}"))?
}

fn process_pdf_blocking(path: String, output_folder: String, source_archive_folder: String) -> Result<Value, String> {
    if path.trim().is_empty() {
        return Err("No PDF path selected.".to_string());
    }
    if output_folder.trim().is_empty() {
        return Err("No processed PDF output folder selected.".to_string());
    }

    run_sidecar(&["--process", &path, &output_folder, &source_archive_folder])
}

#[tauri::command]
async fn save_processed_pdf(path: String, output_folder: String, vendor_name: String, no_op: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || save_processed_pdf_blocking(path, output_folder, vendor_name, no_op)).await.map_err(|error| format!("Save processed PDF task failed: {error}"))?
}

fn save_processed_pdf_blocking(path: String, output_folder: String, vendor_name: String, no_op: String) -> Result<Value, String> {
    if path.trim().is_empty() {
        return Err("No source PDF path selected.".to_string());
    }
    if output_folder.trim().is_empty() {
        return Err("No processed PDF output folder selected.".to_string());
    }

    run_sidecar(&["--save-processed-pdf", &path, &output_folder, &vendor_name, &no_op])
}

fn app_settings_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_data_dir()
        .map_err(|error| format!("Failed to resolve app data directory: {error}"))?;
    fs::create_dir_all(&dir).map_err(|error| format!("Failed to create app data directory {}: {error}", dir.display()))?;
    Ok(dir.join("settings.json"))
}

#[tauri::command]
async fn app_version() -> Result<String, String> {
    Ok(env!("CARGO_PKG_VERSION").to_string())
}

#[tauri::command]
async fn load_app_settings(app: tauri::AppHandle) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let path = app_settings_path(&app)?;
        if !path.exists() {
            return Ok(serde_json::json!({
                "ok": true,
                "settings": null,
                "path": path.to_string_lossy()
            }));
        }
        let content = fs::read_to_string(&path)
            .map_err(|error| format!("Failed to read settings file {}: {error}", path.display()))?;
        let settings = serde_json::from_str::<Value>(&content)
            .map_err(|error| format!("Settings file contains invalid JSON: {error}"))?;
        Ok(serde_json::json!({
            "ok": true,
            "settings": settings,
            "path": path.to_string_lossy()
        }))
    })
    .await
    .map_err(|error| format!("Load settings task failed: {error}"))?
}

#[tauri::command]
async fn save_app_settings(app: tauri::AppHandle, settings: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let path = app_settings_path(&app)?;
        let content = serde_json::to_string_pretty(&settings)
            .map_err(|error| format!("Failed to serialize settings: {error}"))?;
        fs::write(&path, content)
            .map_err(|error| format!("Failed to write settings file {}: {error}", path.display()))?;
        Ok(serde_json::json!({
            "ok": true,
            "path": path.to_string_lossy()
        }))
    })
    .await
    .map_err(|error| format!("Save settings task failed: {error}"))?
}

#[tauri::command]
async fn list_pdf_files(folder: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || list_pdf_files_blocking(folder)).await.map_err(|error| format!("List PDF task failed: {error}"))?
}

fn list_pdf_files_blocking(folder: String) -> Result<Value, String> {
    if folder.trim().is_empty() {
        return Err("No batch source folder selected.".to_string());
    }

    let source_dir = PathBuf::from(&folder);
    if !source_dir.exists() {
        return Err(format!("Batch source folder does not exist: {}", source_dir.display()));
    }

    let mut pdfs = fs::read_dir(&source_dir)
        .map_err(|error| format!("Failed to read batch folder {}: {error}", source_dir.display()))?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| {
            path.is_file()
                && path
                    .extension()
                    .and_then(|extension| extension.to_str())
                    .map(|extension| extension.eq_ignore_ascii_case("pdf"))
                    .unwrap_or(false)
        })
        .map(|path| path.to_string_lossy().to_string())
        .collect::<Vec<_>>();
    pdfs.sort();

    Ok(serde_json::json!({
        "ok": true,
        "folder": folder,
        "count": pdfs.len(),
        "files": pdfs
    }))
}

#[tauri::command]
async fn move_sources_to_archive(paths: Vec<String>, archive_folder: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || move_sources_to_archive_blocking(paths, archive_folder)).await.map_err(|error| format!("Archive move task failed: {error}"))?
}

fn move_sources_to_archive_blocking(paths: Vec<String>, archive_folder: String) -> Result<Value, String> {
    if archive_folder.trim().is_empty() {
        return Err("No source archive folder selected.".to_string());
    }

    let archive_dir = PathBuf::from(&archive_folder);
    fs::create_dir_all(&archive_dir)
        .map_err(|error| format!("Failed to create archive folder {}: {error}", archive_dir.display()))?;

    let mut moved = Vec::new();
    for source in paths {
        if source.trim().is_empty() {
            continue;
        }
        let source_path = PathBuf::from(&source);
        if !source_path.exists() {
            moved.push(serde_json::json!({
                "ok": false,
                "source": source,
                "error": "Source file no longer exists."
            }));
            continue;
        }

        let Some(file_name) = source_path.file_name() else {
            moved.push(serde_json::json!({
                "ok": false,
                "source": source,
                "error": "Source path has no file name."
            }));
            continue;
        };
        let target_path = archive_dir.join(file_name);
        if source_path == target_path {
            moved.push(serde_json::json!({
                "ok": true,
                "source": source,
                "archived_path": target_path.to_string_lossy()
            }));
            continue;
        }

        let move_result = fs::rename(&source_path, &target_path).or_else(|_| {
            fs::copy(&source_path, &target_path)?;
            fs::remove_file(&source_path)
        });
        match move_result {
            Ok(_) => moved.push(serde_json::json!({
                "ok": true,
                "source": source,
                "archived_path": target_path.to_string_lossy()
            })),
            Err(error) => moved.push(serde_json::json!({
                "ok": false,
                "source": source,
                "error": error.to_string()
            })),
        }
    }

    Ok(serde_json::json!({
        "ok": true,
        "archive_folder": archive_folder,
        "moved": moved
    }))
}

#[tauri::command]
async fn process_batch(app: tauri::AppHandle, folder: String, output_folder: String, source_archive_folder: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || process_batch_blocking(app, folder, output_folder, source_archive_folder)).await.map_err(|error| format!("Batch task failed: {error}"))?
}

fn process_batch_blocking(app: tauri::AppHandle, folder: String, output_folder: String, source_archive_folder: String) -> Result<Value, String> {
    if folder.trim().is_empty() {
        return Err("No batch source folder selected.".to_string());
    }
    if output_folder.trim().is_empty() {
        return Err("No processed PDF output folder selected.".to_string());
    }

    let source_dir = PathBuf::from(&folder);
    if !source_dir.exists() {
        return Err(format!("Batch source folder does not exist: {}", source_dir.display()));
    }

    let mut pdfs = Vec::new();
    collect_pdf_files(&source_dir, &mut pdfs)
        .map_err(|error| format!("Failed to scan batch folder {}: {error}", source_dir.display()))?;
    pdfs.sort();

    let _ = app.emit("po_batch_log", format!("Found {} PDF file(s) in batch folder.", pdfs.len()));
    if pdfs.is_empty() {
        return Ok(serde_json::json!({
            "ok": false,
            "folder": folder,
            "count": 0,
            "results": [],
            "error": "No PDF files were found in the selected folder."
        }));
    }

    let mut results = Vec::new();
    for (index, pdf) in pdfs.iter().enumerate() {
        let path_string = pdf.to_string_lossy().to_string();
        let _ = app.emit("po_batch_log", format!("Processing {}/{}: {}", index + 1, pdfs.len(), pdf.display()));
        match process_pdf_blocking(path_string.clone(), output_folder.clone(), source_archive_folder.clone()) {
            Ok(value) => {
                let _ = app.emit("po_batch_log", format!("Done: {}", pdf.display()));
                let _ = app.emit("po_batch_result", value.clone());
                results.push(value);
            }
            Err(error) => {
                let _ = app.emit("po_batch_log", format!("Failed: {} ({error})", pdf.display()));
                let value = serde_json::json!({
                    "ok": false,
                    "source": path_string,
                    "error": error,
                    "rows": []
                });
                let _ = app.emit("po_batch_result", value.clone());
                results.push(value);
            }
        }
    }

    Ok(serde_json::json!({
        "ok": true,
        "folder": folder,
        "count": pdfs.len(),
        "results": results
    }))
}

fn collect_pdf_files(dir: &PathBuf, pdfs: &mut Vec<PathBuf>) -> Result<(), std::io::Error> {
    for entry in fs::read_dir(dir)? {
        let path = entry?.path();
        if path
            .is_file()
            && path
            .extension()
            .and_then(|extension| extension.to_str())
            .map(|extension| extension.eq_ignore_ascii_case("pdf"))
            .unwrap_or(false)
        {
            pdfs.push(path);
        }
    }
    Ok(())
}

#[tauri::command]
async fn ensure_excel(excel_path: String, field_keys: Option<Vec<String>>) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || ensure_excel_blocking(excel_path, field_keys)).await.map_err(|error| format!("Excel task failed: {error}"))?
}

fn ensure_excel_blocking(excel_path: String, field_keys: Option<Vec<String>>) -> Result<Value, String> {
    if excel_path.trim().is_empty() {
        return Err("No Excel target selected.".to_string());
    }

    if let Some(keys) = field_keys {
        let keys_json = serde_json::to_string(&keys).map_err(|error| format!("Failed to serialize Excel fields: {error}"))?;
        run_sidecar(&["--ensure-excel-fields", &excel_path, &keys_json])
    } else {
        run_sidecar(&["--ensure-excel", &excel_path])
    }
}

#[tauri::command]
async fn append_excel_record(excel_path: String, record_json: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || append_excel_record_blocking(excel_path, record_json)).await.map_err(|error| format!("Excel append task failed: {error}"))?
}

fn append_excel_record_blocking(excel_path: String, record_json: String) -> Result<Value, String> {
    if excel_path.trim().is_empty() {
        return Err("No Excel target selected.".to_string());
    }

    let millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| format!("System clock error: {error}"))?
        .as_millis();
    let temp_path = std::env::temp_dir().join(format!("urice-po-record-{millis}.json"));
    fs::write(&temp_path, record_json).map_err(|error| {
        format!("Failed to write temporary Excel record file {}: {error}", temp_path.display())
    })?;

    let temp_path_string = temp_path.to_string_lossy().to_string();
    let result = run_sidecar(&["--append-record-file", &excel_path, &temp_path_string]);
    let _ = fs::remove_file(&temp_path);
    result
}

#[tauri::command]
async fn inspect_excel_headers(path: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || inspect_excel_headers_blocking(path)).await.map_err(|error| format!("Inspect Excel task failed: {error}"))?
}

fn inspect_excel_headers_blocking(path: String) -> Result<Value, String> {
    if path.trim().is_empty() {
        return Err("No Excel path selected.".to_string());
    }

    run_sidecar(&["--inspect-excel", &path])
}

#[tauri::command]
async fn merge_excel_sources(output_path: String, sources: Vec<Value>) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || merge_excel_sources_blocking(output_path, sources)).await.map_err(|error| format!("Merge Excel task failed: {error}"))?
}

fn merge_excel_sources_blocking(output_path: String, sources: Vec<Value>) -> Result<Value, String> {
    if output_path.trim().is_empty() {
        return Err("No Excel output path selected.".to_string());
    }
    if sources.is_empty() {
        return Err("No Excel source selected.".to_string());
    }

    let millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| format!("System clock error: {error}"))?
        .as_millis();
    let temp_path = std::env::temp_dir().join(format!("urice-excel-merge-{millis}.json"));
    let content = serde_json::to_string(&sources).map_err(|error| format!("Failed to serialize merge sources: {error}"))?;
    fs::write(&temp_path, content).map_err(|error| {
        format!("Failed to write temporary merge source file {}: {error}", temp_path.display())
    })?;

    let temp_path_string = temp_path.to_string_lossy().to_string();
    let result = run_sidecar(&["--merge-excel-file", &output_path, &temp_path_string]);
    let _ = fs::remove_file(&temp_path);
    result
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            app_version,
            load_app_settings,
            save_app_settings,
            engine_health,
            extract_pdf,
            process_pdf,
            save_processed_pdf,
            process_batch,
            list_pdf_files,
            move_sources_to_archive,
            ensure_excel,
            append_excel_record,
            inspect_excel_headers,
            merge_excel_sources
        ])
        .run(tauri::generate_context!())
        .expect("error while running URice Tools Client");
}

