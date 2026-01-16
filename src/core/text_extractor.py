"""
Text Extractor - Extraherar text från specifika områden i PDF:er.
"""

from typing import Optional, List
from PIL import Image
import pytesseract
import re
from .pdf_processor import PDFProcessor
from .logger import get_logger

logger = get_logger()


class TextExtractor:
    """Extraherar text från specifika koordinater i PDF:er."""
    
    def __init__(self, pdf_processor: PDFProcessor):
        self.pdf_processor = pdf_processor
    
    def extract_text_from_region(
        self,
        pdf_path: str,
        page_num: int,
        coords: dict,
        pdf_width: float,
        pdf_height: float,
        language: str = "swe+eng"
    ) -> str:
        """
        Extraherar text från ett specifikt område i PDF:en.
        
        Args:
            pdf_path: Sökväg till PDF
            page_num: Sidnummer (0-indexerat)
            coords: Dictionary med x, y, width, height (normaliserade 0.0-1.0)
            pdf_width: PDF:s bredd i points
            pdf_height: PDF:s höjd i points
        
        Returns:
            Extraherad text från området
        """
        try:
            # Hämta PDF-bild
            pdf_image = self.pdf_processor.get_page_image(pdf_path, page_num)
            if not pdf_image:
                return ""
            
            # Konvertera normaliserade koordinater till pixel-koordinater
            img_width, img_height = pdf_image.size
            
            x = int(coords.get("x", 0) * img_width)
            y = int(coords.get("y", 0) * img_height)
            width = int(coords.get("width", 0) * img_width)
            height = int(coords.get("height", 0) * img_height)
            
            # Klipp ut området
            region = pdf_image.crop((x, y, x + width, y + height))
            
            # OCR på området med angivet språk
            text = pytesseract.image_to_string(region, lang=language)
            return text.strip()
        
        except Exception as e:
            logger.error(f"Fel vid extraktion från område: {e}", exc_info=True)
            return ""
    
    def extract_table_text(
        self,
        pdf_path: str,
        page_num: int,
        table_coords: dict,
        pdf_width: float,
        pdf_height: float,
        language: str = "swe+eng"
    ) -> list:
        """
        Extraherar text från ett tabellområde, rad för rad.
        
        Returns:
            Lista med rader, varje rad är en lista med kolumner
        """
        try:
            # Hämta PDF-bild
            pdf_image = self.pdf_processor.get_page_image(pdf_path, page_num)
            if not pdf_image:
                return []
            
            # Konvertera koordinater
            img_width, img_height = pdf_image.size
            
            x = int(table_coords.get("x", 0) * img_width)
            y = int(table_coords.get("y", 0) * img_height)
            width = int(table_coords.get("width", 0) * img_width)
            height = int(table_coords.get("height", 0) * img_height)
            
            # Klipp ut tabellområdet
            table_region = pdf_image.crop((x, y, x + width, y + height))
            
            # OCR på hela tabellen med angivet språk
            text = pytesseract.image_to_string(table_region, lang=language)
            
            # Dela upp i rader
            lines = text.split('\n')
            rows = []
            for line in lines:
                line = line.strip()
                if line:
                    # Försök identifiera kolumner (flera mellanslag eller tabs)
                    columns = re.split(r'\s{2,}|\t', line)
                    if len(columns) > 1:
                        rows.append([col.strip() for col in columns])
            
            return rows
        
        except Exception as e:
            logger.error(f"Fel vid extraktion av tabell: {e}", exc_info=True)
            return []
