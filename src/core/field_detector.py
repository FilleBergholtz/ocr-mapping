"""
Field Detector - Automatisk identifiering av fälttyper.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class FieldType(str, Enum):
    """Enum för fälttyper."""
    INVOICE_NUMBER = "invoice_number"
    DATE = "date"
    AMOUNT = "amount"
    TOTAL_AMOUNT = "total_amount"
    VAT_NUMBER = "vat_number"
    COMPANY_NAME = "company_name"
    ADDRESS = "address"
    EMAIL = "email"
    PHONE = "phone"
    ORDER_NUMBER = "order_number"
    PROJECT_NUMBER = "project_number"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    """Enum för konfidensnivåer."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class FieldDetection:
    """Representerar en fältdetektering."""
    field_type: FieldType
    confidence: ConfidenceLevel
    value: str
    pattern_match: Optional[str] = None
    context_keywords: List[str] = None


class FieldDetector:
    """Detekterar fälttyper baserat på text och mönster."""
    
    def __init__(self):
        """Initierar FieldDetector med regex-mönster och nyckelord."""
        # Regex-mönster för olika fälttyper
        self.patterns = {
            FieldType.INVOICE_NUMBER: [
                re.compile(r'^[A-Z0-9\-/]{4,20}$', re.IGNORECASE),  # Fakturanummer: bokstäver, siffror, streck
                re.compile(r'^INV[-_]?[0-9]{4,}$', re.IGNORECASE),  # INV-format
                re.compile(r'^FAKT[-_]?[0-9]{4,}$', re.IGNORECASE),  # FAKT-format
            ],
            FieldType.DATE: [
                re.compile(r'^\d{4}[-/]\d{2}[-/]\d{2}$'),  # YYYY-MM-DD eller YYYY/MM/DD
                re.compile(r'^\d{2}[-/.]\d{2}[-/.]\d{4}$'),  # DD-MM-YYYY eller DD/MM/YYYY eller DD.MM.YYYY
                re.compile(r'^\d{2}[-/.]\d{2}[-/.]\d{2}$'),  # DD-MM-YY
                re.compile(r'^\d{1,2}\s+(januari|februari|mars|april|maj|juni|juli|augusti|september|oktober|november|december)\s+\d{4}$', re.IGNORECASE),  # Svensk datumformat
            ],
            FieldType.AMOUNT: [
                re.compile(r'^\d{1,3}(?:\s?\d{3})*(?:[,.]\d{2})?\s*(?:SEK|EUR|USD|kr|€|\$)?$', re.IGNORECASE),  # Belopp med valutasymboler
                re.compile(r'^\d{1,3}(?:\s?\d{3})*(?:[,.]\d{2})?$'),  # Belopp utan valutasymboler
            ],
            FieldType.VAT_NUMBER: [
                re.compile(r'^SE\d{12}$', re.IGNORECASE),  # SE123456789001
                re.compile(r'^SE[- ]?\d{12}$', re.IGNORECASE),  # SE-format med streck
            ],
            FieldType.EMAIL: [
                re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),  # Standard e-post
            ],
            FieldType.PHONE: [
                re.compile(r'^\+?[\d\s\-()]{8,}$'),  # Telefonnummer med olika format
                re.compile(r'^0\d{1,3}[- ]?\d{2,4}[- ]?\d{2,4}[- ]?\d{2,4}$'),  # Svenska telefonnummer
            ],
            FieldType.ORDER_NUMBER: [
                re.compile(r'^[Oo]RD[-_]?[0-9]{4,}$', re.IGNORECASE),  # ORD-format
                re.compile(r'^[Oo]RDER[-_]?[0-9]{4,}$', re.IGNORECASE),  # ORDER-format
            ],
            FieldType.PROJECT_NUMBER: [
                re.compile(r'^[Pp]ROJ[-_]?[0-9]{4,}$', re.IGNORECASE),  # PROJ-format
                re.compile(r'^[Pp]ROJECT[-_]?[0-9]{4,}$', re.IGNORECASE),  # PROJECT-format
            ],
        }
        
        # Nyckelord för kontextbaserad identifiering
        self.keywords = {
            FieldType.INVOICE_NUMBER: [
                "fakturanummer", "invoice number", "invoice no", "faktura nr",
                "invoice", "faktura", "invoice#", "faktura#"
            ],
            FieldType.DATE: [
                "datum", "date", "faktureringsdatum", "invoice date", "betaldatum",
                "due date", "förfallodatum", "datum:", "date:"
            ],
            FieldType.AMOUNT: [
                "belopp", "amount", "pris", "price", "summa", "sum",
                "belopp:", "amount:", "kr", "sek"
            ],
            FieldType.TOTAL_AMOUNT: [
                "total", "totalt", "total:", "totalt:", "summa", "total amount",
                "totalt belopp", "totalsumma", "total sum"
            ],
            FieldType.VAT_NUMBER: [
                "momsnummer", "vat number", "vat no", "organisationsnummer",
                "org nr", "vat", "moms", "momsnr"
            ],
            FieldType.COMPANY_NAME: [
                "företag", "company", "leverantör", "supplier", "kund", "customer",
                "fakturerad till", "billed to", "från", "from"
            ],
            FieldType.ADDRESS: [
                "adress", "address", "gata", "street", "postnummer", "zip code",
                "post code", "stad", "city", "land", "country"
            ],
            FieldType.EMAIL: [
                "e-post", "email", "e-mail", "mail", "epost"
            ],
            FieldType.PHONE: [
                "telefon", "phone", "tel", "telefonnummer", "phone number",
                "tfn", "tel:", "phone:"
            ],
            FieldType.ORDER_NUMBER: [
                "ordernummer", "order number", "order no", "order nr",
                "order", "order#", "ordernr"
            ],
            FieldType.PROJECT_NUMBER: [
                "projektnummer", "project number", "project no", "project nr",
                "projekt", "project", "proj", "projekt#"
            ],
        }
    
    def detect_field_type(self, text: str, context: Optional[str] = None) -> FieldDetection:
        """
        Detekterar fälttyp baserat på text och kontext.
        
        Args:
            text: Text att analysera (trimmed, cleaned)
            context: Närliggande text för kontextbaserad identifiering (optional)
        
        Returns:
            FieldDetection med fälttyp, konfidens och värde
        """
        if not text or not text.strip():
            return FieldDetection(
                field_type=FieldType.UNKNOWN,
                confidence=ConfidenceLevel.LOW,
                value=text
            )
        
        text = text.strip()
        context_lower = context.lower() if context else ""
        
        # Testa varje fälttyp
        detections = []
        
        for field_type in FieldType:
            if field_type == FieldType.UNKNOWN:
                continue
            
            # Testa regex-mönster
            pattern_match = None
            for pattern in self.patterns.get(field_type, []):
                if pattern.match(text):
                    pattern_match = pattern.pattern
                    detections.append(FieldDetection(
                        field_type=field_type,
                        confidence=ConfidenceLevel.HIGH,
                        value=text,
                        pattern_match=pattern_match
                    ))
                    break
            
            # Testa kontextbaserad identifiering (nyckelord)
            context_keywords = []
            for keyword in self.keywords.get(field_type, []):
                if keyword.lower() in context_lower:
                    context_keywords.append(keyword)
                    # Om både mönster och kontext matchar, öka konfidens
                    if pattern_match:
                        # Finns redan en detection från mönster, uppgradera konfidens
                        for det in detections:
                            if det.field_type == field_type:
                                det.context_keywords = context_keywords
                                det.confidence = ConfidenceLevel.HIGH
                    else:
                        # Ingen mönstermatchning, men kontext matchar
                        detections.append(FieldDetection(
                            field_type=field_type,
                            confidence=ConfidenceLevel.MEDIUM,
                            value=text,
                            context_keywords=context_keywords
                        ))
                    break
        
        # Specialfall: TOTAL_AMOUNT (kontrollera om text innehåller total-nyckelord och belopp)
        if any(kw.lower() in context_lower for kw in self.keywords[FieldType.TOTAL_AMOUNT]):
            amount_patterns = self.patterns[FieldType.AMOUNT]
            for pattern in amount_patterns:
                if pattern.match(text):
                    detections.append(FieldDetection(
                        field_type=FieldType.TOTAL_AMOUNT,
                        confidence=ConfidenceLevel.HIGH,
                        value=text,
                        pattern_match=pattern.pattern,
                        context_keywords=[kw for kw in self.keywords[FieldType.TOTAL_AMOUNT] if kw.lower() in context_lower]
                    ))
                    break
        
        # Välj bästa detektionen (högsta konfidens, eller första om ingen matchar)
        if not detections:
            return FieldDetection(
                field_type=FieldType.UNKNOWN,
                confidence=ConfidenceLevel.LOW,
                value=text
            )
        
        # Sortera efter konfidens (HIGH > MEDIUM > LOW)
        confidence_order = {ConfidenceLevel.HIGH: 3, ConfidenceLevel.MEDIUM: 2, ConfidenceLevel.LOW: 1}
        detections.sort(key=lambda d: confidence_order[d.confidence], reverse=True)
        
        return detections[0]
    
    def detect_fields_in_text(self, text: str) -> List[FieldDetection]:
        """
        Detekterar alla fält i en text genom att analysera varje rad/ord.
        
        Args:
            text: Text att analysera
        
        Returns:
            Lista med FieldDetection för varje identifierat fält
        """
        if not text:
            return []
        
        lines = text.split('\n')
        detections = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Försök identifiera nyckelord och värde på samma rad
            # Format: "Fakturanummer: INV-12345" eller "Datum: 2024-01-16"
            parts = re.split(r':|;|,', line, maxsplit=1)
            if len(parts) == 2:
                keyword_part = parts[0].strip()
                value_part = parts[1].strip()
                
                detection = self.detect_field_type(value_part, context=keyword_part)
                if detection.field_type != FieldType.UNKNOWN:
                    detections.append(detection)
            else:
                # Ingen separator, testa hela raden
                detection = self.detect_field_type(line)
                if detection.field_type != FieldType.UNKNOWN:
                    detections.append(detection)
        
        return detections
    
    def suggest_field_name(self, field_type: FieldType) -> str:
        """
        Föreslår ett fältnamn baserat på fälttyp.
        
        Args:
            field_type: Fälttyp att föreslå namn för
        
        Returns:
            Föreslaget fältnamn
        """
        suggestions = {
            FieldType.INVOICE_NUMBER: "Fakturanummer",
            FieldType.DATE: "Datum",
            FieldType.AMOUNT: "Belopp",
            FieldType.TOTAL_AMOUNT: "Totalt",
            FieldType.VAT_NUMBER: "Momsnummer",
            FieldType.COMPANY_NAME: "Företagsnamn",
            FieldType.ADDRESS: "Adress",
            FieldType.EMAIL: "E-post",
            FieldType.PHONE: "Telefon",
            FieldType.ORDER_NUMBER: "Ordernummer",
            FieldType.PROJECT_NUMBER: "Projektnummer",
            FieldType.UNKNOWN: "Okänt fält"
        }
        
        return suggestions.get(field_type, "Okänt fält")
