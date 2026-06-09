import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import { FileSpreadsheet, Loader2, Plus, Save, Trash2 } from "lucide-react";
import { useState } from "react";
import type { AppSettings } from "../../config/appSettings";
import { mergerStandardColumns, type MergerStandardColumn } from "../../config/mergerFields";

type InspectExcelResponse = {
  ok: boolean;
  path: string;
  sheet: string;
  headers: string[];
  row_count: number;
  error?: string;
};

type MergeResponse = {
  ok: boolean;
  output_path: string;
  headers: string[];
  row_count: number;
  sources: Array<{ source_name: string; path: string; ok: boolean; row_count?: number; error?: string }>;
};

type MergerSource = {
  path: string;
  sourceName: string;
  sheet: string;
  headers: string[];
  rowCount: number;
  mapping: Record<string, MergerStandardColumn | "">;
};

type Props = {
  settings: AppSettings;
  addHistory: (action: string, detail: string) => void;
};

function fileName(path: string) {
  return path.split(/[\\/]/).pop() || path;
}

function guessSourceName(path: string) {
  const upper = fileName(path).toUpperCase();
  if (upper.includes("SAP")) return "SAP";
  if (upper.includes("PB")) return "PB";
  if (upper.includes("PI")) return "PI";
  if (upper.includes("COM")) return "COM";
  return "Custom";
}

function suggestMapping(header: string): MergerStandardColumn | "" {
  const normalized = header.toLowerCase().replace(/[^a-z0-9]/g, "");
  const hints: Array<[MergerStandardColumn, string[]]> = [
    ["Nomor PO", ["po", "purchaseorder", "purchasingdocument", "nomorpo"]],
    ["Nomor PR", ["pr", "purchaserequisition", "nomorpr"]],
    ["Nomor GR", ["gr", "goodsreceipt", "nomorgr"]],
    ["Vendor Code", ["vendorcode", "kodevendor", "vendor"]],
    ["Vendor Name", ["vendorname", "namavendor", "supplier"]],
    ["Material Code", ["materialcode", "kodematerial", "material"]],
    ["Nama Barang", ["materialdescription", "namabarang", "description", "itemname"]],
    ["Qty", ["qty", "quantity", "orderquantity", "banyaknya"]],
    ["Satuan", ["unit", "uom", "satuan"]],
    ["Harga Satuan", ["netprice", "price", "hargasatuan"]],
    ["Total", ["total", "amount", "value"]],
    ["Tanggal", ["date", "tanggal"]],
    ["Plant", ["plant", "dept", "department"]],
    ["Status", ["status"]],
    ["Keterangan", ["remark", "note", "keterangan"]],
  ];
  return hints.find(([_target, patterns]) => patterns.some((pattern) => normalized.includes(pattern)))?.[0] || "";
}

