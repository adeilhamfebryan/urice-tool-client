"""
File service for Full Client.

Handles:
- Saving only the first page of a PDF with standardized name
- Determining output folder (respects settings for installed vs portable)
"""

import fitz
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from ..core.extraction import POExtractionResult


class FileService:
    def __init__(self, settings: Optional[dict] = None):
        self.settings = settings or {}

    def save_first_page_only(self, source_pdf_path: str, extraction_result: POExtractionResult) -> Tuple[str, str]:
        """
        Saves only the first page of the PDF with the proper name format.
        Returns (output_path, new_filename)
        """
        source_path = Path(source_pdf_path).resolve()
        original_name = source_path.name

        # Use first item for naming (prototype behavior)
        vname = extraction_result.vendor_name or "ONE TIME VENDOR"
        vnumber = extraction_result.vendor_code or "0007000940"
        no_op = extraction_result.no_op or datetime.now().strftime("%Y%m%d%H%M")

        clean_name = re.sub(r'[^A-Za-z0-9\s\.\-]', '', vname).strip()
        clean_name = ' '.join(clean_name.split())
        clean_name = re.sub(r'\s+', '_', clean_name)[:50].strip('_')

        new_filename = f"{clean_name}-{vnumber}-{no_op}.pdf"

        # Decide output directory
        output_base = self.settings.get("output_base", "")
        if output_base and Path(output_base).is_dir():
            processed_dir = Path(output_base) / f"PROCESSED_PO_{datetime.now().strftime('%Y%m%d')}"
        else:
            processed_dir = source_path.parent / "PROCESSED_PO"

        processed_dir.mkdir(parents=True, exist_ok=True)
        output_path = processed_dir / new_filename

        # Actually save first page
        try:
            doc = fitz.open(str(source_path))
            if len(doc) > 0:
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=0, to_page=0)
                new_doc.save(str(output_path), garbage=4, deflate=True)
                new_doc.close()
            doc.close()
        except Exception as e:
            print(f"[FileService] Failed to save first page: {e}")
            return "", ""

        return str(output_path), new_filename
