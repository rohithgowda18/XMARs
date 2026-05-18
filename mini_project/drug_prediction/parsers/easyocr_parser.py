import easyocr
import logging
import numpy as np
import io
from pdf2image import convert_from_bytes

logger = logging.getLogger(__name__)

# Initialize reader globally once
# detail=0 returns only text, paragraph=True groups text into lines
try:
    logger.info("Initializing EasyOCR reader (CPU mode)...")
    reader = easyocr.Reader(['en'], gpu=False)
except Exception as e:
    logger.error(f"Failed to initialize EasyOCR: {e}")
    reader = None

def extract_text_with_easyocr(pdf_file) -> str:
    """
    Backup OCR extraction using EasyOCR.
    Used ONLY when Gemini Vision fails.
    """
    if reader is None:
        logger.error("EasyOCR reader not initialized")
        return ""

    try:
        logger.info("Running EasyOCR fallback...")

        # Reset file pointer and read bytes
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        pdf_file.seek(0)

        # Convert first 2 pages only to save time
        images = convert_from_bytes(
            pdf_bytes,
            dpi=150,
            first_page=1,
            last_page=2
        )

        all_text = []

        for i, image in enumerate(images):
            logger.info(f"EasyOCR processing page {i+1}")
            
            # Convert PIL image to numpy array
            image_np = np.array(image)

            # Perform OCR
            results = reader.readtext(
                image_np,
                detail=0,
                paragraph=True
            )

            page_text = "\n".join(results)
            all_text.append(page_text)

        final_text = "\n".join(all_text)
        logger.info(f"EasyOCR extracted {len(final_text)} chars")
        logger.info(f"OCR text sample: {final_text[:500]}...")

        return final_text

    except Exception as e:
        logger.error(f"EasyOCR extraction failed: {e}")
        return ""
