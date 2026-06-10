import fitz
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from urice_engine.core.extraction import POExtractor


def _page_with_text(text: str):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc, page


def test_extracts_ocr_variation_of_po_no_before_phone_numbers():
    doc, page = _page_with_text(
        """
        INFORMATION
        PO Date : 19.05.2025
        P0 N0 . : 204025001132
        Estimate date of arrival : 19.06.2025
        Plant : Lampung
        Payment term : 30 Hari Setelah Invoice diterima Kasir
        CONTACT PHONE : 081234567890
        """
    )
    try:
        result = POExtractor().extract(page, "source.pdf")
    finally:
        doc.close()

    assert result.no_op == "204025001132"


def test_extracts_no_op_after_label_when_vendor_code_appears_first():
    doc, page = _page_with_text(
        """
        Alamat Supplier Informasi
        TELINDO NUSANTARA, PT. - 0007008013 No. OP . 1871042477
        Telp : 62-021-52920727 Org. Pembelian : COM-COMMERCIAL
        """
    )
    try:
        result = POExtractor().extract(page, "1871042477.pdf")
    finally:
        doc.close()

    assert result.no_op == "1871042477"


def test_extracts_no_op_after_label_for_one_time_vendor_line():
    doc, page = _page_with_text(
        """
        Alamat Supplier Informasi
        ONE TIME VENDOR - 0007000940 No. OP : 1871045323
        Group Pembelian : G11-ME Parts & Pond Ma
        """
    )
    try:
        result = POExtractor().extract(page, "1871045323.pdf")
    finally:
        doc.close()

    assert result.no_op == "1871045323"
