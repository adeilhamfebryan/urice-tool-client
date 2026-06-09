import { motion } from "framer-motion";
import { confirm, message, open, save } from "@tauri-apps/plugin-dialog";
import { invoke } from "@tauri-apps/api/core";
import { getVersion } from "@tauri-apps/api/app";
import { relaunch } from "@tauri-apps/plugin-process";
import { check, type DownloadEvent } from "@tauri-apps/plugin-updater";
import {
  Activity,
  FileSpreadsheet,
  FileText,
  History,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Settings,
  Sparkles,
  Sun,
} from "lucide-react";
import { useEffect, useState } from "react";
import logoUrl from "./assets/urice_logo.ico";
import { BrandScene } from "./components/BrandScene";
import { defaultAppSettings, normalizeAppSettings, type AppSettings } from "./config/appSettings";
import { defaultExtractionFields, extractionFieldOptions, type ExtractionFieldKey } from "./config/extractionFields";
import { ToolCard } from "./components/ToolCard";
import { ExcelMerger } from "./modules/excel-merger/ExcelMerger";
import { PoPdfManager } from "./modules/po-pdf-manager/PoPdfManager";

type ViewName = "po" | "merger" | "history" | "settings";
type UpdatePhase = "idle" | "checking" | "available" | "downloading" | "installing" | "restarting" | "error";

export type HistoryEntry = {
  time: string;
  action: string;
  detail: string;
};

const tools = [
  {
    title: "PO PDF Manager",
    description: "Extract PO data from scanned PDFs, review OCR output, and export clean Excel rows. Requested by Commercial Division CPI Lampung.",
    status: "Intellegence tools make you more efficience",
    icon: FileText,
  },
  {
    title: "Batch Automation",
    description: "Queue folder jobs and keep OCR work running in the background.",
    status: "Operational",
    icon: Activity,
  },
  {
    title: "Auto Update",
    description: "Check and install signed GitHub release updates directly from Settings without command-line work.",
    status: "Enabled",
    icon: RefreshCw,
  },
  {
    title: "Excel Merger",
    description: "Normalize SAP, PB, PI, and COM Excel exports through reusable column mapping.",
    status: "V1.1.0 Foundation",
    icon: FileSpreadsheet,
  },
];

const navItems = [
  { view: "po" as const, label: "PO Manager", icon: FileText },
  { view: "merger" as const, label: "Excel Merger", icon: FileSpreadsheet },
  { view: "history" as const, label: "History", icon: Activity },
  { view: "settings" as const, label: "Settings", icon: Settings },
];

