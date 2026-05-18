import pdfplumber
import logging

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_file) -> str:
    """
    Better PDF extraction using pdfplumber.
    Preserves table-like structure better than pypdf.
    """
    try:
        text_parts = []

        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text(
                    x_tolerance=2,
                    y_tolerance=2
                )
                if text:
                    text_parts.append(text)

        full_text = "\n".join(text_parts)
        logger.info(f"Extracted {len(full_text)} chars from PDF")
        return full_text

    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return ""

def convert_pdf_to_images(pdf_file) -> list:
    """
    Converts PDF pages to PIL Image objects for Gemini Vision.
    Requires Poppler to be installed on the system.
    """
    try:
        from pdf2image import convert_from_bytes
        
        # Reset file pointer and read bytes
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        pdf_file.seek(0) # Reset again for other users
        
        # Convert first 2 pages only to save tokens/time
        images = convert_from_bytes(pdf_bytes, dpi=150, last_page=2)
        logger.info(f"Converted {len(images)} PDF pages to images for vision fallback (DPI=150)")
        return images
    except Exception as e:
        logger.error(f"Failed to convert PDF to images: {e}")
        return []
