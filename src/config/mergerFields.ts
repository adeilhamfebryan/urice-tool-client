export const mergerStandardColumns = [
  "Source",
  "Nomor PO",
  "Nomor PR",
  "Nomor GR",
  "Vendor Code",
  "Vendor Name",
  "Material Code",
  "Nama Barang",
  "Qty",
  "Satuan",
  "Harga Satuan",
  "Total",
  "Tanggal",
  "Plant",
  "Status",
  "Keterangan",
] as const;

export type MergerStandardColumn = typeof mergerStandardColumns[number];

export type ExcelMergerTemplate = {
  id: string;
  name: string;
  mapping: Record<string, MergerStandardColumn>;
};

export const defaultMergerTemplates: ExcelMergerTemplate[] = [
  { id: "sap", name: "SAP", mapping: {} },
  { id: "pb", name: "PB", mapping: {} },
  { id: "pi", name: "PI", mapping: {} },
  { id: "com", name: "COM", mapping: {} },
];