function formatUpdateError(error: unknown) {
  const messageText = String(error);
  if (
    messageText.includes("Could not fetch a valid release JSON") ||
    messageText.includes("404") ||
    messageText.includes("latest.json")
  ) {
    return "Belum ada paket update yang tersedia di server. Ini normal sebelum release GitHub pertama berhasil dipublish.";
  }
  return `Gagal memeriksa update: ${messageText}`;
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value.toFixed(value >= 10 || exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

export function App() {
  const [activeView, setActiveView] = useState<ViewName>("po");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [appVersion, setAppVersion] = useState<string>("loading...");
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [settingsStatus, setSettingsStatus] = useState("Loading local settings...");
  const [updateStatus, setUpdateStatus] = useState<string>("Auto checker will run when the app starts.");
  const [updatePhase, setUpdatePhase] = useState<UpdatePhase>("idle");
  const [updateProgress, setUpdateProgress] = useState(0);
  const [updateDownloaded, setUpdateDownloaded] = useState(0);
  const [updateTotal, setUpdateTotal] = useState<number | null>(null);
  const [updateTargetVersion, setUpdateTargetVersion] = useState<string>("");
  const [settings, setSettings] = useState<AppSettings>(defaultAppSettings);

  function updateSettings(patch: Partial<AppSettings>) {
    setSettings((current) => ({ ...current, ...patch }));
  }

  function addHistory(action: string, detail: string) {
    setHistory((current) => [
      { time: new Date().toLocaleString(), action, detail },
      ...current,
    ].slice(0, 100));
  }

  async function checkForUpdates(manual = false) {
    try {
      setUpdatePhase("checking");
      setUpdateProgress(0);
      setUpdateDownloaded(0);
      setUpdateTotal(null);
      setUpdateTargetVersion("");
      setUpdateStatus(manual ? "Checking for updates..." : "Auto checking for updates...");
      const update = await check();
      if (!update) {
        setUpdatePhase("idle");
        setUpdateStatus("URice Tools Client is already up to date.");
        if (manual) {
          await message("URice Tools Client sudah versi terbaru.", { title: "No Update Available", kind: "info" });
        }
        return;
      }

      setUpdatePhase("available");
      setUpdateTargetVersion(update.version);
      setUpdateStatus(`Update ${update.version} is available.`);
      const approved = await confirm(
        `URice Tools Client versi ${update.version} tersedia.\n\nInstall update sekarang?`,
        { title: "Update Available", kind: "info" },
      );
      if (!approved) {
        setUpdatePhase("idle");
        setUpdateStatus(`Update ${update.version} is available but was postponed.`);
        return;
      }

      let downloadedBytes = 0;
      let totalBytes: number | null = null;
      setUpdatePhase("downloading");
      setUpdateStatus(`Downloading and installing update ${update.version}...`);
      await update.downloadAndInstall((event: DownloadEvent) => {
        if (event.event === "Started") {
          downloadedBytes = 0;
          totalBytes = event.data.contentLength ?? null;
          setUpdateDownloaded(0);
          setUpdateTotal(totalBytes);
          setUpdateProgress(0);
          setUpdateStatus(totalBytes ? `Downloading update ${update.version} (0 / ${formatBytes(totalBytes)})...` : `Downloading update ${update.version}...`);
        }
        if (event.event === "Progress") {
          downloadedBytes += event.data.chunkLength;
          setUpdateDownloaded(downloadedBytes);
          if (totalBytes) {
            const percent = Math.min(100, Math.round((downloadedBytes / totalBytes) * 100));
            setUpdateProgress(percent);
            setUpdateStatus(`Downloading update ${update.version}: ${percent}% (${formatBytes(downloadedBytes)} / ${formatBytes(totalBytes)})`);
          } else {
            setUpdateStatus(`Downloading update ${update.version}: ${formatBytes(downloadedBytes)} received`);
          }
        }
        if (event.event === "Finished") {
          setUpdatePhase("installing");
          setUpdateProgress(100);
          setUpdateStatus(`Installing update ${update.version}...`);
        }
      });
      setUpdatePhase("restarting");
      setUpdateStatus("Update installed. Restarting URice Tools Client...");
      await relaunch();
    } catch (error) {
      const friendlyError = formatUpdateError(error);
      setUpdatePhase("error");
      setUpdateStatus(friendlyError);
      if (manual) {
        await message(friendlyError, { title: "Update Check Failed", kind: "error" });
      }
    }
  }

  useEffect(() => {
    void checkForUpdates(false);
    invoke<string>("app_version")
      .then(setAppVersion)
      .catch(() => getVersion().then(setAppVersion).catch(() => setAppVersion("unknown")));
  }, []);

  useEffect(() => {
    invoke<{ ok: boolean; settings: unknown; path: string }>("load_app_settings")
      .then((result) => {
        if (result.settings) {
          setSettings(normalizeAppSettings(result.settings));
          setSettingsStatus(`Settings loaded from ${result.path}`);
        } else {
          setSettingsStatus("No saved settings yet. Changes will be saved automatically.");
        }
      })
      .catch((error) => {
        setSettingsStatus(`Settings load failed: ${String(error)}`);
      })
      .finally(() => setSettingsLoaded(true));
  }, []);

  useEffect(() => {
    if (!settingsLoaded) return;
    const handle = window.setTimeout(() => {
      invoke("save_app_settings", { settings })
        .then(() => setSettingsStatus("Settings saved automatically."))
        .catch((error) => setSettingsStatus(`Settings save failed: ${String(error)}`));
    }, 450);
    return () => window.clearTimeout(handle);
  }, [settings, settingsLoaded]);

  async function selectExcelTarget() {
    const picked = await save({
      defaultPath: settings.excelPath || "Data_PO.xlsx",
      filters: [{ name: "Excel Workbook", extensions: ["xlsx"] }],
    });
    if (typeof picked === "string") {
      await invoke("ensure_excel", { excelPath: picked, fieldKeys: settings.selectedExtractionFields });
      updateSettings({ excelPath: picked });
      addHistory("Excel target selected", picked);
    }
  }

  async function chooseProcessedOutputFolder() {
    const picked = await open({ directory: true, multiple: false });
    if (typeof picked === "string") updateSettings({ processedOutputFolder: picked });
  }

  async function chooseSourceArchiveFolder() {
    const picked = await open({ directory: true, multiple: false });
    if (typeof picked === "string") updateSettings({ sourceArchiveFolder: picked });
  }

  function toggleExtractionField(key: ExtractionFieldKey) {
    updateSettings({
      selectedExtractionFields: settings.selectedExtractionFields.includes(key)
        ? settings.selectedExtractionFields.filter((field) => field !== key)
        : [...settings.selectedExtractionFields, key],
    });
  }

  return (
    <main className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""} ${settings.themeMode === "light" ? "theme-light" : "theme-dark"}`}>
      <aside className="sidebar" aria-label="Application sidebar">
        <div className="brand-row">
          <img className="brand-logo" src={logoUrl} alt="URice" />
          <div className="brand-copy">
            <p>Tools Client</p>
          </div>
        </div>

        <button
          className="sidebar-toggle"
          type="button"
          title={sidebarCollapsed ? "Maximize sidebar" : "Minimize sidebar"}
          aria-label={sidebarCollapsed ? "Maximize sidebar" : "Minimize sidebar"}
          onClick={() => setSidebarCollapsed((value) => !value)}
        >
          {sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          <span>{sidebarCollapsed ? "Open" : "Minimize"}</span>
        </button>

        <nav className="nav-list" aria-label="Primary navigation">
          {navItems.map(({ view, label, icon: Icon }) => (
            <button
              key={view}
              className={`nav-item ${activeView === view ? "active" : ""}`}
              type="button"
              title={label}
              aria-current={activeView === view ? "page" : undefined}
              onClick={() => setActiveView(view)}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <button
            className="icon-button mobile-sidebar-button"
            type="button"
            title="Toggle sidebar"
            aria-label="Toggle sidebar"
            onClick={() => setSidebarCollapsed((value) => !value)}
          >
            <Menu size={18} />
          </button>
          <div>
            <p className="eyebrow"><Sparkles size={14} /> URice Corporation</p>
            <strong>{navItems.find((item) => item.view === activeView)?.label}</strong>
          </div>
        </header>

        {(activeView === "po" || activeView === "merger") && (
          <>
            <header className="hero-band">
              <div className="hero-copy">
                <p className="eyebrow"><Sparkles size={14} /> URice Corporation</p>
                <motion.h2 initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
                  Mewujudkan ekosistem pekerjaan yang efisien.
                </motion.h2>
                <p>
                  URice Tools Client membantu tim non-IT memproses dokumen PO dengan alur yang jelas:
                  pilih Excel, proses PDF, koreksi preview, lalu apply ke data kerja.
                </p>
              </div>
              <BrandScene />
            </header>

            <section className="tool-grid" aria-label="Tool modules">
              {tools.map((tool) => <ToolCard key={tool.title} {...tool} />)}
            </section>
          </>
        )}

        <div hidden={activeView !== "po"}>
          <PoPdfManager settings={settings} updateSettings={updateSettings} addHistory={addHistory} />
        </div>

        <div hidden={activeView !== "merger"}>
          <ExcelMerger settings={settings} addHistory={addHistory} />
        </div>

        {activeView === "history" && (
          <section className="work-panel placeholder-panel" id="history">
            <p className="eyebrow"><Activity size={14} /> History</p>
            <h2>Processing History</h2>
            <div className="history-list">
              {history.length ? history.map((entry, index) => (
                <article className="history-item" key={`${entry.time}-${index}`}>
                  <strong>{entry.action}</strong>
                  <span>{entry.time}</span>
                  <p>{entry.detail}</p>
                </article>
              )) : <p>Belum ada aktivitas. Proses PDF pertama akan tercatat di sini.</p>}
            </div>
          </section>
        )}

        {activeView === "settings" && (
          <section className="work-panel placeholder-panel" id="settings">
            <p className="eyebrow"><Settings size={14} /> Settings</p>
            <h2>Application Settings</h2>
            <div className="settings-grid">
              <label>
                Application Version
                <input value={`URice Tools Client v${appVersion}`} readOnly />
              </label>
              <label>
                Local Settings
                <input value={settingsStatus} readOnly />
              </label>
              <div className="settings-card update-card">
                <div>
                  <span className="settings-label">Auto Update</span>
                  <strong>{updateTargetVersion ? `Target v${updateTargetVersion}` : "Signed GitHub Releases"}</strong>
                </div>
                <div className="update-progress" aria-label="Update progress">
                  <div
                    className={`update-progress-bar ${updatePhase}`}
                    style={{ width: `${updatePhase === "checking" ? 18 : updateProgress}%` }}
                  />
                </div>
                <p>{updateStatus}</p>
                {(updatePhase === "downloading" || updateDownloaded > 0) && (
                  <span className="update-bytes">
                    {formatBytes(updateDownloaded)}{updateTotal ? ` / ${formatBytes(updateTotal)}` : ""} downloaded
                  </span>
                )}
                <button className="secondary-button" type="button" onClick={() => void checkForUpdates(true)} disabled={["checking", "downloading", "installing", "restarting"].includes(updatePhase)}>
                  <RefreshCw size={16} />
                  {updatePhase === "checking" ? "Checking..." : "Check for Updates"}
                </button>
              </div>
              <label>
                Excel Target
                <input value={settings.excelPath || "Belum dipilih"} readOnly />
                <button className="secondary-button" type="button" onClick={selectExcelTarget}>Select / Create Excel</button>
              </label>
              <label>
                Processed PDF Output Folder
                <input value={settings.processedOutputFolder || "Belum dipilih"} readOnly />
                <button className="secondary-button" type="button" onClick={chooseProcessedOutputFolder}>Choose Output Folder</button>
              </label>
              <label>
                Processed Source Archive Folder
                <input value={settings.sourceArchiveFolder || "Opsional / belum dipilih"} readOnly />
                <button className="secondary-button" type="button" onClick={chooseSourceArchiveFolder}>Choose Archive Folder</button>
              </label>
              <div className="settings-card field-picker-card">
                <div className="settings-card-header">
                  <div>
                    <span className="settings-label">OCR / Excel Fields</span>
                    <strong>{settings.selectedExtractionFields.length} field selected</strong>
                  </div>
                  <button className="secondary-button compact-button" type="button" onClick={() => updateSettings({ selectedExtractionFields: defaultExtractionFields })}>
                    Reset
                  </button>
                </div>
                <div className="field-picker-list">
                  {extractionFieldOptions.map((field) => (
                    <label className="checkbox-row" key={field.key}>
                      <input
                        type="checkbox"
                        checked={settings.selectedExtractionFields.includes(field.key)}
                        onChange={() => toggleExtractionField(field.key)}
                      />
                      <span>
                        <strong>{field.label}</strong>
                        <small>{field.hint}</small>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
              <label>
                Batch Processing Threads
                <select
                  value={settings.batchConcurrency}
                  onChange={(event) => updateSettings({ batchConcurrency: Number(event.target.value) })}
                >
                  <option value={1}>1 thread - safest</option>
                  <option value={2}>2 threads - recommended</option>
                  <option value={3}>3 threads - faster</option>
                  <option value={4}>4 threads - heavier</option>
                </select>
              </label>
              <button className="secondary-button" type="button" onClick={() => updateSettings({ themeMode: settings.themeMode === "dark" ? "light" : "dark" })}>
                {settings.themeMode === "dark" ? <Sun size={16} /> : <Moon size={16} />}
                Switch to {settings.themeMode === "dark" ? "Light" : "Dark"} Theme
              </button>
            </div>
          </section>
        )}
      </section>
    </main>
  );
}



