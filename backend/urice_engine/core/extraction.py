"""
Core PDF Extraction Engine - Full conversion from prototype.

This contains the complete, battle-tested logic from the original main.py
for extracting data from scanned Indonesian PO PDFs using Tesseract OCR.

Changes for Full Client:
- Standalone functions + Extractor class (no UI dependency)
- Returns typed POExtractionResult when possible
- Better Tesseract path handling for proper installers
- Legacy dict output supported for transition
"""

import fitz
import re
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Callable
from collections import defaultdict

try:
    import pytesseract
    from PIL import Image, ImageEnhance
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

from ..models.po_data import POExtractionResult, POItem


CONTACT_NUMBER_CONTEXT = re.compile(r'\b(?:TELP|TELEPON|PHONE|FAX|HP|HANDPHONE|MOBILE|CONTACT|KONTAK|PIC)\b', re.IGNORECASE)


def _has_po_number_label(line: str) -> bool:
    label = re.sub(r'[^A-Z]', '', line.upper().replace("0", "O"))
    return any(token in label for token in ("NOOP", "OPNO", "PONO", "PONUMBER", "PURCHASEORDERNO"))


def _numbers_from_line(line: str) -> list[str]:
    return re.findall(r'\b\d{7,14}\b', line)


def _number_after_po_label(line: str) -> str:
    patterns = [
        r'No\.?\s*OP\s*[:>\-\.]?\s*(\d{7,14})',
        r'OP\s*No\.?\s*[:>\-\.]?\s*(\d{7,14})',
        r'PO\s*No\.?\s*[:>\-\.]?\s*(\d{7,14})',
        r'P\s*[O0]\s*N\s*[O0]\.?\s*[:>\-\.]?\s*(\d{7,14})',
        r'PO\s*Number\s*[:>\-\.]?\s*(\d{7,14})',
        r'Purchase\s*Order\s*No\.?\s*[:>\-\.]?\s*(\d{7,14})',
    ]
    for pattern in patterns:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _extract_document_number(lines: list[str], full_text: str, filename: str) -> str:
    unique_lines = list(dict.fromkeys([line.strip() for line in lines if line.strip()]))

    for line in unique_lines:
        if _has_po_number_label(line):
            labeled_number = _number_after_po_label(line)
            if labeled_number:
                return labeled_number
            for number in _numbers_from_line(line):
                return number

    labeled_number = _number_after_po_label(full_text)
    if labeled_number:
        return labeled_number

    safe_generic_patterns = [
        r'\b(09\d{10})\b',
        r'\b(1871\d{6,})\b',
        r'\b(18\d{8,10})\b',
        r'\b(0\d{11})\b',
    ]
    for pattern in safe_generic_patterns:
        for match in re.finditer(pattern, full_text, re.IGNORECASE):
            context = full_text[max(0, match.start() - 50): match.end() + 50]
            if not CONTACT_NUMBER_CONTEXT.search(context):
                return match.group(1)

    filename_match = re.search(r'(\d{9,12})', filename or "")
    return filename_match.group(1) if filename_match else ""


def _clean_vendor_name(value: str) -> str:
    cleaned = value.strip(" |:;-'\"")
    cleaned = re.sub(r'\s*[\(\[].*$', '', cleaned).strip().strip(',').strip()
    return ' '.join(cleaned.split())


def _normalize_legal_vendor_name(value: str) -> str:
    cleaned = _clean_vendor_name(value)
    match = re.match(r'^PT\.?\s+(.+)$', cleaned, re.IGNORECASE)
    if match:
        return f"{match.group(1).strip().upper()}, PT."
    return cleaned


def get_tesseract_paths() -> dict:
    """Returns possible Tesseract locations (development + installed + bundled)."""
    paths = {}

    # Bundled via PyInstaller
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        paths["bundled"] = str(Path(base) / "tesseract_portable" / "tesseract.exe")

    # Local development bundle (from root of full-client or project)
    dev_root = Path(__file__).parents[4]  # go up to full-client or project root
    paths["dev"] = str(dev_root / "tesseract_portable" / "tesseract.exe")

    # System installs
    paths["system"] = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    return paths


def configure_tesseract() -> bool:
    """Configure pytesseract to the best available Tesseract installation."""
    if not OCR_AVAILABLE:
        return False

    tess_paths = get_tesseract_paths()

    # Try bundled first
    for key in ["bundled", "dev"]:
        p = tess_paths.get(key)
        if p and Path(p).exists():
            pytesseract.pytesseract.tesseract_cmd = p
            tessdata = Path(p).parent / "tessdata"
            if tessdata.exists():
                os.environ["TESSDATA_PREFIX"] = str(tessdata)
            return True

    # System fallback
    for p in tess_paths.get("system", []):
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return True

    return False


