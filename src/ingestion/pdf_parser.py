"""PDF document parser."""

import io
from pathlib import Path
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


class PDFParser:
    """Parse PDF documents to extract text and tables."""
    
    def parse(self, filepath: Path) -> dict:
        """Parse PDF and return structured content."""
        if pdfplumber is None:
            raise ImportError("pdfplumber is required for PDF parsing")
        
        content = {
            'text': '',
            'tables': [],
            'metadata': {},
            'pages': []
        }
        
        with pdfplumber.open(filepath) as pdf:
            content['metadata'] = {
                'num_pages': len(pdf.pages),
                'filename': filepath.name
            }
            
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ''
                content['text'] += f"\n\n--- Page {i + 1} ---\n\n" + page_text
                
                # Extract tables
                tables = page.extract_tables()
                for table in tables:
                    content['tables'].append({
                        'page': i + 1,
                        'data': table
                    })
                
                content['pages'].append({
                    'page_num': i + 1,
                    'text': page_text,
                    'tables': tables
                })
        
        return content
    
    def parse_bytes(self, pdf_bytes: bytes, filename: str = "unknown.pdf") -> dict:
        """Parse PDF from bytes."""
        if pdfplumber is None:
            raise ImportError("pdfplumber is required for PDF parsing")
        
        content = {
            'text': '',
            'tables': [],
            'metadata': {},
            'pages': []
        }
        
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            content['metadata'] = {
                'num_pages': len(pdf.pages),
                'filename': filename
            }
            
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ''
                content['text'] += f"\n\n--- Page {i + 1} ---\n\n" + page_text
                
                tables = page.extract_tables()
                for table in tables:
                    content['tables'].append({
                        'page': i + 1,
                        'data': table
                    })
                
                content['pages'].append({
                    'page_num': i + 1,
                    'text': page_text,
                    'tables': tables
                })
        
        return content
