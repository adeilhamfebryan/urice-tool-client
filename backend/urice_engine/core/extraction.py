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
    from PIL import Image, ImageEnhance, ImageFilter
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


def _normalize_vendor_suffix(value: str) -> str:
    return re.sub(
        r',\s*(PT|CV|PD|UD)\.?$',
        lambda match: f", {match.group(1).upper()}.",
        value.strip(),
        flags=re.IGNORECASE,
    )
def _normalize_legal_vendor_name(value: str) -> str:
    cleaned = _clean_vendor_name(value)
    match = re.match(r'^PT\.?\s+(.+)$', cleaned, re.IGNORECASE)
    if match:
        return f"{match.group(1).strip().upper()}, PT."
    return cleaned



SUPPLIER_ANCHOR_PATTERN = re.compile(r'\b(?:ALAMAT\s+SUPP?LIER|SUPP?LIER)\b', re.IGNORECASE)
SUPPLIER_STOP_PATTERN = re.compile(
    r'\b(?:INFORMATION|INFORMASI|PO\s*DATE|PO\s*NO|NO\.?\s*OP|ESTIMATE|CONTACT|PHONE|FAX|HANDPHONE|TRANSFER\s*INFO|'
    r'DELIVERY\s+ADDRESS|ALAMAT\s+KIRIM|BILLING\s+ADDRESS|ALAMAT\s+PENAGIHAN|PLANT|CURRENCY|PAYMENT\s+TERM)\b',
    re.IGNORECASE,
)
ADDRESS_NOISE_PATTERN = re.compile(
    r'\b(?:JL\.?|JALAN|KEL\.?|KEC\.?|KAB\.?|KOTA|RT/?RW|RAYA|BLOK|LANTAI|OFFICE\s+BUILDING|JAKARTA|PLUIT|PLOEIT|CONTACT|PHONE|FAX|BANK)\b',
    re.IGNORECASE,
)
LEGAL_VENDOR_TOKEN_PATTERN = re.compile(r'\b(?:PT\.?|CV\.?|PD\.?|UD\.?|TOKO|VENDOR)\b', re.IGNORECASE)
PO_HEADER_PATTERN = re.compile(r'\b(?:PURCHASE\s+ORDER|INFORMATION|INFORMASI)\b', re.IGNORECASE)



def _is_supplier_anchor(line: str) -> bool:
    upper = line.upper()
    if "CONFIRMED" in upper or "CONFIRM" in upper:
        return False
    if re.search(r'\bALAMAT\s+SUPP?LIER\b', upper):
        return True
    if re.search(r'\bSUPP?LIER\b', upper):
        return True
    compact = re.sub(r'[^A-Z]', '', upper)
    return "SUPE" in compact and ("INFORMATION" in compact or "INFORMASI" in compact)

def _line_after_supplier_anchor(line: str) -> str:
    match = SUPPLIER_ANCHOR_PATTERN.search(line)
    if not match:
        return ""
    return line[match.end():].strip(" |:;-")


