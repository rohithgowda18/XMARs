import io
import logging
from pypdf import PdfReader

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_file) -> str:
    """
    Extracts raw text from a PDF file-like object.
    
    Args:
        pdf_file: A file-like object containing PDF data.
        
    Returns:
        str: Extracted text from all pages.
    """
    try:
        reader = PdfReader(pdf_file)
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        
        full_text = "\n".join(text_parts)
        logger.info(f"Extracted {len(full_text)} characters from PDF")
        return full_text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return ""
