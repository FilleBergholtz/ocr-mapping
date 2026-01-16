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
            
            # Förbehandla bilden för bättre OCR-resultat
            # Använd PDFProcessor's förbehandling om tillgänglig
            try:
                processed_image = self.pdf_processor._preprocess_image(
                    table_region,
                    enable_adaptive_threshold=True,
                    enable_noise_reduction=True,
                    enable_contrast_enhancement=True,
                    enable_skew_correction=False  # Skew correction kan vara för aggressiv för små områden
                )
            except Exception:
                # Om förbehandling misslyckas, använd originalbild
                processed_image = table_region
            
            # OCR på hela tabellen med angivet språk
            text = pytesseract.image_to_string(processed_image, lang=language)
            
            if not text or not text.strip():
                logger.warning(f"Ingen text extraherad från tabellområde vid koordinater: {table_coords}")
                return []
            
            # Dela upp i rader
            lines = text.split('\n')
            rows = []
            for line in lines:
                line = line.strip()
                if line:
                    # Försök identifiera kolumner (flera mellanslag, tabs, eller lodräta linjer)
                    # Testa olika separationsmönster
                    columns = re.split(r'\s{2,}|\t', line)  # Flera mellanslag eller tabs
                    
                    # Om inga kolumner hittas med flera mellanslag, försök med enkla mellanslag
                    if len(columns) == 1:
                        # Försök med enkla mellanslag för rader som ser ut som tabellrader
                        columns = line.split()
                        # Om raden har flera ord, behandla varje ord som kolumn
                        if len(columns) >= 2:
                            rows.append([col.strip() for col in columns])
                        else:
                            # Om bara ett ord, lägg till som en-kolumns rad (för debugging)
                            rows.append([line.strip()])
                    else:
                        # Flera kolumner hittades med flera mellanslag/tabs
                        rows.append([col.strip() for col in columns])
            
            if not rows:
                logger.warning(f"Inga rader extraherade från tabellområde. Extraherad text: '{text[:100]}...'")
            
            return rows
        
        except Exception as e:
            logger.error(f"Fel vid extraktion av tabell: {e}", exc_info=True)
            return []
    
    def extract_table_cell(
        self,
        pdf_path: str,
        page_num: int,
        cell_coords: dict,
        pdf_width: float,
        pdf_height: float,
        language: str = "swe+eng"
    ) -> str:
        """
        Extraherar text från en specifik cell i en tabell.
        
        Args:
            pdf_path: Sökväg till PDF
            page_num: Sidnummer (0-indexerat)
            cell_coords: Dictionary med x, y, width, height (normaliserade 0.0-1.0)
            pdf_width: PDF:s bredd i points
            pdf_height: PDF:s höjd i points
            language: Tesseract språkkod
        
        Returns:
            Extraherad text från cellen
        """
        try:
            # Hämta PDF-bild
            pdf_image = self.pdf_processor.get_page_image(pdf_path, page_num)
            if not pdf_image:
                return ""
            
            # Konvertera normaliserade koordinater till pixel-koordinater
            img_width, img_height = pdf_image.size
            
            x = int(cell_coords.get("x", 0) * img_width)
            y = int(cell_coords.get("y", 0) * img_height)
            width = int(cell_coords.get("width", 0) * img_width)
            height = int(cell_coords.get("height", 0) * img_height)
            
            # Säkerställ att koordinaterna är inom bildens gränser
            x = max(0, min(img_width, x))
            y = max(0, min(img_height, y))
            width = max(1, min(img_width - x, width))
            height = max(1, min(img_height - y, height))
            
            # Klipp ut cellområdet
            cell_region = pdf_image.crop((x, y, x + width, y + height))
            
            # Förbehandla bilden för bättre OCR-resultat
            try:
                processed_image = self.pdf_processor._preprocess_image(
                    cell_region,
                    enable_adaptive_threshold=True,
                    enable_noise_reduction=True,
                    enable_contrast_enhancement=True,
                    enable_skew_correction=False
                )
            except Exception:
                processed_image = cell_region
            
            # OCR på cellen med angivet språk
            text = pytesseract.image_to_string(processed_image, lang=language)
            return text.strip()
        
        except Exception as e:
            logger.error(f"Fel vid extraktion från cell: {e}", exc_info=True)
            return ""