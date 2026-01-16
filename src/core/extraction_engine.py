"""
Extraction Engine - Extraherar data från PDF:er baserat på mallar.
"""

import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from .template_manager import Template, FieldMapping, TableMapping
from .pdf_processor import PDFProcessor
from .document_manager import PDFDocument
from .text_extractor import TextExtractor
from .logger import get_logger, log_error_with_context
from .exceptions import ExtractionError, CoordinateError, TemplateError

logger = get_logger()


class ExtractionEngine:
    """Motor för extraktion av data från PDF:er."""
    
    def __init__(self, pdf_processor: PDFProcessor):
        self.pdf_processor = pdf_processor
        self.text_extractor = TextExtractor(pdf_processor)
    
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
        
        # Extrahera text med språk från template (om tillgängligt)
        ocr_language = getattr(template, 'ocr_language', 'swe+eng')
        try:
            text = self.pdf_processor.extract_text(pdf_path, use_ocr=False)
            lines = text.split('\n')
            
            # Om ingen text hittades, använd OCR med template-språk
            if not text.strip():
                text = self.pdf_processor.extract_text(pdf_path, use_ocr=True, language=ocr_language)
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
        
        # Ytterligare validering av tabellstruktur
        validation_warnings = self._validate_table_mapping(text, lines, table_mapping, pdf_path)
        if validation_warnings:
            for warning in validation_warnings:
                logger.warning(f"Tabellvalidering - {warning}")
        
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
            # Hämta PDF-dimensioner för koordinatbaserad extraktion
            pdf_dimensions = self.pdf_processor.get_pdf_dimensions(pdf_path)
            if not pdf_dimensions:
                logger.warning(f"Kunde inte hämta PDF-dimensioner för {pdf_path}")
                pdf_dimensions = (612.0, 792.0)  # Default A4-storlek
            
            pdf_width, pdf_height = pdf_dimensions
            
            # Använd språk från template om tillgängligt
            ocr_language = "swe+eng"  # Default
            
            # Kontrollera om vi har koordinatbaserad mappning
            has_column_coords = any(
                col_mapping.get("coords") for col_mapping in table_mapping.columns
            )
            has_row_coords = table_mapping.row_coords is not None and len(table_mapping.row_coords) > 0
            
            if has_column_coords and has_row_coords:
                # Koordinatbaserad extraktion
                return self._extract_table_with_coordinates(
                    pdf_path, table_mapping, pdf_width, pdf_height, ocr_language
                )
            else:
                # Fallback till textbaserad extraktion
                return self._extract_table_from_text(lines, table_mapping)
            
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
    
    def _extract_table_with_coordinates(
        self,
        pdf_path: str,
        table_mapping: TableMapping,
        pdf_width: float,
        pdf_height: float,
        language: str
    ) -> List[Dict]:
        """
        Extraherar tabelldata med koordinatbaserad cell-extraktion.
        
        Args:
            pdf_path: Sökväg till PDF
            table_mapping: Tabellmappning med kolumn- och radkoordinater
            pdf_width: PDF-bredd i points
            pdf_height: PDF-höjd i points
            language: OCR-språk
        
        Returns:
            Lista med dictionaries med tabelldata
        """
        table_data = []
        
        # Sortera kolumner efter index
        sorted_columns = sorted(
            table_mapping.columns,
            key=lambda c: c.get("index", 0)
        )
        
        # Sortera rader efter index
        sorted_rows = []
        if table_mapping.row_coords:
            sorted_rows = sorted(
                table_mapping.row_coords,
                key=lambda r: r.get("y", 0)
            )
        
        # Om inga rader är mappade, försök skapa rader från header
        if not sorted_rows and table_mapping.header_row_coords:
            # Anta samma radhöjd som header och skapa rader nedåt
            header_coords = table_mapping.header_row_coords
            header_y = header_coords.get("y", 0)
            header_height = header_coords.get("height", 0.05)
            table_top = table_mapping.table_coords.get("y", 0)
            table_bottom = table_top + table_mapping.table_coords.get("height", 0)
            
            # Skapa rader med samma höjd som header
            current_y = header_y + header_height
            row_index = 0
            while current_y < table_bottom:
                sorted_rows.append({
                    "y": current_y,
                    "height": header_height,
                    "index": row_index
                })
                current_y += header_height
                row_index += 1
        
        # Extrahera data från varje cell
        for row_info in sorted_rows:
            row_y = row_info.get("y", 0)
            row_height = row_info.get("height", 0.05)
            
            row_data = {}
            for col_mapping in sorted_columns:
                col_name = col_mapping.get("name", "")
                col_coords = col_mapping.get("coords")
                
                if col_coords:
                    # Beräkna cellkoordinater
                    cell_coords = {
                        "x": col_coords.get("x", 0),
                        "y": row_y,
                        "width": col_coords.get("width", 0),
                        "height": row_height
                    }
                    
                    # Extrahera text från cell
                    cell_text = self.text_extractor.extract_table_cell(
                        pdf_path,
                        0,
                        cell_coords,
                        pdf_width,
                        pdf_height,
                        language
                    )
                    
                    row_data[col_name] = cell_text.strip()
                else:
                    row_data[col_name] = ""
            
            # Lägg till rad om den inte är helt tom
            if any(row_data.values()):
                table_data.append(row_data)
        
        return table_data
    
    def _extract_table_from_text(
        self,
        lines: List[str],
        table_mapping: TableMapping
    ) -> List[Dict]:
        """
        Extraherar tabelldata från text (fallback-metod).
        
        Args:
            lines: Text raderad i linjer
            table_mapping: Tabellmappning
        
        Returns:
            Lista med dictionaries med tabelldata
        """
        table_data = []
        
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
    
    def _match_column(
        self,
        col_coords: Dict,
        available_columns: List[Dict],
        tolerance: float = 0.05
    ) -> Optional[int]:
        """
        Matchar en kolumnkoordinat mot tillgängliga kolumner.
        
        Args:
            col_coords: Kolumnkoordinater att matcha
            available_columns: Lista med tillgängliga kolumnkoordinater
            tolerance: Tolerans för matchning (normaliserad)
        
        Returns:
            Index för matchad kolumn eller None
        """
        col_x = col_coords.get("x", 0)
        col_width = col_coords.get("width", 0)
        col_center = col_x + col_width / 2
        
        best_match = None
        best_distance = float('inf')
        
        for idx, available_col in enumerate(available_columns):
            avail_coords = available_col.get("coords", {})
            avail_x = avail_coords.get("x", 0)
            avail_width = avail_coords.get("width", 0)
            avail_center = avail_x + avail_width / 2
            
            distance = abs(col_center - avail_center)
            if distance < tolerance and distance < best_distance:
                best_match = idx
                best_distance = distance
        
        return best_match
            
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
    
    def _validate_table_mapping(
        self,
        text: str,
        lines: List[str],
        table_mapping: TableMapping,
        pdf_path: str
    ) -> List[str]:
        """
        Validerar tabellmappning och returnerar varningar.
        
        Args:
            text: Extraherad text från PDF
            lines: Text raderad i linjer
            table_mapping: Tabellmappning att validera
            pdf_path: Sökväg till PDF-fil (för logging)
        
        Returns:
            Lista med varningsmeddelanden (tom lista om inga varningar)
        """
        warnings = []
        
        if not table_mapping or not table_mapping.columns:
            return warnings
        
        # Validering 1: Kontrollera att alla kolumnindices är rimliga
        max_expected_cols = max(col_mapping.get("index", 0) + 1 for col_mapping in table_mapping.columns)
        
        # Validering 2: Kontrollera tabellstruktur (samma antal kolumner per rad)
        table_lines = []
        for line in lines:
            parts = re.split(r'\s{2,}|\t', line.strip())
            if len(parts) >= len(table_mapping.columns):
                table_lines.append(parts)
        
        if table_lines:
            col_counts = [len(parts) for parts in table_lines]
            unique_counts = set(col_counts)
            if len(unique_counts) > 1:
                warnings.append(
                    f"Tabellen har inkonsekvent struktur: olika antal kolumner per rad "
                    f"({min(unique_counts)}-{max(unique_counts)} kolumner)."
                )
            
            # Kontrollera att kolumnindices inte är utanför tabellstrukturen
            max_actual_cols = max(col_counts) if col_counts else 0
            for col_mapping in table_mapping.columns:
                col_index = col_mapping.get("index", 0)
                if col_index >= max_actual_cols:
                    warnings.append(
                        f"Kolumn '{col_mapping.get('name')}' har index {col_index} "
                        f"men tabellen har endast {max_actual_cols} kolumner."
                    )
        
        # Validering 3: Kontrollera att header-rad finns om den förväntas
        if table_mapping.has_header_row and not table_lines:
            warnings.append("Header-rad förväntas men inga tabellrader hittades.")
        
        # Validering 4: Kontrollera att kolumner inte är för nära varandra
        col_indices = sorted([cm.get("index", 0) for cm in table_mapping.columns])
        for i in range(len(col_indices) - 1):
            if col_indices[i+1] - col_indices[i] == 1:
                warnings.append(
                    f"Kolumner med index {col_indices[i]} och {col_indices[i+1]} är intill varandra. "
                    "Kontrollera att kolumner är korrekt separerade."
                )
        
        return warnings