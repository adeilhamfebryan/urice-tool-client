import { invoke } from "@tauri-apps/api/core";
import { confirm, open } from "@tauri-apps/plugin-dialog";
import { AlertCircle, CheckCircle2, FileUp, Loader2, Play, Save, Table2 } from "lucide-react";
import { useEffect, useState } from "react";
import type { AppSettings } from "../../App";

type HealthResponse = {
  ok: boolean;
  engine: string;
  version: string;
  tesseract_configured?: boolean;
};

type ExtractionRow = {
  tanggal_proses: string;
  no_op: string;
  vendor_name: string;
  vendor_code: string;
};

type ProcessResponse = {
  ok: boolean;
  source?: string;
  processed_pdf_path?: string;
  processed_pdf_filename?: string;
  company_name?: string;
  rows?: ExtractionRow[];
  error?: string;
};

type PdfListResponse = {
  ok: boolean;
  count: number;
  files: string[];
  error?: string;
};

type MoveSourcesResponse = {
  ok: boolean;
  moved: Array<{ ok: boolean; source: string; archived_path?: string; error?: string }>;
};

type CorrectedRecord = {
  tanggal_diproses: string;
  company_name: string;
  nomor_op: string;
  nama_vendor: string;
  nomor_vendor: string;
  keterangan: string;
  status: string;
  source_pdf?: string;
  processed_pdf?: string;
};

type Props = {
  settings: AppSettings;
  updateSettings: (patch: Partial<AppSettings>) => void;
  addHistory: (action: string, detail: string) => void;
};

const editableColumns: Array<{ key: keyof CorrectedRecord; label: string; placeholder?: string }> = [
  { key: "tanggal_diproses", label: "Tanggal Diproses" },
  { key: "company_name", label: "Company Name" },
  { key: "nomor_op", label: "Nomor OP" },
  { key: "nama_vendor", label: "Nama Vendor" },
  { key: "nomor_vendor", label: "Nomor Vendor" },
  { key: "keterangan", label: "Keterangan", placeholder: "Isi manual" },
  { key: "status", label: "Status", placeholder: "Isi manual" },
];

function fileName(path: string) {
  return path.split(/[\\/]/).pop() || path;
}