def _strip_vendor_noise(value: str) -> str:
    text = re.split(
        r'\b(?:PO\s*DATE|PO\s*NO|NO\.?\s*OP|ESTIMATE|CONTACT|PHONE|FAX|HANDPHONE|TRANSFER\s*INFO|PAYMENT\s*TERM)\b',
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    text = re.sub(r'\s*[-–]\s*\d{5,10}\b.*$', '', text).strip()
    text = _clean_vendor_name(text)
    legal_match = re.search(r'^(.+?,\s*(?:PT\.?|CV\.?|PD\.?|UD\.?|TOKO))\b', text, re.IGNORECASE)
    if legal_match:
        text = legal_match.group(1).strip()
    return _normalize_vendor_suffix(text.strip(" -:,"))


def _has_suspicious_short_vendor_tokens(name: str) -> bool:
    allowed = {"PT", "CV", "PD", "UD"}
    tokens = [re.sub(r'[^A-Za-z]', '', token).upper() for token in name.split()]
    tokens = [token for token in tokens if token]
    return any(len(token) <= 2 and token not in allowed for token in tokens)


def _parse_supplier_vendor_line(line: str) -> tuple[str, str]:
    if not line.strip() or SUPPLIER_STOP_PATTERN.match(line.strip()):
        return "", ""
    if ADDRESS_NOISE_PATTERN.search(line):
        return "", ""

    code_scope = re.split(
        r'\b(?:PO\s*DATE|PO\s*NO|NO\.?\s*OP|ESTIMATE|CONTACT|PHONE|FAX|HANDPHONE|TRANSFER\s*INFO|PAYMENT\s*TERM)\b',
        line,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    code_matches = re.findall(r'\b(0{2,}\d{5,10}|\d{5,10})\b', code_scope)
    vendor_code = code_matches[-1] if code_matches else ""
    candidate = code_scope
    if vendor_code:
        candidate = code_scope[:code_scope.rfind(vendor_code)]
    vendor_name = _strip_vendor_noise(candidate)
    if not vendor_name or len(vendor_name) < 4:
        return "", ""
    if _has_suspicious_short_vendor_tokens(vendor_name):
        return "", ""
    if not vendor_code and not LEGAL_VENDOR_TOKEN_PATTERN.search(vendor_name):
        return "", ""
    if re.fullmatch(r'[\d\s\.\-]+', vendor_name):
        return "", ""
    return vendor_name, vendor_code


def _extract_supplier_region_vendor(lines: list[str]) -> tuple[str, str]:
    for line in [line.strip() for line in lines[:8] if line.strip()]:
        if SUPPLIER_STOP_PATTERN.match(line):
            break
        vendor_name, vendor_code = _parse_supplier_vendor_line(line)
        if vendor_name:
            return vendor_name, vendor_code
    return "", ""
def _extract_supplier_block_vendor(lines: list[str]) -> tuple[str, str]:
    unique_lines = list(dict.fromkeys([line.strip() for line in lines if line.strip()]))
    for index, line in enumerate(unique_lines):
        if not _is_supplier_anchor(line):
            continue

        candidates = []
        same_line_tail = _line_after_supplier_anchor(line)
        if same_line_tail and not re.fullmatch(r'(?:INFORMATION|INFORMASI)', same_line_tail, re.IGNORECASE):
            candidates.append(same_line_tail)

        for next_line in unique_lines[index + 1:index + 6]:
            if SUPPLIER_STOP_PATTERN.match(next_line.strip()):
                break
            candidates.append(next_line)

        for candidate in candidates:
            vendor_name, vendor_code = _parse_supplier_vendor_line(candidate)
            if vendor_name:
                return vendor_name, vendor_code

    header_index = -1
    for index, line in enumerate(unique_lines[:25]):
        if PO_HEADER_PATTERN.search(line):
            header_index = index
            if "PURCHASE" in line.upper():
                continue
            break

    if header_index >= 0:
        for candidate in unique_lines[header_index + 1:header_index + 8]:
            if SUPPLIER_STOP_PATTERN.match(candidate.strip()):
                break
            vendor_name, vendor_code = _parse_supplier_vendor_line(candidate)
            if vendor_name:
                return vendor_name, vendor_code
    return "", ""

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

    def _get_supplier_region_text(self, page: fitz.Page) -> str:
        """OCR only the top-left supplier block when full-page OCR misses the vendor line."""
        if not OCR_AVAILABLE:
            return ""
        if not configure_tesseract():
            return ""

        try:
            mat = fitz.Matrix(4, 4)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            width, height = img.size
            supplier_crop = img.crop((0, int(height * 0.10), int(width * 0.62), int(height * 0.44)))
            try:
                supplier_crop = ImageEnhance.Contrast(supplier_crop).enhance(2.8).convert("L")
                supplier_crop = supplier_crop.filter(ImageFilter.SHARPEN)
            except Exception:
                supplier_crop = supplier_crop.convert("L")

            texts = []
            for psm in (6, 4, 11):
                text = pytesseract.image_to_string(supplier_crop, lang="ind+eng", config=f"--psm {psm} --oem 3")
                if text.strip():
                    texts.append(text)
            return "\n".join(texts)
        except Exception as e:
            self.log(f"Supplier-region OCR failed: {str(e)[:120]}", "WARNING")
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
        vendor_name, vendor_code = _extract_supplier_block_vendor(source_lines + lines)
        if not vendor_name:
            supplier_text = self._get_supplier_region_text(page)
            if supplier_text.strip():
                supplier_lines = [l.strip() for l in supplier_text.split("\n") if l.strip()]
                vendor_name, vendor_code = _extract_supplier_block_vendor(supplier_lines + source_lines + lines)
                if not vendor_name:
                    vendor_name, vendor_code = _extract_supplier_region_vendor(supplier_lines)
                if vendor_name:
                    self.log("Vendor recovered from supplier-region OCR.")
        result.vendor_name = vendor_name
        result.vendor_code = vendor_code
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
