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

# Cache för dependency-checks (klassvariabel)
_tesseract_checked: Optional[bool] = None
_tesseract_path: Optional[str] = None
_poppler_checked: Optional[bool] = None
_poppler_path: Optional[str] = None


def check_tesseract_available(tesseract_cmd: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Kontrollerar om Tesseract OCR är tillgängligt.
    
    Args:
        tesseract_cmd: Sökväg till tesseract executable (optional)
    
    Returns:
        Tuple med (is_available, tesseract_path)
    """
    global _tesseract_checked, _tesseract_path
    
    # Om redan kontrollerad, returnera cached värde
    if _tesseract_checked is not None and tesseract_cmd is None:
        return _tesseract_checked, _tesseract_path
    
    found_path = None
    
    # Om explicit sökväg angiven
    if tesseract_cmd:
        if os.path.exists(tesseract_cmd):
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            found_path = tesseract_cmd
            _tesseract_checked = True
            _tesseract_path = found_path
            return True, found_path
    else:
        # Försök hitta automatiskt
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                found_path = path
                break
    
    # Verifiera att Tesseract fungerar
    try:
        pytesseract.get_tesseract_version()
        _tesseract_checked = True
        _tesseract_path = found_path
        return True, found_path
    except Exception:
        _tesseract_checked = False
        _tesseract_path = None
        return False, None


def check_poppler_available(poppler_path: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Kontrollerar om Poppler är tillgängligt.
    
    Args:
        poppler_path: Sökväg till Poppler bin-mapp (optional)
    
    Returns:
        Tuple med (is_available, poppler_path)
    """
    global _poppler_checked, _poppler_path
    
    # Om redan kontrollerad, returnera cached värde
    if _poppler_checked is not None and poppler_path is None:
        return _poppler_checked, _poppler_path
    
    found_path = None
    
    # Om explicit sökväg angiven
    if poppler_path:
        poppler_bin = Path(poppler_path)
        if poppler_bin.exists():
            os.environ["PATH"] = str(poppler_bin) + os.pathsep + os.environ.get("PATH", "")
            found_path = poppler_path
            _poppler_checked = True
            _poppler_path = found_path
            return True, found_path
    else:
        # Försök hitta automatiskt
        possible_poppler_paths = [
            r"C:\poppler\Library\bin",
            r"C:\Program Files\poppler\Library\bin",
            r"C:\Program Files (x86)\poppler\Library\bin",
        ]
        for path in possible_poppler_paths:
            if os.path.exists(path):
                os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
                found_path = path
                break
    
    # Verifiera att Poppler fungerar genom att testa om pdf2image kan använda det
    # Om found_path är None, försök använda system PATH
    if found_path:
        # Om vi hittat en sökväg, antag att Poppler fungerar
        # (verklig verifiering skulle kräva att vi försöker konvertera en PDF, vilket är dyrt)
        _poppler_checked = True
        _poppler_path = found_path
        return True, found_path
    else:
        # Ingen sökväg hittades, kontrollera om pdf2image kan hitta Poppler via PATH
        # Detta är en heuristisk kontroll - verklig verifiering kräver faktisk konvertering
        _poppler_checked = False
        _poppler_path = None
        return False, None


def get_tesseract_installation_guide() -> str:
    """Returnerar installationsguide för Tesseract."""
    return (
        "Installera Tesseract från: https://github.com/UB-Mannheim/tesseract/wiki\n"
        "Eller ange sökväg till tesseract.exe i PDFProcessor.__init__()\n\n"
        "För Windows:\n"
        "1. Ladda ner installeraren från: https://github.com/UB-Mannheim/tesseract/wiki\n"
        "2. Installera till standardplats (C:\\Program Files\\Tesseract-OCR)\n"
        "3. Starta om applikationen"
    )


def get_poppler_installation_guide() -> str:
    """Returnerar installationsguide för Poppler."""
    return (
        "Installera Poppler från: https://github.com/oschwartz10612/poppler-windows/releases/\n"
        "Extrahera till C:\\poppler och lägg till C:\\poppler\\Library\\bin till PATH\n\n"
        "För Windows:\n"
        "1. Ladda ner poppler från: https://github.com/oschwartz10612/poppler-windows/releases/\n"
        "2. Extrahera till C:\\poppler\n"
        "3. Lägg till C:\\poppler\\Library\\bin till system-PATH\n"
        "4. Starta om applikationen\n\n"
        "Se INSTALL_POPPLER.md för detaljerade instruktioner."
    )


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
        # Använd helper-funktioner för dependency-detektering
        self.tesseract_available, tesseract_found_path = check_tesseract_available(tesseract_cmd)
        if not self.tesseract_available:
            logger.warning("Tesseract OCR hittades inte. OCR-funktionalitet kommer inte att fungera.")
            logger.info(f"Installationsguide:\n{get_tesseract_installation_guide()}")
        
        self.poppler_available, self.poppler_path = check_poppler_available(poppler_path)
        if not self.poppler_available:
            logger.warning("Poppler hittades inte. PDF-till-bild konvertering kommer inte att fungera.")
            logger.info(f"Installationsguide:\n{get_poppler_installation_guide()}")
    
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
