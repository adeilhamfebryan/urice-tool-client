import { motion } from "framer-motion";
import { confirm, message, open, save } from "@tauri-apps/plugin-dialog";
import { invoke } from "@tauri-apps/api/core";
import { getVersion } from "@tauri-apps/api/app";
import { relaunch } from "@tauri-apps/plugin-process";
import { check } from "@tauri-apps/plugin-updater";
import {
  Activity,
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
import { ToolCard } from "./components/ToolCard";
import { PoPdfManager } from "./modules/po-pdf-manager/PoPdfManager";

type ViewName = "po" | "history" | "settings";
type ThemeMode = "dark" | "light";

export type AppSettings = {
  excelPath: string;
  processedOutputFolder: string;
  sourceArchiveFolder: string;
  themeMode: ThemeMode;
};

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
];

const navItems = [
  { view: "po" as const, label: "PO Manager", icon: FileText },
  { view: "history" as const, label: "History", icon: Activity },
  { view: "settings" as const, label: "Settings", icon: Settings },
];

export function App() {
  const [activeView, setActiveView] = useState<ViewName>("po");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [appVersion, setAppVersion] = useState<string>("0.1.0");
  const [updateStatus, setUpdateStatus] = useState<string>("Auto checker will run when the app starts.");
  const [settings, setSettings] = useState<AppSettings>({
    excelPath: "",
    processedOutputFolder: "",
    sourceArchiveFolder: "",
    themeMode: "dark",
  });

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
      setUpdateStatus(manual ? "Checking for updates..." : "Auto checking for updates...");
      const update = await check();
      if (!update) {
        setUpdateStatus("URice Tools Client is already up to date.");
        if (manual) {
          await message("URice Tools Client sudah versi terbaru.", { title: "No Update Available", kind: "info" });
        }
        return;
      }

      setUpdateStatus(`Update ${update.version} is available.`);
      const approved = await confirm(
        `URice Tools Client versi ${update.version} tersedia.\n\nInstall update sekarang?`,
        { title: "Update Available", kind: "info" },
      );
      if (!approved) {
        setUpdateStatus(`Update ${update.version} is available but was postponed.`);
        return;
      }

      setUpdateStatus(`Downloading and installing update ${update.version}...`);
      await update.downloadAndInstall();
      setUpdateStatus("Update installed. Restarting URice Tools Client...");
      await relaunch();
    } catch (error) {
      setUpdateStatus(`Update check failed: ${String(error)}`);
      if (manual) {
        await message(`Gagal memeriksa update: ${String(error)}`, { title: "Update Check Failed", kind: "error" });
      }
    }
  }

  useEffect(() => {
    void checkForUpdates(false);
    getVersion().then(setAppVersion).catch(() => undefined);
  }, []);

  async function selectExcelTarget() {
    const picked = await save({
      defaultPath: settings.excelPath || "Data_PO.xlsx",
      filters: [{ name: "Excel Workbook", extensions: ["xlsx"] }],
    });
    if (typeof picked === "string") {
      await invoke("ensure_excel", { excelPath: picked });
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

        {activeView === "po" && (
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
                Auto Update Status
                <input value={updateStatus} readOnly />
              </label>
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
              <button className="secondary-button" type="button" onClick={() => updateSettings({ themeMode: settings.themeMode === "dark" ? "light" : "dark" })}>
                {settings.themeMode === "dark" ? <Sun size={16} /> : <Moon size={16} />}
                Switch to {settings.themeMode === "dark" ? "Light" : "Dark"} Theme
              </button>
              <button className="secondary-button" type="button" onClick={() => void checkForUpdates(true)}>
                <RefreshCw size={16} />
                Check for Updates
              </button>
            </div>
          </section>
        )}
      </section>
    </main>
  );
}



