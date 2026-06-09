import { defaultExtractionFields, type ExtractionFieldKey } from "./extractionFields";
import { defaultMergerTemplates, type ExcelMergerTemplate } from "./mergerFields";

export type ThemeMode = "dark" | "light";

export type AppSettings = {
  excelPath: string;
  processedOutputFolder: string;
  sourceArchiveFolder: string;
  themeMode: ThemeMode;
  selectedExtractionFields: ExtractionFieldKey[];
  batchConcurrency: number;
  excelMergerTemplates: ExcelMergerTemplate[];
};

export const defaultAppSettings: AppSettings = {
  excelPath: "",
  processedOutputFolder: "",
  sourceArchiveFolder: "",
  themeMode: "dark",
  selectedExtractionFields: defaultExtractionFields,
  batchConcurrency: 2,
  excelMergerTemplates: defaultMergerTemplates,
};

export function normalizeAppSettings(value: unknown): AppSettings {
  if (!value || typeof value !== "object") {
    return defaultAppSettings;
  }
  const raw = value as Partial<AppSettings>;
  const selectedExtractionFields = Array.isArray(raw.selectedExtractionFields) && raw.selectedExtractionFields.length
    ? raw.selectedExtractionFields
    : defaultExtractionFields;
  const batchConcurrency = Number(raw.batchConcurrency);
  return {
    ...defaultAppSettings,
    ...raw,
    themeMode: raw.themeMode === "light" ? "light" : "dark",
    selectedExtractionFields,
    batchConcurrency: Number.isFinite(batchConcurrency) ? Math.max(1, Math.min(4, Math.round(batchConcurrency))) : 2,
    excelMergerTemplates: Array.isArray(raw.excelMergerTemplates) && raw.excelMergerTemplates.length
      ? raw.excelMergerTemplates
      : defaultMergerTemplates,
  };
}
