export type ExtractionFieldKey =
  | "tanggal_diproses"
  | "company_name"
  | "nama_vendor"
  | "nomor_vendor"
  | "nomor_op"
  | "nomor_item"
  | "nama_barang"
  | "quantity"
  | "satuan"
  | "harga_satuan"
  | "total"
  | "processed_pdf"
  | "keterangan"
  | "status";

export const extractionFieldOptions: Array<{ key: ExtractionFieldKey; label: string; hint: string }> = [
  { key: "tanggal_diproses", label: "Tanggal Diproses", hint: "Waktu proses aplikasi" },
  { key: "company_name", label: "Company Name", hint: "Biasanya pojok kiri atas lembar pertama" },
  { key: "nama_vendor", label: "Nama Vendor", hint: "Area Alamat Suplier" },
  { key: "nomor_vendor", label: "No. Vendor", hint: "Kode vendor, dijaga sebagai teks Excel" },
  { key: "nomor_op", label: "No. OP", hint: "Field Informasi, dijaga sebagai teks Excel" },
  { key: "nomor_item", label: "Nomor Item", hint: "Nomor baris item PO" },
  { key: "nama_barang", label: "Nama Barang", hint: "Deskripsi barang dari tabel PO" },
  { key: "quantity", label: "Banyaknya / QTY", hint: "Jumlah barang" },
  { key: "satuan", label: "Satuan", hint: "Unit barang" },
  { key: "harga_satuan", label: "Harga Satuan", hint: "Harga per unit" },
  { key: "total", label: "Total", hint: "Nilai total baris item" },
  { key: "processed_pdf", label: "Processed PDF Link", hint: "Link file PDF lembar pertama untuk Excel" },
  { key: "keterangan", label: "Keterangan", hint: "Diisi manual oleh user" },
  { key: "status", label: "Status", hint: "Diisi manual oleh user" },
];

export const defaultExtractionFields: ExtractionFieldKey[] = [
  "tanggal_diproses",
  "company_name",
  "nomor_op",
  "nama_vendor",
  "nomor_vendor",
  "processed_pdf",
  "keterangan",
  "status",
];
