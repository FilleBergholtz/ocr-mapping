"""
Extraction Engine - Extraherar data från PDF:er baserat på mallar.
"""

import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from .template_manager import Template, FieldMapping, TableMapping
from .pdf_processor import PDFProcessor
from .document_manager import PDFDocument
from .logger import get_logger, log_error_with_context
from .exceptions import ExtractionError, CoordinateError, TemplateError

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
        
        Args:
            pdf_path: Sökväg till PDF-fil
            template: Mappningsmall
        
        Returns:
            Dictionary med extraherad data {"fields": {...}, "tables": {...}, "raw_text": "..."}
        
        Raises:
            ExtractionError: Om extraktion misslyckas helt
            TemplateError: Om mall är ogiltig
        """
        # Validera att filen existerar
        if not Path(pdf_path).exists():
            error_msg = f"PDF-fil existerar inte: {pdf_path}"
            logger.error(error_msg)
            raise ExtractionError(
                error_msg,
                pdf_path=pdf_path,
                user_message=f"Kunde inte hitta PDF-fil: '{pdf_path}'.\n\nKontrollera att filen existerar."
            )
        
        # Validera template
        if not template:
            error_msg = "Template är None"
            logger.error(error_msg)
            raise TemplateError(
                error_msg,
                user_message="Ingen mappningsmall angiven.\n\nLadda eller skapa en mappningsmall först."
            )
        
        if not template.field_mappings and not template.table_mappings:
            logger.warning(f"Template är tom för kluster: {template.cluster_id}")
            # Returnera tom resultat istället för att krascha
            return {
                "fields": {},
                "tables": {},
                "raw_text": ""
            }
        
        # Extrahera text
        try:
            text = self.pdf_processor.extract_text(pdf_path)
            lines = text.split('\n')
        except Exception as e:
            log_error_with_context(
                logger, e,
                {"file_path": pdf_path, "cluster_id": template.cluster_id},
                "Fel vid textextraktion i ExtractionEngine"
            )
            raise ExtractionError(
                f"Kunde inte extrahera text från PDF: {str(e)}",
                pdf_path=pdf_path,
                user_message=f"Kunde inte extrahera text från PDF: '{pdf_path}'.\n\nLoggar innehåller mer information."
            ) from e
        
        # Extrahera fält (returnera partiella resultat om några fält misslyckas)
        extracted_fields = {}
        failed_fields = []
        
        for field_mapping in template.field_mappings:
            try:
                value = self._extract_field_value(
                    text, lines, field_mapping, pdf_path
                )
                if value is not None:
                    extracted_fields[field_mapping.field_name] = value
            except Exception as e:
                failed_fields.append(field_mapping.field_name)
                log_error_with_context(
                    logger, e,
                    {
                        "field_name": field_mapping.field_name,
                        "file_path": pdf_path,
                        "field_type": field_mapping.field_type
                    },
                    f"Fel vid extraktion av fält '{field_mapping.field_name}'"
                )
                # Fortsätt med nästa fält även om ett fält misslyckas
        
        # Logga misslyckade fält om några
        if failed_fields:
            logger.warning(f"Följande fält misslyckades vid extraktion: {', '.join(failed_fields)}")
        
        # Extrahera tabeller (returnera partiella resultat om några tabeller misslyckas)
        extracted_tables = {}
        failed_tables = []
        
        for table_mapping in template.table_mappings:
            try:
                table_data = self._extract_table(
                    text, lines, table_mapping, pdf_path
                )
                if table_data:
                    extracted_tables[table_mapping.table_name] = table_data
            except Exception as e:
                failed_tables.append(table_mapping.table_name)
                log_error_with_context(
                    logger, e,
                    {
                        "table_name": table_mapping.table_name,
                        "file_path": pdf_path
                    },
                    f"Fel vid extraktion av tabell '{table_mapping.table_name}'"
                )
                # Fortsätt med nästa tabell även om en tabell misslyckas
        
        # Logga misslyckade tabeller om några
        if failed_tables:
            logger.warning(f"Följande tabeller misslyckades vid extraktion: {', '.join(failed_tables)}")
        
        # Om alla extraktioner misslyckade, raise exception
        if not extracted_fields and not extracted_tables:
            error_msg = "Inga fält eller tabeller kunde extraheras från PDF"
            if failed_fields:
                error_msg += f". Misslyckade fält: {', '.join(failed_fields)}"
            if failed_tables:
                error_msg += f". Misslyckade tabeller: {', '.join(failed_tables)}"
            
            raise ExtractionError(
                error_msg,
                pdf_path=pdf_path,
                user_message="Extraktion misslyckades helt.\n\nKontrollera att mappningsmallen matchar PDF:ens struktur.\n\nLoggar innehåller mer information."
            )
        
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
        """
        Extraherar ett fältvärde.
        
        Args:
            text: Extraherad text från PDF
            lines: Text raderad i linjer
            field_mapping: Fältmappning att använda
            pdf_path: Sökväg till PDF-fil (för logging)
        
        Returns:
            Extraherat värde eller None om inte hittat
        
        Raises:
            CoordinateError: Om koordinater saknas eller är ogiltiga
        """
        # Validera att field_mapping har nödvändig information
        if not field_mapping:
            logger.warning("Field mapping är None")
            return None
        
        # Validera koordinater om de krävs
        if field_mapping.field_type == "value_header":
            if not field_mapping.value_coords and not field_mapping.header_text:
                logger.warning(
                    f"Field mapping '{field_mapping.field_name}' saknar både koordinater och header_text"
                )
                return None
            
            # Validera koordinater om de finns
            if field_mapping.value_coords:
                coords = field_mapping.value_coords
                if not all(key in coords for key in ["x", "y", "width", "height"]):
                    log_error_with_context(
                        logger, None,
                        {
                            "field_name": field_mapping.field_name,
                            "coords": coords
                        },
                        "Ogiltiga koordinater i field mapping"
                    )
                    raise CoordinateError(
                        f"Ogiltiga koordinater för fält '{field_mapping.field_name}': {coords}",
                        coords=coords,
                        pdf_path=pdf_path
                    )
        
        try:
            if field_mapping.field_type == "value_header":
                return self._extract_value_header_field(
                    text, lines, field_mapping
                )
            else:
                logger.warning(f"Okänd field_type: {field_mapping.field_type}")
                return None
        except CoordinateError:
            # Propagera CoordinateError
            raise
        except Exception as e:
            log_error_with_context(
                logger, e,
                {
                    "field_name": field_mapping.field_name,
                    "field_type": field_mapping.field_type,
                    "pdf_path": pdf_path
                },
                f"Oväntat fel vid extraktion av fältvärde"
            )
            # Returnera None istället för att krascha - partial results
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
        """
        Extraherar tabelldata.
        
        Args:
            text: Extraherad text från PDF
            lines: Text raderad i linjer
            table_mapping: Tabellmappning att använda
            pdf_path: Sökväg till PDF-fil (för logging)
        
        Returns:
            Lista med dictionaries med tabelldata (en dict per rad)
        
        Raises:
            CoordinateError: Om koordinater saknas eller är ogiltiga
        """
        # Validera table_mapping
        if not table_mapping:
            logger.warning("Table mapping är None")
            return []
        
        if not table_mapping.columns:
            logger.warning(f"Table mapping '{table_mapping.table_name}' saknar kolumner")
            return []
        
        # Validera koordinater om de finns
        if table_mapping.table_coords:
            coords = table_mapping.table_coords
            if not all(key in coords for key in ["x", "y", "width", "height"]):
                log_error_with_context(
                    logger, None,
                    {
                        "table_name": table_mapping.table_name,
                        "coords": coords
                    },
                    "Ogiltiga koordinater i table mapping"
                )
                raise CoordinateError(
                    f"Ogiltiga koordinater för tabell '{table_mapping.table_name}': {coords}",
                    coords=coords,
                    pdf_path=pdf_path
                )
        
        table_data = []
        
        try:
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
            
        except CoordinateError:
            # Propagera CoordinateError
            raise
        except Exception as e:
            log_error_with_context(
                logger, e,
                {
                    "table_name": table_mapping.table_name,
                    "pdf_path": pdf_path,
                    "columns": len(table_mapping.columns)
                },
                f"Oväntat fel vid extraktion av tabell"
            )
            # Returnera tom lista istället för att krascha - partial results
            return []
