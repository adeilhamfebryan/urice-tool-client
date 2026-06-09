"""Command-line entrypoint for the URice Tools Client Python sidecar."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import fitz
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from urice_engine import __version__
from urice_engine.core.extraction import POExtractor, configure_tesseract

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

EXCEL_HEADERS = [
    "Tanggal Diproses",
    "Company Name",
    "Nomor OP",
    "Nama Vendor",
    "Nomor Vendor",
    "Keterangan",
    "Status",
]

TEXT_COLUMNS = {
    "Nomor OP",
    "Nomor Vendor",
}


def _excel_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text.startswith("'") else f"'{text}"


def health() -> dict:
    return {
        "ok": True,
        "engine": "urice-python-sidecar",
        "version": __version__,
        "tesseract_configured": configure_tesseract(),
    }


def _extract_page_payload(path: Path) -> tuple[list[dict], str]:
    doc = fitz.open(str(path))
    try:
        if len(doc) == 0:
            return [], ""
        page = doc[0]
        extractor = POExtractor(log_callback=lambda _message, _level="INFO": None)
        with contextlib.redirect_stdout(io.StringIO()):
            rows = extractor.extract_legacy(page, path.name)
            text = page.get_text("text") or ""
            if len(text.strip()) < 30:
                text = extractor._get_ocr_text(page)
        return rows, _extract_company_name(text)
    finally:
        doc.close()


def _extract_rows(path: Path) -> list[dict]:
    rows, _company = _extract_page_payload(path)
    return rows


def _extract_company_name(text: str) -> str:
    lines = [" ".join(line.strip().split()) for line in text.splitlines() if line.strip()]
    joined = " ".join(lines)
    known_patterns = [
        r"(PT\.?\s+CHAROEN\s+POKPHAND\s+INDONESIA(?:\s+Tbk\.?)?)",
        r"(CHAROEN\s+POKPHAND\s+INDONESIA(?:\s+Tbk\.?)?)",
        r"(PT\.?\s+SINAR\s+TERNAK\s+SEJAHTERA(?:\s*-\s*LAMPUNG)?)",
        r"(SINAR\s+TERNAK\s+SEJAHTERA(?:\s*-\s*LAMPUNG)?)",
        r"(CPI\s+[^\n,]{3,60})",
    ]
    for pattern in known_patterns:
        match = re.search(pattern, joined, re.IGNORECASE)
        if match:
            return " ".join(match.group(1).strip(" -:,").split())[:80]

    for line in lines[:30]:
        upper = line.upper()
        if any(token in upper for token in ["CHAROEN", "SINAR TERNAK", "POKPHAND", "CPI"]):
            if not any(skip in upper for skip in ["VENDOR", "PHONE", "FAX", "EMAIL", "BANK"]):
                return line[:80]
    return ""


def _clean_filename_part(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\s\.\-]", "", value or fallback).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:60].strip("_") or fallback


def _save_first_page(source_pdf: Path, output_folder: Path, vendor_name: str, no_op: str) -> tuple[str, str]:
    output_folder.mkdir(parents=True, exist_ok=True)
    filename = f"{_clean_filename_part(vendor_name, 'VENDOR')}-{_clean_filename_part(no_op, datetime.now().strftime('%Y%m%d%H%M%S'))}.pdf"
    output_path = output_folder / filename

    doc = fitz.open(str(source_pdf))
    try:
        if len(doc) == 0:
            raise ValueError("PDF has no pages")
        new_doc = fitz.open()
        try:
            new_doc.insert_pdf(doc, from_page=0, to_page=0)
            new_doc.save(str(output_path), garbage=4, deflate=True)
        finally:
            new_doc.close()
    finally:
        doc.close()

    return str(output_path), filename


def extract_pdf(pdf_path: str) -> dict:
    path = Path(pdf_path).resolve()
    if not path.exists():
        raise FileNotFoundError(str(path))

    rows, company_name = _extract_page_payload(path)
    return {"ok": True, "source": str(path), "company_name": company_name, "rows": rows}


def process_pdf(pdf_path: str, output_folder: str, source_archive_folder: str = "") -> dict:
    path = Path(pdf_path).resolve()
    if not path.exists():
        raise FileNotFoundError(str(path))

    rows, company_name = _extract_page_payload(path)
    if not rows:
        return {"ok": False, "error": "No extraction rows were produced.", "source": str(path), "rows": []}

    first = rows[0]
    processed_path, processed_filename = _save_first_page(
        path,
        Path(output_folder).expanduser().resolve(),
        first.get("vendor_name", "VENDOR"),
        first.get("no_op", ""),
    )

    return {
        "ok": True,
        "source": str(path),
        "processed_pdf_path": processed_path,
        "processed_pdf_filename": processed_filename,
        "archived_source_path": "",
        "company_name": company_name,
        "rows": rows,
    }


def ensure_excel_file(excel_path: str) -> Path:
    path = Path(excel_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        return path

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data PO"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="630D16", end_color="630D16", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin", color="B4B4B4"),
        right=Side(style="thin", color="B4B4B4"),
        top=Side(style="thin", color="B4B4B4"),
        bottom=Side(style="thin", color="B4B4B4"),
    )

    for col, header in enumerate(EXCEL_HEADERS, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
        if header in TEXT_COLUMNS:
            ws.column_dimensions[get_column_letter(col)].number_format = "@"

    widths = [20, 26, 18, 34, 18, 40, 18]
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A2"
    wb.save(path)
    wb.close()
    return path


def append_record(excel_path: str, record_json: str) -> dict:
    path = ensure_excel_file(excel_path)
    record = json.loads(record_json)

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    if ws.max_row == 0:
        ws.append(EXCEL_HEADERS)

    values = [
        record.get("tanggal_diproses", ""),
        record.get("company_name", ""),
        _excel_text(record.get("nomor_op", "")),
        record.get("nama_vendor", ""),
        _excel_text(record.get("nomor_vendor", "")),
        record.get("keterangan", ""),
        record.get("status", ""),
    ]
    ws.append(values)
    last_row = ws.max_row

    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )
    for col in range(1, len(EXCEL_HEADERS) + 1):
        cell = ws.cell(row=last_row, column=col)
        cell.border = thin_border
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        if EXCEL_HEADERS[col - 1] in TEXT_COLUMNS:
            cell.number_format = "@"

    wb.save(path)
    wb.close()
    return {"ok": True, "excel_path": str(path), "row": last_row}


def append_record_file(excel_path: str, record_file: str) -> dict:
    payload = Path(record_file).read_text(encoding="utf-8-sig")
    return append_record(excel_path, payload)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="URice Tools Client sidecar")
    parser.add_argument("--health", action="store_true", help="Print backend health as JSON")
    parser.add_argument("--extract", metavar="PDF", help="Extract PO data from a PDF and print JSON")
    parser.add_argument("--process", nargs=3, metavar=("PDF", "OUTPUT_FOLDER", "SOURCE_ARCHIVE"), help="Extract PDF and save the first page. Source archive move is handled after Excel apply.")
    parser.add_argument("--ensure-excel", metavar="XLSX", help="Create target Excel if it does not exist")
    parser.add_argument("--append-record", nargs=2, metavar=("XLSX", "JSON"), help="Append one corrected PO record to Excel")
    parser.add_argument("--append-record-file", nargs=2, metavar=("XLSX", "JSON_FILE"), help="Append one corrected PO record from a JSON file")
    args = parser.parse_args(argv)

    try:
        if args.health:
            payload = health()
        elif args.extract:
            payload = extract_pdf(args.extract)
        elif args.process:
            payload = process_pdf(args.process[0], args.process[1], args.process[2])
        elif args.ensure_excel:
            path = ensure_excel_file(args.ensure_excel)
            payload = {"ok": True, "excel_path": str(path)}
        elif args.append_record:
            payload = append_record(args.append_record[0], args.append_record[1])
        elif args.append_record_file:
            payload = append_record_file(args.append_record_file[0], args.append_record_file[1])
        else:
            payload = {"ok": False, "error": "No command provided"}
            print(json.dumps(payload), file=sys.stderr)
            return 2

        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
