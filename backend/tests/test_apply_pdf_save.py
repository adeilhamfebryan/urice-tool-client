import sys
from pathlib import Path

import fitz

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import engine


def _make_pdf(path: Path) -> None:
    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_text((72, 72), "PO test page")
        doc.save(path)
    finally:
        doc.close()


def test_process_pdf_only_extracts_preview_and_does_not_save_first_page(tmp_path, monkeypatch):
    source = tmp_path / "source.pdf"
    output = tmp_path / "processed"
    _make_pdf(source)

    monkeypatch.setattr(
        engine,
        "_extract_page_payload",
        lambda path: ([{"vendor_name": "OCR WRONG", "no_op": "000111222333"}], "PT TEST"),
    )

    payload = engine.process_pdf(str(source), str(output), "")

    assert payload["ok"] is True
    assert payload["source"] == str(source.resolve())
    assert payload["processed_pdf_path"] == ""
    assert payload["processed_pdf_filename"] == ""
    assert not output.exists()


def test_save_processed_pdf_uses_corrected_preview_vendor_and_no_op(tmp_path):
    source = tmp_path / "source.pdf"
    output = tmp_path / "processed"
    _make_pdf(source)

    payload = engine.save_processed_pdf(
        str(source),
        str(output),
        "LABORATORIUM SOLUSI INDONESIA, PT.",
        "0204025001132",
    )

    assert payload["ok"] is True
    assert payload["processed_pdf_filename"] == "LABORATORIUM_SOLUSI_INDONESIA_PT.-0204025001132.pdf"
    saved = Path(payload["processed_pdf_path"])
    assert saved.exists()
    assert saved.parent == output.resolve()

    doc = fitz.open(str(saved))
    try:
        assert len(doc) == 1
    finally:
        doc.close()