class POExtractor:
    """
    Main extraction engine. Converted from the monolithic method in prototype.
    Can be used independently of the UI (good for testing and future features).
    """

    def __init__(self, settings: Optional[dict] = None, log_callback: Optional[Callable[[str, str], None]] = None):
        self.settings = settings or {}
        self.log = log_callback or (lambda msg, level="INFO": print(f"[{level}] {msg}"))

    def _get_ocr_text(self, page: fitz.Page) -> str:
        """Render page and run OCR (portable-aware)."""
        if not OCR_AVAILABLE:
            self.log("OCR library not available.", "ERROR")
            return ""

        if not configure_tesseract():
            self.log("Tesseract not found. OCR will fail.", "ERROR")
            return ""

        try:
            mat = fitz.Matrix(3, 3)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            try:
                img = ImageEnhance.Contrast(img).enhance(1.7).convert('L')
            except Exception:
                pass

            text = pytesseract.image_to_string(img, lang="ind+eng", config="--psm 6 --oem 3")
            return text
        except Exception as e:
            self.log(f"OCR failed: {str(e)[:150]}", "WARNING")
            return ""

    def extract(self, page: fitz.Page, original_filename: str) -> POExtractionResult:
        """
        Full extraction (complete port of the prototype logic).
        Returns typed model.
        """
        result = POExtractionResult(original_filename=original_filename)

        # Text layer first
        text = page.get_text("text") or ""
        used_ocr = False

        if len(text.strip()) < 30:
            self.log("No text layer â†’ using OCR + table position filter...", "WARNING")
            text = self._get_ocr_text(page)
            used_ocr = True

        if not text.strip():
            self.log("Failed to get any text from PDF.", "ERROR")
            return result

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        source_lines = list(lines)
        full_text = " ".join(lines)
        original_full_text = full_text

        # === POSITION FILTER (from prototype) ===
        table_lines = []
        if used_ocr and OCR_AVAILABLE:
            try:
                if not configure_tesseract():
                    raise RuntimeError("Tesseract not configured")

                mat = fitz.Matrix(3, 3)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                try:
                    img = ImageEnhance.Contrast(img).enhance(1.7).convert('L')
                except:
                    img = img.convert('L')

                ocr_data = pytesseract.image_to_data(img, lang="ind+eng", output_type=pytesseract.Output.DICT)

                line_groups = defaultdict(list)
                for i, txt in enumerate(ocr_data['text']):
                    if txt.strip() and int(ocr_data['conf'][i]) > 20:
                        top = ocr_data['top'][i]
                        bucket = (top // 20) * 20
                        line_groups[bucket].append((ocr_data['left'][i], txt))

                for bucket in sorted(line_groups.keys()):
                    if 200 < bucket < 2000:
                        words = sorted(line_groups[bucket], key=lambda x: x[0])
                        line_text = ' '.join(w[1] for w in words)
                        table_lines.append(line_text.strip())

                if table_lines:
                    lines = table_lines
                    full_text = " ".join(lines)
                    self.log("Using table-area text only (position filter).")
            except Exception as e:
                self.log(f"Position filter failed, using full text: {str(e)[:80]}", "WARNING")

        # NO. OP / PO No.
        result.no_op = _extract_document_number(source_lines + lines, original_full_text, original_filename)


        # VENDOR
        bad_vendor_kw = ["SINAR TERNAK", "CHAROEN", "DELIVERY", "BILLING", "PHONE", "TELP", "FAX", "CONTACT", "BANK", "ATTENTION", "PIC ", "NPWP", "NITKU", "ORG.", "PLANT", "GROUP PEMBELIAN", "MATA UANG", "ALAMAT", "INFORMASI", "SALES PERSON", "SHIPPING", "PO DATE", "ESTIMATE DATE", "PAYMENT TERM", "CURRENCY", "TOLERANCE", "INCOTERM", "PLUIT", "PLOEIT", "JL.", "JALAN", "OFFICE BUILDING", "LANTAI", "JAKARTA", "KEL.", "KEC.", "RAYA BLOK"]
        candidates = []
        supplier_lines = list(dict.fromkeys([l.strip() for l in source_lines + lines if l.strip()]))

        for idx, line in enumerate(supplier_lines):
            next_line = supplier_lines[idx + 1] if idx + 1 < len(supplier_lines) else ""
            m = re.search(r'(.+?)\s*[-â€“]\s*\|?\s*PO\s*Date\b', line, re.IGNORECASE)
            if m:
                name_part = _clean_vendor_name(m.group(1))
                if len(name_part) >= 4 and not any(b in name_part.upper() for b in bad_vendor_kw):
                    candidates.append((name_part, "", 45))

            m = re.search(r'(.+?)\s*[-â€“]\s*(?:No\.?\s*OP|PO\s*Date)\b', line, re.IGNORECASE)
            if m:
                name_part = _clean_vendor_name(m.group(1))
                code_match = re.search(r'\b(0{2,}\d{5,10}|\d{6,10})\b', next_line)
                code_part = code_match.group(1) if code_match else ""
                if name_part and code_part:
                    candidates.append((name_part, code_part, 35))

            m = re.search(r'(ONE\s*TIME\s*VENDOR)\s*[-â€“]\s*(\d{5,10})', line, re.IGNORECASE)
            if m:
                candidates.append(("ONE TIME VENDOR", m.group(2), 40))

            m = re.search(r'Transfer\s*info\s*[-—:]?\s*(PT\.?\s+[A-Za-z0-9\.\,\s\(\)\-]+?)(?:\s+Payment|\s+Incoterm|\s+Bank|$)', line, re.IGNORECASE)
            if m:
                candidates.append((_normalize_legal_vendor_name(m.group(1)), "", 44))

        for line in supplier_lines:
            for m in re.finditer(r'([A-Z][A-Za-z0-9\.\,\s\(\)\-]+?)\s*[-â€“]\s*(\d{5,10})(?:\s|$|[^0-9])', line):
                name_part = m.group(1).strip().strip('-â€“').strip()
                code_part = m.group(2).strip()
                name_part = _clean_vendor_name(name_part)
                nu = name_part.upper()
                if len(name_part) >= 4 and not any(b in nu for b in bad_vendor_kw) and not name_part.replace(' ', '').replace('-', '').isdigit():
                    if len(name_part) >= 4:
                        candidates.append((name_part, code_part, 12))

        if candidates:
            def vendor_score(candidate):
                name, code, priority = candidate
                upper = name.upper()
                trusted = 8 if any(k in upper for k in ["SOLUSINDO", "TOKO", "PT.", "CV.", "TBK", "VENDOR"]) else 0
                noisy = -30 if any(k in upper for k in bad_vendor_kw) else 0
                has_code = 6 if code else 0
                return priority + trusted + has_code + noisy

            candidates.sort(key=lambda c: (-vendor_score(c), -len(c[0])))
            best = candidates[0]
            result.vendor_name = best[0]
            result.vendor_code = best[1]
        else:
            m = re.search(r'(ONE\s*TIME\s*VENDOR)\s*[-â€“]?\s*(\d{5,10})', original_full_text, re.IGNORECASE)
            if m:
                result.vendor_name = "ONE TIME VENDOR"
                result.vendor_code = m.group(2)

        # SONIC rescue
        if result.vendor_name.startswith("ONE TIME") or len(result.vendor_name) < 6 or "ARMADI" in result.vendor_name.upper():
            m = re.search(r'(SONIC\s+SOLUSINDO[^-]*?)\s*[-â€“]\s*(\d{5,10})', original_full_text, re.IGNORECASE)
            if m:
                result.vendor_name = m.group(1).strip()
                result.vendor_code = m.group(2)

        # Clean vendor name
        vn = result.vendor_name
        if re.search(r'\s*[-â€“]\s*\d{5,10}$', vn):
            vn = re.sub(r'\s*[-â€“]\s*\d{5,10}$', '', vn).strip()
        result.vendor_name = ' '.join(vn.split()) if vn else "ONE TIME VENDOR"

        # MULTI-ITEM PARSING (core of the prototype's power)
        item_rows_raw = []
        seen = set()
        cands = list(dict.fromkeys((table_lines if 'table_lines' in locals() else []) + lines + [l.strip() for l in original_full_text.split('\n') if l.strip()]))

        for line in cands:
            mat = re.search(r'(\d{2,6}\.\d{2}\.\d{3,5})', line)
            if not mat:
                continue
            item = mat.group(1)
            if re.match(r'^\d{1,2}\.\d{1,2}\.\d{2,4}$', item) or item in seen:
                continue

            after = line[mat.end():]
            desc = ""
            cut = re.search(r'\s{1,}\d[\d\.,]*\s*(?:UNT|PC|PCS|UNIT|EA)\b', after, re.IGNORECASE)
            if not cut:
                cut = re.search(r'\s{1,}[\d\.,]{2,}', after)
            if cut:
                desc = after[:cut.start()]
            else:
                for p in re.split(r'\s{2,}', after):
                    if sum(c.isalpha() for c in p) >= 3 and len(p) > 4:
                        desc = p
                        break
            desc = re.sub(r'^[\s\-â€“|:\d\.\,\(\)]+', '', desc).strip()
            desc = re.sub(r'\s+', ' ', desc)[:90]

            has_unit = bool(re.search(r'(?i)\b(UNT|PC|PCS|UNIT)\b', line))
            num_count = len(re.findall(r'[\d\.,]{2,}', line[mat.end():]))
            alpha_count = sum(c.isalpha() for c in desc)
            if alpha_count < 3 and not has_unit and num_count < 2:
                continue

            seen.add(item)

            # Number parsing (robust)
            qty = unit = harga = total = ""
            mnum = re.search(r'([\d\.,]+)\s*(UNT|PC|PCS|UNIT|EA)?\s*([\d\.,]+)\s+([\d\.,]+)', line, re.IGNORECASE)
            if mnum:
                qty, unit, harga, total = mnum.group(1), (mnum.group(2) or "").strip().title(), mnum.group(3), mnum.group(4)
            if not (qty and harga and total):
                nums = [n for n in re.findall(r'[\d\.,]{2,}', line[mat.end():]) if len(n.replace(',','').replace('.','')) >= 2]
                if len(nums) >= 3 and not qty:
                    qty, harga, total = nums[0], nums[1], nums[2]
            if not unit:
                unit = "Unit" if re.search(r'(?i)\b(UNT|UNIT)\b', line) else ("Pc" if re.search(r'(?i)PC', line) else "Pc")
            unit = unit.title()
            if unit in ("Unt", "Unit", "Ea"):
                unit = "Unit"

            item_rows_raw.append({
                "item": item,
                "nama_barang": desc or item,
                "quantity": qty,
                "satuan": unit or "Pc",
                "harga_satuan": harga,
                "total": total,
            })

        # Post-rescue + fallback (simplified but functional version of prototype logic)
        if not item_rows_raw:
            mat = re.search(r'(\d{2,6}\.\d{2}\.\d{3,5})', original_full_text)
            if mat and not re.match(r'^\d{1,2}\.\d{1,2}\.\d{2,4}$', mat.group(1)):
                item_rows_raw = [{"item": mat.group(1), "nama_barang": mat.group(1), "quantity": "", "satuan": "Pc", "harga_satuan": "", "total": ""}]

        # Grand total
        gm = re.search(r'(?:Total\s*Keseluruhan|Grand\s*Total|TOTAL\s*BEFORE\s*TAX|Total\s*Sesudah)\s*[: ]*([\d\.\,]+)', original_full_text, re.IGNORECASE)
        grand = gm.group(1) if gm else ""
        if grand:
            grand = re.sub(r'[^\d\.,]', '', grand)

        # Build final typed result
        for raw in item_rows_raw:
            for k in ["quantity", "harga_satuan", "total"]:
                if raw.get(k):
                    raw[k] = re.sub(r'[^\d\.,]', '', raw[k])
            item = POItem(
                item_code=raw.get("item", ""),
                nama_barang=raw.get("nama_barang", ""),
                quantity=raw.get("quantity", ""),
                satuan=raw.get("satuan", "Pc"),
                harga_satuan=raw.get("harga_satuan", ""),
                total=raw.get("total", "")
            )
            result.items.append(item)

        if grand:
            result.grand_total = grand

        # Auto correction (if enabled in settings)
        if self.settings.get("auto_correction"):
            for it in result.items:
                if it.quantity in ("0,00", "0.00") and any(x in it.nama_barang.upper() for x in ["10", "SEPULUH"]):
                    it.quantity = "10,00"

        return result

    # Legacy support - returns list of dicts exactly like the old prototype
    def extract_legacy(self, page: fitz.Page, original_filename: str) -> List[Dict]:
        res = self.extract(page, original_filename)
        return res.to_excel_rows()


# Convenience function
def extract_from_page(page: fitz.Page, original_filename: str, settings: Optional[dict] = None) -> List[Dict]:
    extractor = POExtractor(settings=settings)
    return extractor.extract_legacy(page, original_filename)
