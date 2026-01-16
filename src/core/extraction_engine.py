"""
Extraction Engine - Extraherar data från PDF:er baserat på mallar.
"""

import re
from typing import Dict, List, Optional, Tuple
from .template_manager import Template, FieldMapping, TableMapping
from .pdf_processor import PDFProcessor
from .document_manager import PDFDocument
from .logger import get_logger

logger = get_logger()


class ExtractionEngine:
    """Motor för extraktion av data från PDF:er."""
    
    def __init__(self, pdf_processor: PDFProcessor):
        self.pdf_processor = pdf_processor
    
    def extract_data(
        self,
        pdf_path: str,
        template: Template
    ) -> Dict:
        """
        Extraherar data från en PDF baserat på en mall.
        
        Returns:
            Dictionary med extraherad data
        """
        # Extrahera text
        text = self.pdf_processor.extract_text(pdf_path)
        lines = text.split('\n')
        
        # Extrahera fält
        extracted_fields = {}
        for field_mapping in template.field_mappings:
            value = self._extract_field_value(
                text, lines, field_mapping, pdf_path
            )
            if value is not None:
                extracted_fields[field_mapping.field_name] = value
        
        # Extrahera tabeller
        extracted_tables = {}
        for table_mapping in template.table_mappings:
            table_data = self._extract_table(
                text, lines, table_mapping, pdf_path
            )
            if table_data:
                extracted_tables[table_mapping.table_name] = table_data
        
        return {
            "fields": extracted_fields,
            "tables": extracted_tables,
            "raw_text": text
        }
    
    def _extract_field_value(
        self,
        text: str,
        lines: List[str],
        field_mapping: FieldMapping,
        pdf_path: str
    ) -> Optional[str]:
        """Extraherar ett fältvärde."""
        if field_mapping.field_type == "value_header":
            return self._extract_value_header_field(
                text, lines, field_mapping
            )
        return None
    
    def _extract_value_header_field(
        self,
        text: str,
        lines: List[str],
        field_mapping: FieldMapping
    ) -> Optional[str]:
        """Extraherar ett värde-rubrik-fält."""
        # Metod 1: Använd header_text om tillgängligt
        if field_mapping.header_text:
            pattern = re.escape(field_mapping.header_text) + r'\s*[:]?\s*(.+?)(?:\n|$)'
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()
        
        # Metod 2: Använd koordinater om tillgängliga
        if field_mapping.value_coords:
            # För nu, returnera None - koordinatbaserad extraktion
            # kräver mer komplex implementation med PDF-koordinater
            pass
        
        # Metod 3: Proximity search - hitta värde nära rubriken
        if field_mapping.header_text:
            # Sök efter rubriken och hitta närmaste värde
            for i, line in enumerate(lines):
                if field_mapping.header_text.lower() in line.lower():
                    # Kolla nästa rader för värde
                    for j in range(i, min(i+3, len(lines))):
                        value_line = lines[j]
                        # Ta bort rubriken och få värdet
                        value = value_line.replace(
                            field_mapping.header_text, ""
                        ).strip(": ").strip()
                        if value and value != line:
                            return value
        
        return None
    
    def _extract_table(
        self,
        text: str,
        lines: List[str],
        table_mapping: TableMapping,
        pdf_path: str
    ) -> List[Dict]:
        """Extraherar tabelldata."""
        table_data = []
        
        # Hitta tabellområdet i texten
        # Detta är en förenklad implementation
        # En fullständig implementation skulle använda koordinater
        
        # För nu, extrahera rader baserat på kolumnmappningar
        start_line = 0
        if table_mapping.has_header_row:
            start_line = 1
        
        # Identifiera tabellrader (rader med flera kolumner)
        table_lines = []
        for line in lines:
            # Kontrollera om raden ser ut som en tabellrad
            parts = re.split(r'\s{2,}|\t', line.strip())
            if len(parts) >= len(table_mapping.columns):
                table_lines.append(parts)
        
        # Mappa kolumner
        for row_parts in table_lines[start_line:]:
            row_data = {}
            for col_mapping in table_mapping.columns:
                col_index = col_mapping.get("index", 0)
                col_name = col_mapping.get("name", "")
                if col_index < len(row_parts):
                    row_data[col_name] = row_parts[col_index].strip()
                else:
                    row_data[col_name] = ""
            
            # Lägg till rad om den inte är tom
            if any(row_data.values()):
                table_data.append(row_data)
        
        return table_data