export function ExcelMerger({ addHistory }: Props) {
  const [sources, setSources] = useState<MergerSource[]>([]);
  const [isInspecting, setIsInspecting] = useState(false);
  const [isMerging, setIsMerging] = useState(false);
  const [message, setMessage] = useState("Select Excel source files, map their columns, then export a normalized workbook.");
  const [logs, setLogs] = useState<string[]>([]);

  function log(line: string) {
    setLogs((current) => [`${new Date().toLocaleTimeString()} - ${line}`, ...current].slice(0, 160));
  }

  async function addSources() {
    const picked = await open({
      multiple: true,
      filters: [{ name: "Excel Workbook", extensions: ["xlsx", "xlsm", "xltx", "xltm"] }],
    });
    const paths = Array.isArray(picked) ? picked : typeof picked === "string" ? [picked] : [];
    if (!paths.length) return;

    setIsInspecting(true);
    setMessage(`Reading ${paths.length} Excel source file(s)...`);
    try {
      const inspected: MergerSource[] = [];
      for (const path of paths) {
        log(`Reading headers: ${path}`);
        const result = await invoke<InspectExcelResponse>("inspect_excel_headers", { path });
        if (!result.ok) {
          log(`Failed to inspect ${fileName(path)}: ${result.error || "unknown error"}`);
          continue;
        }
        const mapping = Object.fromEntries(result.headers.map((header) => [header, suggestMapping(header)]));
        inspected.push({
          path: result.path,
          sourceName: guessSourceName(result.path),
          sheet: result.sheet,
          headers: result.headers,
          rowCount: result.row_count,
          mapping,
        });
        log(`Loaded ${fileName(result.path)}: ${result.headers.length} header(s), ${result.row_count} row(s).`);
      }
      setSources((current) => [...current, ...inspected]);
      setMessage(`${inspected.length} source file(s) ready for mapping.`);
      addHistory("Excel source inspected", `${inspected.length} workbook(s) loaded for merger mapping`);
    } catch (error) {
      setMessage(`Failed to inspect Excel source: ${String(error)}`);
      log(`Inspect failed: ${String(error)}`);
    } finally {
      setIsInspecting(false);
    }
  }

  function updateSource(index: number, patch: Partial<MergerSource>) {
    setSources((current) => current.map((source, sourceIndex) => (sourceIndex === index ? { ...source, ...patch } : source)));
  }

  function updateMapping(sourceIndex: number, header: string, target: MergerStandardColumn | "") {
    setSources((current) =>
      current.map((source, index) =>
        index === sourceIndex ? { ...source, mapping: { ...source.mapping, [header]: target } } : source,
      ),
    );
  }

  async function exportMergedExcel() {
    if (!sources.length) {
      setMessage("No Excel source selected yet.");
      return;
    }
    const outputPath = await save({
      defaultPath: "URice_Merged_Data.xlsx",
      filters: [{ name: "Excel Workbook", extensions: ["xlsx"] }],
    });
    if (typeof outputPath !== "string") return;

    setIsMerging(true);
    setMessage("Merging normalized Excel data...");
    log(`Export target: ${outputPath}`);
    try {
      const payload = sources.map((source) => ({
        path: source.path,
        source_name: source.sourceName,
        mapping: Object.fromEntries(Object.entries(source.mapping).filter(([_header, target]) => target)),
      }));
      const result = await invoke<MergeResponse>("merge_excel_sources", { outputPath, sources: payload });
      setMessage(`Merged ${result.row_count} row(s) into ${result.output_path}`);
      log(`Merge completed: ${result.row_count} row(s), ${result.headers.length} output column(s).`);
      for (const source of result.sources) {
        log(source.ok ? `${source.source_name}: ${source.row_count || 0} row(s)` : `${source.source_name}: ${source.error || "failed"}`);
      }
      addHistory("Excel merger exported", `${result.row_count} row(s) exported to ${result.output_path}`);
    } catch (error) {
      setMessage(`Merge failed: ${String(error)}`);
      log(`Merge failed: ${String(error)}`);
    } finally {
      setIsMerging(false);
    }
  }

  return (
    <section className="work-panel" id="excel-merger">
      <div className="panel-header">
        <div>
          <p className="eyebrow"><FileSpreadsheet size={14} /> Excel Merger</p>
          <h2>Excel Merger for SAP, PB, PI, COM</h2>
        </div>
        <button className="secondary-button" type="button" onClick={addSources} disabled={isInspecting}>
          {isInspecting ? <Loader2 className="spin" size={16} /> : <Plus size={16} />}
          Add Excel Source
        </button>
      </div>

      <div className="status-line">{message}</div>

      <div className="action-row">
        <button className="primary-button" type="button" disabled={isMerging || !sources.length} onClick={exportMergedExcel}>
          {isMerging ? <Loader2 className="spin" size={16} /> : <Save size={16} />}
          Export Normalized Excel
        </button>
      </div>

      <div className="merger-source-list">
        {sources.length ? sources.map((source, sourceIndex) => (
          <article className="settings-card merger-source-card" key={`${source.path}-${sourceIndex}`}>
            <div className="settings-card-header">
              <div>
                <span className="settings-label">{fileName(source.path)}</span>
                <strong>{source.rowCount} row(s) in {source.sheet}</strong>
              </div>
              <button className="secondary-button compact-button" type="button" onClick={() => setSources((current) => current.filter((_source, index) => index !== sourceIndex))}>
                <Trash2 size={15} />
                Remove
              </button>
            </div>
            <label>
              Source Type
              <select value={source.sourceName} onChange={(event) => updateSource(sourceIndex, { sourceName: event.target.value })}>
                <option>SAP</option>
                <option>PB</option>
                <option>PI</option>
                <option>COM</option>
                <option>Custom</option>
              </select>
            </label>
            <div className="mapping-grid">
              {source.headers.map((header) => (
                <label key={header}>
                  <span>{header}</span>
                  <select value={source.mapping[header] || ""} onChange={(event) => updateMapping(sourceIndex, header, event.target.value as MergerStandardColumn | "")}>
                    <option value="">Do not import</option>
                    {mergerStandardColumns.filter((column) => column !== "Source").map((column) => (
                      <option key={column} value={column}>{column}</option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          </article>
        )) : (
          <div className="empty-merger-state">
            <FileSpreadsheet size={26} />
            <p>No Excel source loaded yet.</p>
          </div>
        )}
      </div>

      <div className="realtime-log">
        <strong>Merger Log</strong>
        {logs.length ? logs.map((item, index) => <span key={index}>{item}</span>) : <span>No merger activity yet.</span>}
      </div>
    </section>
  );
}
