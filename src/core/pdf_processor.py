"""
PDF Processor - Hanterar PDF-läsning och OCR.
"""

import os
from typing import Optional, Tuple
from pathlib import Path
import PyPDF2
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import numpy as np
from .logger import get_logger
from .cache import get_cache

logger = get_logger()
cache = get_cache()


class PDFProcessor:
    """Hanterar PDF-läsning och OCR."""
    
    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
        poppler_path: Optional[str] = None
    ):
        """
        Initierar PDF-processor.
        
        Args:
            tesseract_cmd: Sökväg till tesseract executable (för Windows)
            poppler_path: Sökväg till Poppler bin-mapp (för Windows, t.ex. "C:\\poppler\\Library\\bin")
        """
        # Konfigurera Tesseract
        self.tesseract_available = False
        if tesseract_cmd:
            if os.path.exists(tesseract_cmd):
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
                self.tesseract_available = True
            else:
                logger.warning(f"Tesseract-sökväg angiven men hittades inte: {tesseract_cmd}")
        else:
            # Försök hitta tesseract automatiskt
            # Windows standard path
            possible_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    self.tesseract_available = True
                    break
        
        # Verifiera att Tesseract fungerar
        if not self.tesseract_available:
            try:
                pytesseract.get_tesseract_version()
                self.tesseract_available = True
            except Exception:
                logger.warning("Tesseract OCR hittades inte. OCR-funktionalitet kommer inte att fungera.")
                self.tesseract_available = False
        
        # Konfigurera Poppler
        self.poppler_available = False
        self.poppler_path = poppler_path
        if poppler_path:
            # Lägg till Poppler till PATH för denna session
            poppler_bin = Path(poppler_path)
            if poppler_bin.exists():
                os.environ["PATH"] = str(poppler_bin) + os.pathsep + os.environ.get("PATH", "")
                self.poppler_available = True
            else:
                logger.warning(f"Poppler-sökväg angiven men hittades inte: {poppler_path}")
        else:
            # Försök hitta Poppler automatiskt
            possible_poppler_paths = [
                r"C:\poppler\Library\bin",
                r"C:\Program Files\poppler\Library\bin",
                r"C:\Program Files (x86)\poppler\Library\bin",
            ]
            for path in possible_poppler_paths:
                if os.path.exists(path):
                    self.poppler_path = path
                    os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
                    self.poppler_available = True
                    break
        
        # Verifiera att Poppler fungerar (testa genom att försöka konvertera en test-PDF)
        if not self.poppler_available:
            # Kontrollera om pdf2image kan hitta poppler
            try:
                # Försök importera och testa
                from pdf2image.exceptions import PDFInfoNotInstalledError
                # Om vi kommer hit utan exception, är Poppler troligen tillgängligt via PATH
                self.poppler_available = True
            except Exception:
                logger.warning("Poppler hittades inte. PDF-till-bild konvertering kommer inte att fungera.")
                logger.info("Installera Poppler från: https://github.com/oschwartz10612/poppler-windows/releases/")
                self.poppler_available = False
    
    def extract_text(self, pdf_path: str, use_ocr: bool = False) -> str:
        """
        Extraherar text från PDF.
        
        Args:
            pdf_path: Sökväg till PDF-fil
            use_ocr: Om True, använd OCR även om PDF har text-lager
        
        Returns:
            Extraherad text
        """
        # Kolla cache först (endast om use_ocr=False, eftersom OCR kan variera)
        if not use_ocr:
            cached_text = cache.get_cached_text(pdf_path)
            if cached_text:
                return cached_text
        
        try:
            # Försök extrahera text direkt från PDF
            text = self._extract_text_from_pdf(pdf_path)
            
            # Om ingen text hittades eller use_ocr=True, använd OCR
            if not text.strip() or use_ocr:
                ocr_text = self._extract_text_with_ocr(pdf_path)
                if ocr_text:
                    text = ocr_text
            
            # Cache texten (endast om use_ocr=False)
            if text and not use_ocr:
                cache.cache_text(pdf_path, text)
            
            return text
        except Exception as e:
            logger.error(f"Fel vid extraktion från {pdf_path}: {e}", exc_info=True)
            return ""
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extraherar text direkt från PDF (om text-lager finns)."""
        text_parts = []
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                    except Exception as e:
                        logger.warning(f"Fel vid läsning av sida {page_num}: {e}")
        
        except Exception as e:
            logger.error(f"Fel vid öppning av PDF: {e}", exc_info=True)
        
        return "\n".join(text_parts)
    
    def _extract_text_with_ocr(self, pdf_path: str) -> str:
        """Extraherar text med OCR."""
        if not self.tesseract_available:
            error_msg = "Tesseract OCR är inte installerat eller hittades inte."
            logger.error(error_msg)
            raise RuntimeError(
                f"{error_msg}\n"
                "Installera Tesseract från: https://github.com/UB-Mannheim/tesseract/wiki\n"
                "Eller ange sökväg till tesseract.exe i PDFProcessor.__init__()"
            )
        
        if not self.poppler_available:
            error_msg = "Poppler är inte installerat eller hittades inte."
            logger.error(error_msg)
            raise RuntimeError(
                f"{error_msg}\n"
                "Installera Poppler från: https://github.com/oschwartz10612/poppler-windows/releases/\n"
                "Extrahera till C:\\poppler och lägg till C:\\poppler\\Library\\bin till PATH"
            )
        
        text_parts = []
        
        try:
            # Konvertera PDF till bilder
            # Använd poppler_path om det är konfigurerat
            if self.poppler_path:
                images = convert_from_path(
                    pdf_path,
                    dpi=300,
                    poppler_path=self.poppler_path
                )
            else:
                images = convert_from_path(pdf_path, dpi=300)
            
            for image in images:
                # Förbehandling för bättre OCR
                processed_image = self._preprocess_image(image)
                
                # OCR med svenska och engelska
                ocr_text = pytesseract.image_to_string(
                    processed_image,
                    lang='swe+eng'
                )
                text_parts.append(ocr_text)
        
        except Exception as e:
            logger.error(f"Fel vid OCR: {e}", exc_info=True)
            raise
        
        return "\n".join(text_parts)
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Förbehandlar bild för bättre OCR-resultat."""
        # Konvertera till grayscale
        if image.mode != 'L':
            image = image.convert('L')
        
        # Konvertera till numpy array för processing
        img_array = np.array(image)
        
        # Enkel thresholding (kan förbättras med adaptive thresholding)
        # För nu, returnera originalet
        
        return image
    
    def get_page_image(self, pdf_path: str, page_num: int = 0, dpi: int = 200) -> Optional[Image.Image]:
        """Hämtar en sida som bild."""
        if not self.poppler_available:
            error_msg = "Poppler är inte installerat eller hittades inte."
            logger.error(error_msg)
            raise RuntimeError(
                f"{error_msg}\n"
                "Installera Poppler från: https://github.com/oschwartz10612/poppler-windows/releases/\n"
                "Extrahera till C:\\poppler och lägg till C:\\poppler\\Library\\bin till PATH"
            )
        
        # Kolla cache först
        cached_image = cache.get_cached_image(pdf_path, page_num, dpi)
        if cached_image:
            return cached_image
        
        try:
            # Använd poppler_path om det är konfigurerat
            if self.poppler_path:
                images = convert_from_path(
                    pdf_path,
                    first_page=page_num+1,
                    last_page=page_num+1,
                    dpi=dpi,
                    poppler_path=self.poppler_path
                )
            else:
                images = convert_from_path(
                    pdf_path,
                    first_page=page_num+1,
                    last_page=page_num+1,
                    dpi=dpi
                )
            if images:
                image = images[0]
                # Cache bilden
                cache.cache_image(pdf_path, page_num, image, dpi)
                return image
        except Exception as e:
            error_msg = f"Fel vid konvertering av sida {page_num}: {e}"
            logger.error(error_msg, exc_info=True)
            if "poppler" in str(e).lower():
                tip_msg = (
                    "TIP: Installera Poppler från https://github.com/oschwartz10612/poppler-windows/releases/\n"
                    "     Extrahera till C:\\poppler och lägg till C:\\poppler\\Library\\bin till PATH"
                )
                logger.warning(tip_msg)
                raise RuntimeError(f"{error_msg}\n{tip_msg}") from e
            raise
        return None
    
    def get_pdf_dimensions(self, pdf_path: str) -> Optional[Tuple[float, float]]:
        """Hämtar PDF-dimensioner (width, height i points)."""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                if pdf_reader.pages:
                    page = pdf_reader.pages[0]
                    return (float(page.mediabox.width), float(page.mediabox.height))
        except Exception as e:
            logger.error(f"Fel vid läsning av PDF-dimensioner: {e}", exc_info=True)
        return None
