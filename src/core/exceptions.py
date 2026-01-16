"""
Custom Exceptions - Tydliga exceptions för bättre felhantering.
"""

from typing import Optional, Dict, Any


class OCRMappingException(Exception):
    """Base exception för OCR Mapping applikationen."""
    
    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(message)
        self.user_message = user_message or message
        self.message = message


class PDFProcessingError(OCRMappingException):
    """Exception för fel vid PDF-bearbetning."""
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        page_num: Optional[int] = None,
        user_message: Optional[str] = None
    ):
        super().__init__(message, user_message)
        self.file_path = file_path
        self.page_num = page_num
        
        if not user_message:
            self.user_message = f"Kunde inte bearbeta PDF: '{file_path or 'Okänt'}'"
            if page_num is not None:
                self.user_message += f" (sida {page_num + 1})"


class OCRProcessingError(OCRMappingException):
    """Exception för fel vid OCR-bearbetning."""
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        page_num: Optional[int] = None,
        user_message: Optional[str] = None
    ):
        super().__init__(message, user_message)
        self.file_path = file_path
        self.page_num = page_num
        
        if not user_message:
            self.user_message = (
                "OCR-fel vid bearbetning av PDF.\n\n"
                "Kontrollera att Tesseract OCR är installerat och korrekt konfigurerat.\n\n"
                "Installationsguide: Se dokumentation för Tesseract-installation."
            )


class ExtractionError(OCRMappingException):
    """Exception för fel vid dataextraktion."""
    
    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        table_name: Optional[str] = None,
        pdf_path: Optional[str] = None,
        user_message: Optional[str] = None
    ):
        super().__init__(message, user_message)
        self.field_name = field_name
        self.table_name = table_name
        self.pdf_path = pdf_path
        
        if not user_message:
            if field_name:
                self.user_message = f"Kunde inte extrahera fält '{field_name}' från PDF."
            elif table_name:
                self.user_message = f"Kunde inte extrahera tabell '{table_name}' från PDF."
            else:
                self.user_message = "Extraktion misslyckades."
            self.user_message += "\n\nLoggar innehåller mer information för debugging."


class DependencyNotFoundError(OCRMappingException):
    """Exception för saknade dependencies."""
    
    def __init__(
        self,
        dependency_name: str,
        installation_guide: Optional[str] = None,
        affected_features: Optional[str] = None,
        user_message: Optional[str] = None
    ):
        message = f"{dependency_name} är inte installerat eller hittades inte."
        super().__init__(message, user_message)
        self.dependency_name = dependency_name
        self.installation_guide = installation_guide
        self.affected_features = affected_features
        
        if not user_message:
            self.user_message = f"{dependency_name} saknas.\n\n"
            if affected_features:
                self.user_message += f"Påverkade funktioner: {affected_features}\n\n"
            if installation_guide:
                self.user_message += f"Installationsinstruktioner:\n{installation_guide}"
            else:
                self.user_message += "Kontrollera dokumentationen för installationsinstruktioner."


class CoordinateError(OCRMappingException):
    """Exception för fel vid koordinathantering."""
    
    def __init__(
        self,
        message: str,
        coords: Optional[Dict[str, float]] = None,
        pdf_path: Optional[str] = None,
        user_message: Optional[str] = None
    ):
        super().__init__(message, user_message)
        self.coords = coords
        self.pdf_path = pdf_path
        
        if not user_message:
            self.user_message = (
                "Kunde inte mappa koordinater.\n\n"
                "Försök markera området igen eller kontrollera PDF:ens struktur."
            )


class TemplateError(OCRMappingException):
    """Exception för fel vid mallhantering."""
    
    def __init__(
        self,
        message: str,
        cluster_id: Optional[str] = None,
        user_message: Optional[str] = None
    ):
        super().__init__(message, user_message)
        self.cluster_id = cluster_id
        
        if not user_message:
            self.user_message = (
                f"Fel i mappningsmall för kluster '{cluster_id or 'Okänt'}'.\n\n"
                "Kontrollera att mappningsmallar är korrekt formaterade."
            )
