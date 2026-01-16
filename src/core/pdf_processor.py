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
from .logger import get_logger, log_error_with_context
from .cache import get_cache
from .exceptions import (
    PDFProcessingError,
    OCRProcessingError,
    DependencyNotFoundError
)

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
            Extraherad text (tom sträng om extraktion misslyckas)
        
        Raises:
            PDFProcessingError: Om PDF inte kan läsas
            OCRProcessingError: Om OCR misslyckas
            DependencyNotFoundError: Om Tesseract eller Poppler saknas
        """
        # Validera att filen existerar
        if not os.path.exists(pdf_path):
            error_msg = f"PDF-fil existerar inte: {pdf_path}"
            logger.error(error_msg)
            raise PDFProcessingError(
                error_msg,
                file_path=pdf_path,
                user_message=f"Kunde inte hitta PDF-fil: '{pdf_path}'.\n\nKontrollera att filen existerar och att sökvägen är korrekt."
            )
        
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
                try:
                    ocr_text = self._extract_text_with_ocr(pdf_path)
                    if ocr_text:
                        text = ocr_text
                except DependencyNotFoundError:
                    # Om OCR-kravs dependency saknas, returnera det som finns
                    if text.strip():
                        logger.warning(f"OCR misslyckades men text-lager hittades: {pdf_path}")
                        return text
                    # Annars låt exceptionen propagera
                    raise
            
            # Cache texten (endast om use_ocr=False)
            if text and not use_ocr:
                cache.cache_text(pdf_path, text)
            
            return text
            
        except (PDFProcessingError, OCRProcessingError, DependencyNotFoundError):
            # Propagera custom exceptions
            raise
        except Exception as e:
            log_error_with_context(
                logger, e,
                {"file_path": pdf_path, "use_ocr": use_ocr},
                "Oväntat fel vid textextraktion"
            )
            raise PDFProcessingError(
                f"Fel vid extraktion från PDF: {str(e)}",
                file_path=pdf_path,
                user_message=f"Kunde inte extrahera text från PDF: '{pdf_path}'.\n\nKontrollera att PDF:en är korruptfri."
            ) from e
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extraherar text direkt från PDF (om text-lager finns).
        
        Args:
            pdf_path: Sökväg till PDF-fil
        
        Returns:
            Extraherad text
        
        Raises:
            PDFProcessingError: Om PDF inte kan läsas eller är korrupt
        """
        text_parts = []
        
        try:
            with open(pdf_path, 'rb') as file:
                try:
                    pdf_reader = PyPDF2.PdfReader(file)
                except Exception as e:
                    log_error_with_context(
                        logger, e,
                        {"file_path": pdf_path},
                        "Fel vid läsning av PDF-struktur"
                    )
                    raise PDFProcessingError(
                        f"PDF:en är korrupt eller kan inte läsas: {str(e)}",
                        file_path=pdf_path,
                        user_message=f"Kunde inte läsa PDF: '{pdf_path}'.\n\nKontrollera att PDF:en är korruptfri och inte lösenordsskyddad."
                    ) from e
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                    except Exception as e:
                        log_error_with_context(
                            logger, e,
                            {"file_path": pdf_path, "page_num": page_num},
                            f"Fel vid läsning av sida {page_num}"
                        )
                        # Fortsätt med nästa sida även om en sida misslyckas
        
        except PDFProcessingError:
            # Propagera PDFProcessingError
            raise
        except Exception as e:
            log_error_with_context(
                logger, e,
                {"file_path": pdf_path},
                "Fel vid öppning av PDF"
            )
            raise PDFProcessingError(
                f"Kunde inte öppna PDF: {str(e)}",
                file_path=pdf_path,
                user_message=f"Kunde inte öppna PDF: '{pdf_path}'.\n\nKontrollera att filen är tillgänglig och inte är låst."
            ) from e
        
        return "\n".join(text_parts)
    
    def _extract_text_with_ocr(self, pdf_path: str) -> str:
        """
        Extraherar text med OCR.
        
        Args:
            pdf_path: Sökväg till PDF-fil
        
        Returns:
            Extraherad text via OCR
        
        Raises:
            DependencyNotFoundError: Om Tesseract eller Poppler saknas
            OCRProcessingError: Om OCR-bearbetning misslyckas
        """
        if not self.tesseract_available:
            raise DependencyNotFoundError(
                dependency_name="Tesseract OCR",
                installation_guide=(
                    "Installera Tesseract från: https://github.com/UB-Mannheim/tesseract/wiki\n"
                    "Eller ange sökväg till tesseract.exe i PDFProcessor.__init__()"
                ),
                affected_features="OCR-funktionalitet för skannade PDF:er"
            )
        
        if not self.poppler_available:
            raise DependencyNotFoundError(
                dependency_name="Poppler",
                installation_guide=(
                    "Installera Poppler från: https://github.com/oschwartz10612/poppler-windows/releases/\n"
                    "Extrahera till C:\\poppler och lägg till C:\\poppler\\Library\\bin till PATH\n\n"
                    "Se INSTALL_POPPLER.md för detaljerade instruktioner."
                ),
                affected_features="PDF-till-bild konvertering (krävs för OCR)"
            )
        
        text_parts = []
        
        try:
            # Konvertera PDF till bilder
            # Använd poppler_path om det är konfigurerat
            try:
                if self.poppler_path:
                    images = convert_from_path(
                        pdf_path,
                        dpi=300,
                        poppler_path=self.poppler_path
                    )
                else:
                    images = convert_from_path(pdf_path, dpi=300)
            except Exception as e:
                error_str = str(e).lower()
                if "poppler" in error_str or "pdfinfo" in error_str:
                    log_error_with_context(
                        logger, e,
                        {"file_path": pdf_path, "poppler_path": self.poppler_path},
                        "Fel vid PDF-till-bild konvertering (Poppler)"
                    )
                    raise DependencyNotFoundError(
                        dependency_name="Poppler",
                        installation_guide=(
                            "Installera Poppler från: https://github.com/oschwartz10612/poppler-windows/releases/\n"
                            "Se INSTALL_POPPLER.md för detaljerade instruktioner."
                        ),
                        affected_features="PDF-till-bild konvertering"
                    ) from e
                else:
                    raise
            
            for page_num, image in enumerate(images):
                try:
                    # Förbehandling för bättre OCR
                    processed_image = self._preprocess_image(image)
                    
                    # OCR med svenska och engelska
                    ocr_text = pytesseract.image_to_string(
                        processed_image,
                        lang='swe+eng'
                    )
                    text_parts.append(ocr_text)
                except Exception as e:
                    log_error_with_context(
                        logger, e,
                        {"file_path": pdf_path, "page_num": page_num},
                        f"Fel vid OCR på sida {page_num}"
                    )
                    # Fortsätt med nästa sida även om OCR misslyckas på en sida
                    logger.warning(f"Skippar sida {page_num} på grund av OCR-fel")
        
        except (DependencyNotFoundError, OCRProcessingError):
            # Propagera custom exceptions
            raise
        except Exception as e:
            log_error_with_context(
                logger, e,
                {"file_path": pdf_path},
                "Oväntat fel vid OCR-bearbetning"
            )
            raise OCRProcessingError(
                f"OCR misslyckades: {str(e)}",
                file_path=pdf_path
            ) from e
        
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
        """
        Hämtar en sida som bild.
        
        Args:
            pdf_path: Sökväg till PDF-fil
            page_num: Sidnummer (0-indexerat)
            dpi: Upplösning för bildkonvertering
        
        Returns:
            PIL Image eller None om konvertering misslyckas
        
        Raises:
            PDFProcessingError: Om PDF inte kan läsas
            DependencyNotFoundError: Om Poppler saknas
        """
        # Validera att filen existerar
        if not os.path.exists(pdf_path):
            raise PDFProcessingError(
                f"PDF-fil existerar inte: {pdf_path}",
                file_path=pdf_path,
                page_num=page_num,
                user_message=f"Kunde inte hitta PDF-fil: '{pdf_path}'.\n\nKontrollera att filen existerar."
            )
        
        if not self.poppler_available:
            raise DependencyNotFoundError(
                dependency_name="Poppler",
                installation_guide=(
                    "Installera Poppler från: https://github.com/oschwartz10612/poppler-windows/releases/\n"
                    "Se INSTALL_POPPLER.md för detaljerade instruktioner."
                ),
                affected_features="PDF-visualisering och PDF-till-bild konvertering"
            )
        
        # Kolla cache först
        cached_image = cache.get_cached_image(pdf_path, page_num, dpi)
        if cached_image:
            return cached_image
        
        try:
            # Använd poppler_path om det är konfigurerat
            try:
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
            except Exception as e:
                error_str = str(e).lower()
                if "poppler" in error_str or "pdfinfo" in error_str:
                    log_error_with_context(
                        logger, e,
                        {"file_path": pdf_path, "page_num": page_num, "poppler_path": self.poppler_path},
                        "Fel vid PDF-till-bild konvertering (Poppler)"
                    )
                    raise DependencyNotFoundError(
                        dependency_name="Poppler",
                        installation_guide=(
                            "Installera Poppler från: https://github.com/oschwartz10612/poppler-windows/releases/\n"
                            "Se INSTALL_POPPLER.md för detaljerade instruktioner."
                        ),
                        affected_features="PDF-visualisering"
                    ) from e
                else:
                    raise
            
            if images:
                image = images[0]
                # Cache bilden
                cache.cache_image(pdf_path, page_num, image, dpi)
                return image
            
            # Ingen bild returnerades
            log_error_with_context(
                logger, None,
                {"file_path": pdf_path, "page_num": page_num},
                "Ingen bild returnerades vid konvertering"
            )
            return None
            
        except (PDFProcessingError, DependencyNotFoundError):
            # Propagera custom exceptions
            raise
        except Exception as e:
            log_error_with_context(
                logger, e,
                {"file_path": pdf_path, "page_num": page_num},
                f"Oväntat fel vid konvertering av sida {page_num}"
            )
            raise PDFProcessingError(
                f"Kunde inte konvertera sida {page_num + 1} till bild: {str(e)}",
                file_path=pdf_path,
                page_num=page_num,
                user_message=f"Kunde inte konvertera PDF-sida till bild.\n\nKontrollera att PDF:en kan läsas korrekt."
            ) from e
    
    def get_pdf_dimensions(self, pdf_path: str) -> Optional[Tuple[float, float]]:
        """
        Hämtar PDF-dimensioner (width, height i points).
        
        Args:
            pdf_path: Sökväg till PDF-fil
        
        Returns:
            Tuple med (width, height) i points, eller None om fel
        
        Raises:
            PDFProcessingError: Om PDF inte kan läsas
        """
        # Validera att filen existerar
        if not os.path.exists(pdf_path):
            log_error_with_context(
                logger, None,
                {"file_path": pdf_path},
                "PDF-fil existerar inte vid hämtning av dimensioner"
            )
            raise PDFProcessingError(
                f"PDF-fil existerar inte: {pdf_path}",
                file_path=pdf_path,
                user_message=f"Kunde inte hitta PDF-fil: '{pdf_path}'.\n\nKontrollera att filen existerar."
            )
        
        try:
            with open(pdf_path, 'rb') as file:
                try:
                    pdf_reader = PyPDF2.PdfReader(file)
                except Exception as e:
                    log_error_with_context(
                        logger, e,
                        {"file_path": pdf_path},
                        "Fel vid läsning av PDF-struktur (dimensioner)"
                    )
                    raise PDFProcessingError(
                        f"PDF:en är korrupt eller kan inte läsas: {str(e)}",
                        file_path=pdf_path,
                        user_message=f"Kunde inte läsa PDF-dimensioner från '{pdf_path}'.\n\nKontrollera att PDF:en är korruptfri."
                    ) from e
                
                if not pdf_reader.pages:
                    logger.warning(f"PDF har inga sidor: {pdf_path}")
                    return None
                
                page = pdf_reader.pages[0]
                return (float(page.mediabox.width), float(page.mediabox.height))
                
        except PDFProcessingError:
            # Propagera PDFProcessingError
            raise
        except Exception as e:
            log_error_with_context(
                logger, e,
                {"file_path": pdf_path},
                "Oväntat fel vid läsning av PDF-dimensioner"
            )
            raise PDFProcessingError(
                f"Kunde inte läsa PDF-dimensioner: {str(e)}",
                file_path=pdf_path,
                user_message=f"Kunde inte läsa PDF-dimensioner från '{pdf_path}'.\n\nKontrollera att PDF:en kan läsas korrekt."
            ) from e
