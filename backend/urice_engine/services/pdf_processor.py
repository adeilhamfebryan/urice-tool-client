"""
PDF Processing Service.

Handles opening PDFs, taking first page, and calling the extraction engine.
"""

import fitz
from pathlib import Path
from typing import Optional, Tuple

from ..core.extraction import extract_data_from_pdf, POExtractionResult


class PDFProcessor:
    """Service for processing PO PDFs."""

    def process_first_page(self, pdf_path: str) -> Tuple[Optional[POExtractionResult], Optional[str], Optional[str]]:
        """
        Process a single PDF file:
        - Open PDF
        - Take only the first page
        - Run extraction
        - Return (extraction_result, output_path_for_processed_pdf, new_filename)

        Note: Actual saving of the processed first-page PDF is handled separately
        (so the installer / app can decide where to put files).
        """
        try:
            pdf_path = str(Path(pdf_path).resolve())
            original_name = Path(pdf_path).name

            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                doc.close()
                return None, None, None

            page = doc[0]

            # Run extraction
            result = extract_data_from_pdf(page, original_name)

            # Close original doc (we don't save here)
            doc.close()

            return result, None, None   # output path & filename will be decided by caller

        except Exception as e:
            print(f"[PDFProcessor] Error processing {pdf_path}: {e}")
            return None, None, None
