import pypdf
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_text_from_pdf(uploaded_file) -> List[Dict[str, Any]]:
    """
    Extracts text from a single PDF file page by page.
    Returns a list of dicts with keys: 'page_num', 'text'.
    """
    pages_data = []
    try:
        reader = pypdf.PdfReader(uploaded_file)
        num_pages = len(reader.pages)
        logger.info(f"Extracting text from {uploaded_file.name} ({num_pages} pages)")
        
        for i in range(num_pages):
            page = reader.pages[i]
            text = page.extract_text()
            if text:
                # Clean up whitespace and empty lines
                cleaned_lines = [line.strip() for line in text.splitlines() if line.strip()]
                cleaned_text = "\n".join(cleaned_lines)
                pages_data.append({
                    "page_num": i + 1,
                    "text": cleaned_text
                })
    except Exception as e:
        logger.error(f"Error extracting PDF text: {str(e)}")
        raise e
        
    return pages_data

def extract_text_from_multiple_pdfs(uploaded_files) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extracts text from multiple uploaded PDFs.
    Returns a dictionary mapping filename to a list of page data dicts.
    """
    all_pdfs_data = {}
    for uploaded_file in uploaded_files:
        pages = extract_text_from_pdf(uploaded_file)
        if pages:
            all_pdfs_data[uploaded_file.name] = pages
    return all_pdfs_data

def get_combined_outline_text(all_pdfs_data: Dict[str, List[Dict[str, Any]]], max_chars: int = 150000) -> str:
    """
    Combines text from all PDFs to create a summary/outline string for Gemini topic extraction.
    Truncates if text is exceptionally large, focusing on the first few pages and chapter headings.
    """
    combined_lines = []
    for filename, pages in all_pdfs_data.items():
        combined_lines.append(f"=== File: {filename} ===")
        for page in pages:
            # We add page headers to help Gemini identify subheadings
            combined_lines.append(f"--- Page {page['page_num']} ---")
            combined_lines.append(page['text'])
            
    full_text = "\n".join(combined_lines)
    if len(full_text) > max_chars:
        # If it's huge, keep the first 75,000 chars and last 75,000 chars, or just truncate
        logger.warning(f"Extracted text length ({len(full_text)}) exceeds max_chars ({max_chars}). Truncating for topic analysis.")
        half_chars = max_chars // 2
        return full_text[:half_chars] + "\n\n[TRUNCATED DUE TO SIZE]\n\n" + full_text[-half_chars:]
    return full_text