export function PoPdfManager({ settings, addHistory }: Props) {
  const [selectedPath, setSelectedPath] = useState<string>("");
  const [engineStatus, setEngineStatus] = useState<string>("Checking engine...");
  const [engineReady, setEngineReady] = useState<boolean | null>(null);
  const [processedPdfPath, setProcessedPdfPath] = useState<string>("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [mode, setMode] = useState<"single" | "batch">("single");
  const [batchFolder, setBatchFolder] = useState<string>("");
  const [logs, setLogs] = useState<string[]>([]);
  const [previewRows, setPreviewRows] = useState<CorrectedRecord[]>([]);

  function log(line: string) {
    setLogs((current) => [`${new Date().toLocaleTimeString()} - ${line}`, ...current].slice(0, 200));
  }

  async function checkEngine() {
    setEngineStatus("Checking engine...");
    try {
      const result = await invoke<HealthResponse>("engine_health");
      setEngineReady(result.ok);
      setEngineStatus(`${result.engine} ${result.version}: ${result.ok ? "ready" : "unavailable"}`);
      log(`Engine check: ${result.ok ? "ready" : "unavailable"}${result.tesseract_configured ? ", Tesseract bundled" : ""}`);
    } catch (error) {
      setEngineReady(false);
      setEngineStatus(`Engine bridge unavailable: ${String(error)}`);
      log(`Engine check failed: ${String(error)}`);
    }
  }

  useEffect(() => {
    void checkEngine();
  }, []);

  function recordFromProcessResult(result: ProcessResponse): CorrectedRecord {
    const first = result.rows?.[0];
    return {
      tanggal_diproses: first?.tanggal_proses || new Date().toLocaleString(),
      company_name: result.company_name || "",
      nomor_op: first?.no_op || "",
      nama_vendor: first?.vendor_name || "",
      nomor_vendor: first?.vendor_code || "",
      keterangan: "",
      status: "",
      source_pdf: result.source,
      processed_pdf: result.processed_pdf_path,
    };
  }

  function setSinglePreview(result: ProcessResponse) {
    const row = recordFromProcessResult(result);
    setPreviewRows([row]);
    setProcessedPdfPath(row.processed_pdf || "");
    return row;
  }

  function appendPreview(result: ProcessResponse) {
    const row = recordFromProcessResult(result);
    setPreviewRows((current) => [...current, row]);
    setProcessedPdfPath((current) => current || row.processed_pdf || "");
    return row;
  }

  function updatePreviewRow(index: number, key: keyof CorrectedRecord, value: string) {
    setPreviewRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, [key]: value } : row)),
    );
  }

  async function choosePdf() {
    const picked = await open({ multiple: false, filters: [{ name: "PDF", extensions: ["pdf"] }] });
    if (typeof picked === "string") {
      setSelectedPath(picked);
      setProcessedPdfPath("");
      setPreviewRows([]);
      setMessage("PDF selected. Run Process PDF to create preview.");
      log(`Single PDF selected: ${picked}`);
    }
  }

  async function chooseBatchFolder() {
    const picked = await open({ directory: true, multiple: false });
    if (typeof picked === "string") {
      setBatchFolder(picked);
      setPreviewRows([]);
      setProcessedPdfPath("");
      setMessage("Batch folder selected. Run Process Batch to scan PDF files in this folder only.");
      log(`Batch folder selected: ${picked}`);
    }
  }

  function validateSettings() {
    if (!settings.excelPath) {
      setMessage("Please select or create an Excel target first in Settings.");
      return false;
    }
    if (!settings.processedOutputFolder) {
      setMessage("Please choose a processed PDF output folder first in Settings.");
      return false;
    }
    return true;
  }

  async function processPdf() {
    if (!selectedPath || !validateSettings()) return;

    setIsProcessing(true);
    setMessage("Processing PDF...");
    log(`Reading source PDF: ${selectedPath}`);
    log(`OCR reading first page: ${fileName(selectedPath)}`);
    try {
      const result = await invoke<ProcessResponse>("process_pdf", {
        path: selectedPath,
        outputFolder: settings.processedOutputFolder,
        sourceArchiveFolder: "",
      });
      if (!result.ok) {
        setMessage(result.error || "Process failed.");
        log(result.error || "Single PDF process failed");
        return;
      }
      const row = setSinglePreview(result);
      log(`First page saved: ${result.processed_pdf_filename || fileName(result.processed_pdf_path || "")}`);
      log(`Saved to: ${result.processed_pdf_path || "-"}`);
      log(`Preview row ready: ${row.nama_vendor || "Vendor kosong"} / ${row.nomor_op || "No OP kosong"}`);
      setMessage("Preview ready. Review the row, then Apply Preview to Excel.");
      addHistory("PDF processed", `${selectedPath} -> ${result.processed_pdf_path || "processed output"}`);
    } catch (error) {
      setMessage(`Process bridge failed: ${String(error)}`);
      log(`Process bridge failed: ${String(error)}`);
    } finally {
      setIsProcessing(false);
    }
  }

  async function processBatch() {
    if (!batchFolder || !validateSettings()) return;

    setIsProcessing(true);
    setPreviewRows([]);
    setProcessedPdfPath("");
    setMessage("Scanning batch folder...");
    log(`Scanning batch folder only, no subfolders: ${batchFolder}`);
    try {
      const list = await invoke<PdfListResponse>("list_pdf_files", { folder: batchFolder });
      if (!list.ok || !list.files.length) {
        setMessage(list.error || "No PDF files were found in the selected folder.");
        log(list.error || "No PDF files found in selected folder.");
        return;
      }

      log(`Found ${list.count} PDF source file(s).`);
      let success = 0;
      let failed = 0;
      for (let index = 0; index < list.files.length; index += 1) {
        const pdf = list.files[index];
        log(`Processing ${index + 1}/${list.files.length}: ${fileName(pdf)}`);
        log(`OCR reading first page: ${fileName(pdf)}`);
        const result = await invoke<ProcessResponse>("process_pdf", {
          path: pdf,
          outputFolder: settings.processedOutputFolder,
          sourceArchiveFolder: "",
        });
        if (!result.ok) {
          failed += 1;
          log(`Failed ${fileName(pdf)}: ${result.error || "unknown error"}`);
          continue;
        }
        success += 1;
        const row = appendPreview(result);
        log(`First page saved: ${result.processed_pdf_filename || fileName(result.processed_pdf_path || "")}`);
        log(`Saved to: ${result.processed_pdf_path || "-"}`);
        log(`Preview row added: ${row.nama_vendor || "Vendor kosong"} / ${row.nomor_op || "No OP kosong"}`);
      }

      setMessage(`Batch OCR completed: ${success}/${list.count} PDF ready for preview, ${failed} failed. Review rows, then Apply Preview to Excel.`);
      log(`Batch OCR completed: ${success}/${list.count} PDF ready, ${failed} failed.`);
      addHistory("Batch OCR completed", `${batchFolder}: ${success}/${list.count} PDF ready`);
    } catch (error) {
      setMessage(`Batch process failed: ${String(error)}`);
      log(`Batch process failed: ${String(error)}`);
    } finally {
      setIsProcessing(false);
    }
  }

  async function moveSourcesAfterApply() {
    if (!settings.sourceArchiveFolder) {
      log("Source archive folder is not set. Source PDF move skipped.");
      return;
    }
    const paths = Array.from(new Set(previewRows.map((row) => row.source_pdf).filter(Boolean))) as string[];
    if (!paths.length) return;

    log(`Moving ${paths.length} source PDF(s) to archive: ${settings.sourceArchiveFolder}`);
    const result = await invoke<MoveSourcesResponse>("move_sources_to_archive", {
      paths,
      archiveFolder: settings.sourceArchiveFolder,
    });
    const moved = result.moved.filter((item) => item.ok);
    for (const item of result.moved) {
      if (item.ok) {
        log(`Source moved: ${fileName(item.source)} -> ${item.archived_path}`);
      } else {
        log(`Source move failed: ${fileName(item.source)} (${item.error || "unknown error"})`);
      }
    }
    addHistory("Source archive moved", `${moved.length}/${paths.length} PDF moved to ${settings.sourceArchiveFolder}`);
  }

  async function applyToExcel() {
    if (!settings.excelPath) {
      setMessage("Please select or create an Excel target first in Settings.");
      return;
    }
    if (!previewRows.length) {
      setMessage("No preview rows to apply yet.");
      return;
    }

    const approved = await confirm(
      `Apply ${previewRows.length} preview row(s) to Excel?\n\nTarget:\n${settings.excelPath}`,
      { title: "Confirm Apply to Excel", kind: "warning" },
    );
    if (!approved) {
      setMessage("Apply to Excel cancelled.");
      log("Apply to Excel cancelled by user.");
      return;
    }

    setIsApplying(true);
    setMessage(`Applying ${previewRows.length} row(s) to Excel...`);
    log(`Applying ${previewRows.length} preview row(s) to Excel: ${settings.excelPath}`);
    try {
      let lastRow = 0;
      for (const row of previewRows) {
        const result = await invoke<{ ok: boolean; excel_path: string; row: number }>("append_excel_record", {
          excelPath: settings.excelPath,
          recordJson: JSON.stringify(row),
        });
        lastRow = result.row;
        log(`Excel updated at row ${result.row}: ${row.nomor_op || row.nama_vendor || "preview row"}`);
      }
      await moveSourcesAfterApply();
      setMessage(`Applied ${previewRows.length} row(s) to Excel. Last row: ${lastRow}. Source move completed if archive folder is set.`);
      addHistory("Excel updated", `${settings.excelPath} up to row ${lastRow}`);
      setSelectedPath("");
      setBatchFolder("");
      setProcessedPdfPath("");
      setPreviewRows([]);
      setMessage("");
      log("PO Manager reset after successful apply. Realtime log retained.");
    } catch (error) {
      setMessage(`Failed to update Excel: ${String(error)}`);
      log(`Excel update failed: ${String(error)}`);
    } finally {
      setIsApplying(false);
    }
  }

  return (
    <section className="work-panel" id="po">
      <div className="panel-header">
        <div>
          <p className="eyebrow"><Table2 size={14} /> PO workflow</p>
          <h2>PO PDF Manager</h2>
        </div>
        <button className="secondary-button" onClick={checkEngine}>Check Engine</button>
      </div>

      <div className="mode-toggle" role="tablist" aria-label="Processing mode">
        <button className={mode === "single" ? "active" : ""} type="button" onClick={() => setMode("single")}>Single PDF</button>
        <button className={mode === "batch" ? "active" : ""} type="button" onClick={() => setMode("batch")}>Batch Mode</button>
      </div>

      <div className="workflow-steps compact">
        {mode === "single" ? (
          <button className="step-button" onClick={choosePdf}><FileUp size={18} /> Choose Single PDF</button>
        ) : (
          <button className="step-button" onClick={chooseBatchFolder}><FileUp size={18} /> Choose PDF Source Folder</button>
        )}
      </div>

      <div className="selected-paths">
        <span><strong>Excel target:</strong> {settings.excelPath || "Set in Settings"}</span>
        <span><strong>Processed PDF folder:</strong> {settings.processedOutputFolder || "Set in Settings"}</span>
        <span><strong>Source archive:</strong> {settings.sourceArchiveFolder || "Optional / set in Settings"}</span>
        <span><strong>Selected PDF:</strong> {selectedPath || "Belum dipilih"}</span>
        <span><strong>Batch folder:</strong> {batchFolder || "Belum dipilih"}</span>
        {processedPdfPath && <span><strong>First processed PDF:</strong> {processedPdfPath}</span>}
      </div>

      <div className="action-row">
        <button className="primary-button" disabled={isProcessing || (mode === "single" ? !selectedPath : !batchFolder)} onClick={mode === "single" ? processPdf : processBatch}>
          {isProcessing ? <Loader2 className="spin" size={16} /> : <Play size={16} />}
          {mode === "single" ? "Process PDF" : "Process Batch"}
        </button>
        <button className="primary-button muted" disabled={isApplying || !previewRows.length} onClick={applyToExcel}>
          {isApplying ? <Loader2 className="spin" size={16} /> : <Save size={16} />}
          Apply Preview to Excel
        </button>
      </div>

      <div className="status-line status-with-icon">
        {engineReady ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
        Python backend: {engineStatus}
      </div>
      <div className="status-line">{message || "Select an Excel target in Settings, then process a PO PDF or batch folder."}</div>

      <div className="realtime-log">
        <strong>Realtime Log</strong>
        {logs.length ? logs.map((item, index) => <span key={index}>{item}</span>) : <span>No process log yet.</span>}
      </div>

      <div className="preview-table-wrap">
        <table className="preview-table editable-preview-table">
          <thead>
            <tr>
              <th>No</th>
              {editableColumns.map((column) => <th key={column.key}>{column.label}</th>)}
              <th>Source PDF</th>
              <th>Processed PDF</th>
            </tr>
          </thead>
          <tbody>
            {previewRows.length ? previewRows.map((row, rowIndex) => (
              <tr key={`${row.source_pdf || "row"}-${rowIndex}`}>
                <td>{rowIndex + 1}</td>
                {editableColumns.map((column) => (
                  <td key={column.key}>
                    <input
                      value={String(row[column.key] || "")}
                      placeholder={column.placeholder}
                      onChange={(event) => updatePreviewRow(rowIndex, column.key, event.target.value)}
                    />
                  </td>
                ))}
                <td>{row.source_pdf || <span className="empty-cell">-</span>}</td>
                <td>{row.processed_pdf || <span className="empty-cell">-</span>}</td>
              </tr>
            )) : (
              <tr>
                <td colSpan={10} className="empty-cell">No preview rows yet. Process a single PDF or batch folder first.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
