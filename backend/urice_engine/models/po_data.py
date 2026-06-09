"""
Data models for PO extraction results.

This replaces the loose dicts used in the prototype.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class POItem:
    """Single line item extracted from a PO."""
    item_code: str = ""
    nama_barang: str = ""
    quantity: str = ""
    satuan: str = "Pc"
    harga_satuan: str = ""
    total: str = ""


@dataclass
class POExtractionResult:
    """Result of processing one PDF (can contain multiple items)."""
    no_op: str = ""
    vendor_name: str = "ONE TIME VENDOR"
    vendor_code: str = "0007000940"
    tanggal_proses: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    grand_total: str = ""
    items: list[POItem] = field(default_factory=list)
    original_filename: str = ""
    processed_pdf_path: str = ""
    processed_filename: str = ""

    def to_excel_rows(self) -> list[dict]:
        """Convert to rows suitable for Excel (one row per item)."""
        if not self.items:
            # Fallback single row (like prototype behavior)
            return [{
                "tanggal_proses": self.tanggal_proses,
                "no_op": self.no_op,
                "vendor_name": self.vendor_name,
                "vendor_code": self.vendor_code,
                "item": "",
                "nama_barang": "",
                "quantity": "",
                "satuan": "Pc",
                "harga_satuan": "",
                "total": "",
                "grand_total": self.grand_total,
            }]

        rows = []
        for item in self.items:
            rows.append({
                "tanggal_proses": self.tanggal_proses,
                "no_op": self.no_op,
                "vendor_name": self.vendor_name,
                "vendor_code": self.vendor_code,
                "item": item.item_code,
                "nama_barang": item.nama_barang,
                "quantity": item.quantity,
                "satuan": item.satuan,
                "harga_satuan": item.harga_satuan,
                "total": item.total,
                "grand_total": self.grand_total,
            })
        return rows
