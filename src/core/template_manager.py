"""
Template Manager - Hanterar mappningsmallar.
"""

import json
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass, field, asdict
from .logger import get_logger

logger = get_logger()


@dataclass
class FieldMapping:
    """Representerar en fältmappning."""
    field_name: str
    field_type: str  # "value_header" eller "table"
    value_coords: Optional[Dict] = None  # {"x": 0.1, "y": 0.2, "width": 0.1, "height": 0.05}
    header_coords: Optional[Dict] = None
    header_text: Optional[str] = None
    is_recurring: bool = False  # Återkommande eller unikt värde
    column_index: Optional[int] = None  # För tabeller
    table_coords: Optional[Dict] = None  # För tabeller


@dataclass
class TableMapping:
    """Representerar en tabellmappning."""
    table_name: str
    table_coords: Dict  # {"x": 0.1, "y": 0.3, "width": 0.8, "height": 0.5}
    columns: List[Dict]  # [{"name": "Art.nr", "index": 0, "coords": {"x": 0.1, "y": 0.3, "width": 0.15, "height": 0.5}}, ...]
    has_header_row: bool = True
    row_coords: Optional[List[Dict]] = None  # [{"y": 0.3, "height": 0.05, "index": 0}, ...]
    header_row_coords: Optional[Dict] = None  # {"y": 0.3, "height": 0.05}


@dataclass
class Template:
    """Representerar en komplett mappningsmall."""
    cluster_id: str
    reference_file: str
    field_mappings: List[FieldMapping] = field(default_factory=list)
    table_mappings: List[TableMapping] = field(default_factory=list)
    ocr_language: str = "swe+eng"  # Tesseract language code (default: svenska + engelska)
    
    def to_dict(self) -> Dict:
        """Konverterar till dictionary."""
        return {
            "cluster_id": self.cluster_id,
            "reference_file": self.reference_file,
            "ocr_language": self.ocr_language,
            "field_mappings": [
                asdict(fm) for fm in self.field_mappings
            ],
            "table_mappings": [
                {
                    "table_name": tm.table_name,
                    "table_coords": tm.table_coords,
                    "columns": tm.columns,
                    "has_header_row": tm.has_header_row,
                    "row_coords": tm.row_coords,
                    "header_row_coords": tm.header_row_coords
                }
                for tm in self.table_mappings
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Template':
        """Skapar från dictionary."""
        field_mappings = [
            FieldMapping(**fm) for fm in data.get("field_mappings", [])
        ]
        table_mappings = [
            TableMapping(
                table_name=tm["table_name"],
                table_coords=tm["table_coords"],
                columns=tm["columns"],
                has_header_row=tm.get("has_header_row", True),
                row_coords=tm.get("row_coords"),
                header_row_coords=tm.get("header_row_coords")
            )
            for tm in data.get("table_mappings", [])
        ]
        
        return cls(
            cluster_id=data["cluster_id"],
            reference_file=data["reference_file"],
            ocr_language=data.get("ocr_language", "swe+eng"),  # Bakåtkompatibilitet: default till swe+eng
            field_mappings=field_mappings,
            table_mappings=table_mappings
        )


class TemplateManager:
    """Hanterar mappningsmallar."""
    
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(exist_ok=True)
        
        self.templates: Dict[str, Template] = {}
        self._load_templates()
    
    def create_template(self, cluster_id: str, reference_file: str) -> Template:
        """Skapar en ny mall."""
        template = Template(
            cluster_id=cluster_id,
            reference_file=reference_file
        )
        self.templates[cluster_id] = template
        return template
    
    def get_template(self, cluster_id: str) -> Optional[Template]:
        """Hämtar en mall."""
        return self.templates.get(cluster_id)
    
    def save_template(self, template: Template):
        """Sparar en mall."""
        self.templates[template.cluster_id] = template
        self._save_template_to_file(template)
    
    def save_all_templates(self):
        """Sparar alla mallar."""
        for template in self.templates.values():
            self._save_template_to_file(template)
    
    def _save_template_to_file(self, template: Template):
        """Sparar en mall till fil."""
        template_file = self.templates_dir / f"{template.cluster_id}.json"
        with open(template_file, "w", encoding="utf-8") as f:
            json.dump(template.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _load_templates(self):
        """Laddar alla mallar från disk."""
        for template_file in self.templates_dir.glob("*.json"):
            try:
                with open(template_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                template = Template.from_dict(data)
                self.templates[template.cluster_id] = template
            except Exception as e:
                logger.error(f"Fel vid laddning av mall {template_file}: {e}", exc_info=True)
    
    def delete_template(self, cluster_id: str):
        """Raderar en mall."""
        if cluster_id in self.templates:
            del self.templates[cluster_id]
            template_file = self.templates_dir / f"{cluster_id}.json"
            if template_file.exists():
                template_file.unlink()
