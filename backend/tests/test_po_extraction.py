import fitz
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from urice_engine.core.extraction import POExtractor, _extract_supplier_region_vendor
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
        SUPPLIER
        BINTANG JAYA,PD.(OWNER: ANDY SUYANARTHA) - 7001234 PO Date - 28112024
        Jl. HRM. Mangundiprojo No. 38 A, Bumi Kedamaian,, Kel. PO No. : 55924007991
        """
    )
    try:
        result = POExtractor().extract(page, "55924007991.pdf")
    finally:
        doc.close()

    assert result.vendor_name == "BINTANG JAYA, PD."
    assert result.vendor_code == "7001234"
    assert result.no_op == "55924007991"


def test_extracts_supplier_name_before_noisy_po_date_label():
    doc, page = _page_with_text(
        """
        PT. SURYA UNGGAS:MANDIRI - JAMBI Page 1 of 1
        SUPPLIER INFORMATION
        SUMATRA MOTOR, TOKO(OWNER:KEENDY KUSUMA) - 701227 PO Date ~: 05.12.2024
        ISN Ne, MPU, Estimate date ofarival :- 12.12.2024
        36097142402239 :
        """
    )
    try:
        result = POExtractor().extract(page, "097142402239.pdf")
    finally:
        doc.close()

    assert result.vendor_name == "SUMATRA MOTOR, TOKO"
    assert result.vendor_code == "701227"
    assert result.no_op == "097142402239"


def test_does_not_use_transfer_info_when_supplier_block_has_no_valid_vendor():
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

    assert result.vendor_name == ""
    assert result.vendor_code == ""
    assert result.no_op == "204025001132"




def test_extracts_vendor_after_noisy_supplier_information_anchor():
    doc, page = _page_with_text(
        """
        PT. SINAR TERNAK SEJAHTERA - LAMPUNG
        [supeRSS~* SC INFORMATION
        SINAR JAYA, TOKO (LINA VIVIA HARNATA) - 7009488 PO Date . 18.03.2025
        Jl. Ikan Bawal No. 56 (Gudang Lelang), Teluk Betung,, Po No. > 098582500643
        """
    )
    try:
        result = POExtractor().extract(page, "098582500643.pdf")
    finally:
        doc.close()

    assert result.vendor_name == "SINAR JAYA, TOKO"
    assert result.vendor_code == "7009488"
    assert result.no_op == "098582500643"


def test_extracts_vendor_only_from_supplier_block_with_code():
    doc, page = _page_with_text(
        """
        PT. SINAR TERNAK SEJAHTERA - LAMPUNG
        SUPPLIER
        SINAR JAYA, TOKO (LINA VIVIA HARNATA) - 7009488
        Jl. Ikan Bawal No. 30 Gudang Lelang
        Contact : Lina Vivia Harnata
        INFORMATION
        PO No. : 098582500643
        """
    )
    try:
        result = POExtractor().extract(page, "098582500643.pdf")
    finally:
        doc.close()

    assert result.vendor_name == "SINAR JAYA, TOKO"
    assert result.vendor_code == "7009488"
    assert result.no_op == "098582500643"



def test_extracts_vendor_from_supplier_region_crop_without_anchor():
    vendor_name, vendor_code = _extract_supplier_region_vendor([
        "LABORATORIUM SOLUSI INDONESIA, PT. - 7014213 PO Date",
        "De Ploeit Centrale Office Building Lantai 9, No. 903,, Jl. PO No.",
        "Contact : Ellen Plant",
    ])

    assert vendor_name == "LABORATORIUM SOLUSI INDONESIA, PT."
    assert vendor_code == "7014213"


def test_extracts_vendor_from_supplier_region_crop_for_asia_indoteknik():
    vendor_name, vendor_code = _extract_supplier_region_vendor([
        "ASIA INDOTEKNIK GEMILANG, PT. - 7016731 PO Date",
        "Jl. H. Komarudin No. 60, LK II, RT. 017 / RW, 000,, Kel. PO No.",
        "Contact : Bapak Lukman Plant",
    ])

    assert vendor_name == "ASIA INDOTEKNIK GEMILANG, PT."
    assert vendor_code == "7016731"

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
