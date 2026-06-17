import fitz
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from urice_engine.core.extraction import POExtractor
from engine import _extract_company_name


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


def test_extracts_supplier_name_before_po_date_label():
    doc, page = _page_with_text(
        """
        PT.PRIMAFOOD INTERNATIONAL Page 1 of 1
        PURCHASE ORDER
        INFORMATION
        BINTANG JAYA,PD.(OWNER: ANDY SUYANARTHA) - | PO Date - 28112024
        Jl. HRM. Mangundiprojo No. 38 A, Bumi Kedamaian,, Kel. PO No. : 55924007991
        """
    )
    try:
        result = POExtractor().extract(page, "55924007991.pdf")
    finally:
        doc.close()

    assert result.vendor_name == "BINTANG JAYA,PD."
    assert result.no_op == "55924007991"


def test_extracts_supplier_name_before_noisy_po_date_label():
    doc, page = _page_with_text(
        """
        PT. SURYA UNGGAS:MANDIRI - JAMBI Page 1 of 1
        SUPPLIER INFORMATION
        SUMATRA MOTOR, TOKO(OWNER:KEENDY KUSUMA) - PO Date ~: 05.12.2024
        ISN Ne, MPU, Estimate date ofarival :- 12.12.2024
        36097142402239 :
        """
    )
    try:
        result = POExtractor().extract(page, "097142402239.pdf")
    finally:
        doc.close()

    assert result.vendor_name == "SUMATRA MOTOR, TOKO"
    assert result.no_op == "097142402239"


def test_rescues_vendor_from_transfer_info_when_supplier_line_is_address_noise():
    doc, page = _page_with_text(
        """
        PT. CHAROEN POKPHAND JAYA FARM Page 1 of 1
        SUPPLIER INFORMATION
        ace fo Off Maa, PT. - 3 ie i PO Date | | 1 19.05.2025 |
        De Ploeit Centrale Office Building Lantai 9, No. 903,, Jl. PO No. - 204 132
        Transfer info : PT. Laboratorium Solusi Indonesia Payment term :
        204025001132
        """
    )
    try:
        result = POExtractor().extract(page, "204025001132.pdf")
    finally:
        doc.close()

    assert result.vendor_name == "LABORATORIUM SOLUSI INDONESIA, PT."
    assert result.no_op == "204025001132"


def test_extracts_company_name_from_top_pt_header_before_address():
    text = """
    PT.PRIMAFOOD INTERNATIONAL Page 1 of 1
    NPWP No. 1 0020391769056000 02/12/2024
    Alamat NPWP : JI, Ancol Barat VIII No. 1, Pademangan,
    PURCHASE ORDER
    """

    assert _extract_company_name(text) == "PT.PRIMAFOOD INTERNATIONAL"


def test_extracts_company_name_with_ocr_colon_noise():
    text = """
    PT. SURYA UNGGAS:MANDIRI - JAMBI Gf sy Page 1 of 1
    NPWP No. : 0026078808451000 2 06/12/2024
    Alamat NPWP: PERUMAHAN CITRA RAYA RUKO
    PURCHASE ORDER
    """

    assert _extract_company_name(text) == "PT. SURYA UNGGAS MANDIRI - JAMBI"
