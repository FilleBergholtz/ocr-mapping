"""
Mapping Tab - Hanterar mappning av fält och tabeller på PDF:er.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QDialog, QLineEdit, QComboBox, QCheckBox,
    QMessageBox, QGroupBox, QScrollArea, QFrame, QTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QSlider
)
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QImage, QWheelEvent
from PIL import Image
import io
from typing import Optional, Dict, List, Tuple
from ..core.document_manager import DocumentManager, PDFDocument
from ..core.template_manager import TemplateManager, Template, FieldMapping, TableMapping
from ..core.pdf_processor import PDFProcessor
from ..core.extraction_engine import ExtractionEngine
from ..core.text_extractor import TextExtractor
from ..core.logger import get_logger, log_error_with_context
from .table_mapping_dialog import TableMappingDialog


class ValueHeaderMappingDialog(QDialog):
    """Dialog för mappning av värde-rubrik-fält."""
    
    def __init__(self, parent=None, extracted_value: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Mappa Fält")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        # Visa extraherad text
        layout.addWidget(QLabel("<b>Extraherad text från markerat område:</b>"))
        self.value_display = QTextEdit()
        self.value_display.setReadOnly(True)
        self.value_display.setMaximumHeight(100)
        self.value_display.setPlainText(extracted_value if extracted_value else "(Ingen text hittades)")
        layout.addWidget(self.value_display)
        
        layout.addWidget(QLabel("Rubrik (som står nära värdet):"))
        self.header_input = QLineEdit()
        layout.addWidget(self.header_input)
        
        layout.addWidget(QLabel("Typ:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Unikt (varierar per PDF)", "Återkommande (samma för alla)"])
        layout.addWidget(self.type_combo)
        
        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Avbryt")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
    
    def get_result(self) -> tuple:
        """Returnerar (header_text, is_recurring)."""
        return (
            self.header_input.text(),
            self.type_combo.currentIndex() == 1
        )


class PDFViewer(QFrame):
    """Widget för visning och mappning av PDF."""
    
    value_selected = Signal(QRect)  # Emitteras när användaren markerar ett värde
    table_selected = Signal(QRect)  # Emitteras när användaren markerar en tabell
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 800)
        self.setStyleSheet("background-color: white; border: 1px solid gray;")
        
        self.pdf_image: Optional[QPixmap] = None
        self.original_image: Optional[QPixmap] = None  # Originalbild för zoom
        self.scale_factor = 1.0
        self.min_scale = 0.1
        self.max_scale = 5.0
        self.selection_rect: Optional[QRect] = None
        self.selection_mode = None  # "value" eller "table"
        self.pan_start_pos: Optional[QPoint] = None
        self.pan_offset = QPoint(0, 0)
        self.is_panning = False
        
        # Mappade områden att visa
        self.field_mappings: List[Dict] = []  # [{"name": "...", "coords": {...}, "value": "..."}]
        self.table_mappings: List[Dict] = []  # [{"name": "...", "coords": {...}}]
        
        self.setMouseTracking(True)
    
    def set_pdf_image(self, pixmap: QPixmap):
        """
        Sätter PDF-bilden och initialiserar zoom/panning.
        
        Vid initial laddning sätts zoom till fit-to-widget (visa hela PDF:en).
        Panning återställs till centrerad position.
        
        Args:
            pixmap: QPixmap med PDF-bilddata
        """
        self.pdf_image = pixmap
        self.original_image = pixmap
        
        # Initial scaling: visa hela PDF:en (fit-to-widget)
        # Beräkna scale_factor för att bilden ska passa i widget med lite marginal (0.9)
        if pixmap:
            # Beräkna scale som passar både i bredd och höjd
            scale_to_fit = min(
                self.width() / pixmap.width(),
                self.height() / pixmap.height()
            ) * 0.9  # 0.9 ger 10% marginal
            
            # Begränsa till min_scale och max_scale
            self.scale_factor = max(self.min_scale, min(self.max_scale, scale_to_fit))
            
            # Återställ panning till centrerad position
            self.pan_offset = QPoint(0, 0)
        
        # Trigga omritning
        self.update()
    
    def set_selection_mode(self, mode: Optional[str]):
        """Sätter läge för markering (None, 'value', 'table')."""
        self.selection_mode = mode
        self.selection_rect = None
    
    def set_mappings(self, field_mappings: List[Dict] = None, table_mappings: List[Dict] = None):
        """Sätter mappningar att visa på PDF:en."""
        if field_mappings is not None:
            self.field_mappings = field_mappings
        if table_mappings is not None:
            self.table_mappings = table_mappings
        self.update()
    
    def mousePressEvent(self, event):
        """Hanterar musklick."""
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier):
            # Starta panning
            self.is_panning = True
            self.pan_start_pos = event.pos()
        elif self.selection_mode and event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.selection_rect = QRect(self.start_pos, self.start_pos)
            self.update()
    
    def mouseMoveEvent(self, event):
        """
        Hanterar musrörelse för panning och markering.
        
        Panning begränsas till rimliga gränser så att bilden inte flyttas för långt
        utanför widgeten. Detta förbättrar användarupplevelsen vid navigering.
        """
        if self.is_panning and self.pan_start_pos:
            # Panning: beräkna delta och uppdatera panning-offset
            delta = event.pos() - self.pan_start_pos
            new_pan_offset = self.pan_offset + delta
            
            # Begränsa panning inom rimliga gränser
            # Beräkna max panning baserat på bildstorlek och widget-storlek
            if self.pdf_image:
                scaled_width = int(self.pdf_image.width() * self.scale_factor)
                scaled_height = int(self.pdf_image.height() * self.scale_factor)
                
                # Beräkna max offset (halva skillnaden mellan bild och widget)
                max_x_offset = max(0, (scaled_width - self.width()) / 2)
                max_y_offset = max(0, (scaled_height - self.height()) / 2)
                
                # Begränsa till max offset (eller 0 om bild är mindre än widget)
                new_pan_offset.setX(max(-max_x_offset, min(max_x_offset, new_pan_offset.x())))
                new_pan_offset.setY(max(-max_y_offset, min(max_y_offset, new_pan_offset.y())))
            
            self.pan_offset = new_pan_offset
            self.pan_start_pos = event.pos()
            self.update()
        elif self.selection_mode and self.selection_rect is not None:
            # Markering: uppdatera selection-rektangel under dragning
            self.selection_rect = QRect(self.start_pos, event.pos()).normalized()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Hanterar musrelease."""
        if self.is_panning:
            self.is_panning = False
            self.pan_start_pos = None
        elif self.selection_mode and self.selection_rect:
            # Konvertera till normaliserade koordinater (0.0-1.0)
            normalized_rect = self._normalize_rect(self.selection_rect)
            
            if self.selection_mode == "value":
                self.value_selected.emit(normalized_rect)
            elif self.selection_mode == "table":
                self.table_selected.emit(normalized_rect)
            
            self.selection_rect = None
            self.update()
    
    def wheelEvent(self, event: QWheelEvent):
        """Hanterar scrollhjul för zoom."""
        if not self.pdf_image:
            return
        
        # Beräkna zoom-faktor
        delta = event.angleDelta().y()
        zoom_factor = 1.1 if delta > 0 else 0.9
        
        # Begränsa zoom
        new_scale = self.scale_factor * zoom_factor
        if self.min_scale <= new_scale <= self.max_scale:
            self.scale_factor = new_scale
            self.update()
    
    def _normalize_rect(self, rect: QRect) -> QRect:
        """
        Konverterar widget-koordinater till normaliserade koordinater (0.0-1.0).
        
        Denna metod är inversen till _denormalize_rect(). Den tar en rektangel i widget-koordinater
        (relativa till PDFViewer-widgeten) och konverterar den till normaliserade koordinater
        (0.0-1.0) relativa till den faktiska PDF-bildens dimensioner.
        
        Normaliserade koordinater används för att lagra mappningar oberoende av:
        - PDF-storlek (A4, A3, Letter, etc.)
        - DPI-inställningar (72, 150, 300 DPI, etc.)
        - Zoom-nivå (0.1x - 5.0x)
        - Panning-position
        
        Process:
        1. Hämta faktisk bildstorlek (pixels)
        2. Beräkna skalad bildstorlek i widget (med zoom)
        3. Beräkna offset för centrerad bild (med panning)
        4. Konvertera widget-koordinater → pixel-koordinater → normaliserade (0.0-1.0)
        5. Returnera som QRect med värden multiplicerade med 1000 för precision
        
        Args:
            rect: QRect i widget-koordinater (relativa till PDFViewer-widgeten)
        
        Returns:
            QRect med normaliserade värden (x, y, width, height alla i [0, 1000])
            Värden representerar position i faktisk PDF-bild (0.0-1.0 * 1000)
        """
        if not self.pdf_image:
            return rect
        
        # Hämta faktisk bildstorlek i pixels (inte widget-storlek)
        img_width = self.pdf_image.width()
        img_height = self.pdf_image.height()
        
        if img_width <= 0 or img_height <= 0:
            return rect
        
        # Beräkna skalad bildstorlek i widget (med zoom-factor)
        scaled_width = img_width * self.scale_factor
        scaled_height = img_height * self.scale_factor
        
        # Beräkna offset för centrerad bild (inklusive panning)
        # Bilden centreras i widget, plus eventuell panning-offset
        x_offset = max(0, (self.width() - scaled_width) / 2) + self.pan_offset.x()
        y_offset = max(0, (self.height() - scaled_height) / 2) + self.pan_offset.y()
        
        # Steg 1: Konvertera widget-koordinater till pixel-koordinater
        # Subtrahera offset (för att kompensera centrering och panning)
        # Dividera med scale_factor (för att kompensera zoom)
        adj_x = (rect.x() - x_offset) / self.scale_factor
        adj_y = (rect.y() - y_offset) / self.scale_factor
        adj_width = rect.width() / self.scale_factor
        adj_height = rect.height() / self.scale_factor
        
        # Steg 2: Säkerställ att koordinaterna är inom bildens gränser
        # Detta hanterar edge cases där markeringen går utanför bilden
        adj_x = max(0, min(img_width, adj_x))
        adj_y = max(0, min(img_height, adj_y))
        adj_width = max(0, min(img_width - adj_x, adj_width))
        adj_height = max(0, min(img_height - adj_y, adj_height))
        
        # Steg 3: Normalisera till 0.0-1.0 baserat på faktisk bildstorlek
        # Detta gör koordinaterna oberoende av PDF-storlek och DPI
        normalized_x = adj_x / img_width
        normalized_y = adj_y / img_height
        normalized_width = adj_width / img_width
        normalized_height = adj_height / img_height
        
        # Steg 4: Säkerställ att värdena är strikt inom [0, 1]
        # Extra säkerhet för floating-point precision-problem
        normalized_x = max(0.0, min(1.0, normalized_x))
        normalized_y = max(0.0, min(1.0, normalized_y))
        normalized_width = max(0.0, min(1.0 - normalized_x, normalized_width))
        normalized_height = max(0.0, min(1.0 - normalized_y, normalized_height))
        
        # Returnera som QRect med normaliserade värden (multiplicerade med 1000 för precision)
        # QRect använder integers, så vi multiplicerar med 1000 för att behålla 3 decimals precision
        return QRect(
            int(normalized_x * 1000),
            int(normalized_y * 1000),
            int(normalized_width * 1000),
            int(normalized_height * 1000)
        )
    
    def paintEvent(self, event):
        """Ritar PDF-bilden och markeringar."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if self.pdf_image:
            # Rita PDF-bilden med zoom och panning
            scaled_width = int(self.pdf_image.width() * self.scale_factor)
            scaled_height = int(self.pdf_image.height() * self.scale_factor)
            
            # Beräkna position med panning
            x_offset = (self.width() - scaled_width) / 2 + self.pan_offset.x()
            y_offset = (self.height() - scaled_height) / 2 + self.pan_offset.y()
            
            painter.drawPixmap(
                int(x_offset), int(y_offset),
                scaled_width, scaled_height,
                self.pdf_image
            )
            
            # Rita aktiva markeringar (under mappning)
            if self.selection_rect:
                # Tydlig röd färg för aktiv markering med tillräcklig kontrast
                # Använd tjocklek som anpassas för zoom (minst 2px, ökar vid zoom in)
                pen_width = max(2, int(2 * self.scale_factor))
                pen = QPen(QColor(255, 0, 0), pen_width)
                painter.setPen(pen)
                
                # Semi-transparent fyllning för visuell feedback under dragning
                brush = QColor(255, 0, 0, 30)  # Röd med låg opacity
                painter.fillRect(self.selection_rect, brush)
                painter.drawRect(self.selection_rect)
            
            # Rita mappade fältområden
            for field in self.field_mappings:
                coords = field.get("coords")
                if coords:
                    rect = self._denormalize_rect(coords)
                    if rect:
                        # Blå färg för fält med anpassad tjocklek för zoom
                        # Tjocklek anpassas för bättre synlighet vid alla zoom-nivåer
                        pen_width = max(2, int(2 * self.scale_factor))
                        pen = QPen(QColor(0, 150, 255), pen_width)
                        painter.setPen(pen)
                        painter.drawRect(rect)
                        
                        # Visa fältnamn och värde ovanför rektangeln
                        field_name = field.get("name", "")
                        field_value = field.get("value", "")
                        label_text = f"{field_name}"
                        if field_value:
                            label_text += f": {field_value[:30]}"
                        
                        # Beräkna textposition (ovanför eller inuti om nära toppen)
                        text_y = max(2, rect.y() - 18)
                        
                        # Bakgrund för text med högre opacity för bättre läsbarhet
                        # Font-size anpassas för zoom för att vara läsbar vid alla nivåer
                        text_rect = painter.boundingRect(
                            rect.x(), text_y,
                            rect.width(), 18,
                            Qt.AlignLeft,
                            label_text
                        )
                        # Förbättrad bakgrund med padding och högre opacity
                        painter.fillRect(text_rect.adjusted(-3, -2, 3, 2), QColor(255, 255, 255, 240))
                        painter.setPen(QColor(0, 0, 0))
                        painter.drawText(text_rect, label_text)
            
            # Rita mappade tabellområden
            for table in self.table_mappings:
                coords = table.get("coords")
                if coords:
                    rect = self._denormalize_rect(coords)
                    if rect:
                        # Grön färg för tabeller med anpassad tjocklek för zoom
                        # Tjocklek anpassas för bättre synlighet vid alla zoom-nivåer
                        pen_width = max(2, int(2 * self.scale_factor))
                        pen = QPen(QColor(0, 200, 0), pen_width)
                        painter.setPen(pen)
                        painter.drawRect(rect)
                        
                        # Visa tabellnamn ovanför rektangeln
                        table_name = table.get("name", "Tabell")
                        label_text = f"📊 {table_name}"
                        
                        # Beräkna textposition (ovanför eller inuti om nära toppen)
                        text_y = max(2, rect.y() - 18)
                        
                        # Bakgrund för text med högre opacity för bättre läsbarhet
                        # Font-size anpassas för zoom för att vara läsbar vid alla nivåer
                        text_rect = painter.boundingRect(
                            rect.x(), text_y,
                            rect.width(), 18,
                            Qt.AlignLeft,
                            label_text
                        )
                        # Förbättrad bakgrund med padding och högre opacity
                        painter.fillRect(text_rect.adjusted(-3, -2, 3, 2), QColor(255, 255, 255, 240))
                        painter.setPen(QColor(0, 0, 0))
                        painter.drawText(text_rect, label_text)
    
    def _denormalize_rect(self, coords: Dict) -> Optional[QRect]:
        """
        Konverterar normaliserade koordinater (0.0-1.0) till widget-koordinater.
        
        Denna metod är inversen till _normalize_rect(). Den tar normaliserade koordinater
        (0.0-1.0 relativa till faktisk PDF-bild) och konverterar dem till widget-koordinater
        (relativa till PDFViewer-widgeten) med hänsyn till aktuell zoom och panning.
        
        Process:
        1. Hämta normaliserade koordinater från dict (0.0-1.0)
        2. Konvertera till pixel-koordinater (multiplicera med bildstorlek)
        3. Skala till widget-storlek (multiplicera med scale_factor)
        4. Lägg till offset för centrering och panning
        5. Returnera som QRect i widget-koordinater
        
        Args:
            coords: Dict med normaliserade koordinater {"x": 0.0-1.0, "y": 0.0-1.0, 
                   "width": 0.0-1.0, "height": 0.0-1.0}
        
        Returns:
            QRect i widget-koordinater, eller None om koordinater saknas eller är ogiltiga
        """
        if not self.pdf_image or not coords:
            return None
        
        # Hämta normaliserade koordinater från dict (0.0-1.0)
        norm_x = coords.get("x", 0)
        norm_y = coords.get("y", 0)
        norm_width = coords.get("width", 0)
        norm_height = coords.get("height", 0)
        
        # Hämta faktisk bildstorlek i pixels
        img_width = self.pdf_image.width()
        img_height = self.pdf_image.height()
        
        if img_width <= 0 or img_height <= 0:
            return None
        
        # Steg 1: Konvertera normaliserade koordinater till pixel-koordinater
        # Multiplicera med faktisk bildstorlek för att få absoluta pixel-koordinater
        pixel_x = norm_x * img_width
        pixel_y = norm_y * img_height
        pixel_width = norm_width * img_width
        pixel_height = norm_height * img_height
        
        # Steg 2: Beräkna skalad bildstorlek i widget (med zoom-factor)
        scaled_width = img_width * self.scale_factor
        scaled_height = img_height * self.scale_factor
        
        # Steg 3: Beräkna offset för centrerad bild (inklusive panning)
        # Samma beräkning som i _normalize_rect() för symmetri
        x_offset = max(0, (self.width() - scaled_width) / 2) + self.pan_offset.x()
        y_offset = max(0, (self.height() - scaled_height) / 2) + self.pan_offset.y()
        
        # Steg 4: Konvertera pixel-koordinater till widget-koordinater
        # Multiplicera med scale_factor (för zoom) och lägg till offset (för centrering och panning)
        widget_x = int(x_offset + pixel_x * self.scale_factor)
        widget_y = int(y_offset + pixel_y * self.scale_factor)
        widget_width = int(pixel_width * self.scale_factor)
        widget_height = int(pixel_height * self.scale_factor)
        
        return QRect(widget_x, widget_y, widget_width, widget_height)


class MappingTab(QWidget):
    """Flik för mappning av fält och tabeller."""
    
    mapping_completed = Signal(str)  # cluster_id
    
    def __init__(
        self,
        document_manager: DocumentManager,
        template_manager: TemplateManager
    ):
        super().__init__()
        self.document_manager = document_manager
        self.template_manager = template_manager
        self.pdf_processor = PDFProcessor()
        self.extraction_engine = ExtractionEngine(self.pdf_processor)
        self.text_extractor = TextExtractor(self.pdf_processor)
        self.logger = get_logger()
        
        self.current_cluster_id: Optional[str] = None
        self.current_doc: Optional[PDFDocument] = None
        self.current_template: Optional[Template] = None
        self.pdf_dimensions: Optional[Tuple[float, float]] = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Skapar UI."""
        layout = QHBoxLayout(self)
        
        # Vänster panel: Fältlista och kontroller
        left_panel = QVBoxLayout()
        
        # Header
        header = QLabel("🗺️ Mapping")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        left_panel.addWidget(header)
        
        # Fältlista
        field_group = QGroupBox("Fält")
        field_layout = QVBoxLayout()
        
        self.field_list = QListWidget()
        self.field_list.itemClicked.connect(self._on_field_selected)
        field_layout.addWidget(self.field_list)
        
        # Fältknappar
        field_btn_layout = QHBoxLayout()
        self.map_value_btn = QPushButton("✏️ Markera Värde")
        self.map_value_btn.clicked.connect(self._start_value_mapping)
        self.map_value_btn.setEnabled(False)
        field_btn_layout.addWidget(self.map_value_btn)
        
        self.map_table_btn = QPushButton("📍 Mappa Tabell")
        self.map_table_btn.clicked.connect(self._start_table_mapping)
        self.map_table_btn.setEnabled(False)
        field_btn_layout.addWidget(self.map_table_btn)
        
        field_layout.addLayout(field_btn_layout)
        
        self.create_field_btn = QPushButton("➕ Skapa Eget Fält")
        self.create_field_btn.clicked.connect(self._create_custom_field)
        field_layout.addWidget(self.create_field_btn)
        
        field_group.setLayout(field_layout)
        left_panel.addWidget(field_group)
        
        # Action knappar
        action_group = QGroupBox("Åtgärder")
        action_layout = QVBoxLayout()
        
        self.test_btn = QPushButton("🧪 Testa Extraktion")
        self.test_btn.clicked.connect(self._test_extraction)
        self.test_btn.setEnabled(False)
        action_layout.addWidget(self.test_btn)
        
        self.map_all_btn = QPushButton("🚀 Mappa Alla i Klustret")
        self.map_all_btn.clicked.connect(self._map_all_in_cluster)
        self.map_all_btn.setEnabled(False)
        action_layout.addWidget(self.map_all_btn)
        
        self.save_template_btn = QPushButton("💾 Spara Mall")
        self.save_template_btn.clicked.connect(self._save_template)
        self.save_template_btn.setEnabled(False)
        action_layout.addWidget(self.save_template_btn)
        
        action_group.setLayout(action_layout)
        left_panel.addWidget(action_group)
        
        left_panel.addStretch()
        
        # Höger panel: PDF-visning
        right_panel = QVBoxLayout()
        
        # Zoom-kontroller
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setMinimum(10)  # 0.1x
        self.zoom_slider.setMaximum(500)  # 5.0x
        self.zoom_slider.setValue(90)  # 0.9x (default)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)
        self.zoom_label = QLabel("90%")
        zoom_layout.addWidget(self.zoom_label)
        zoom_layout.addWidget(QLabel("(Scrollhjul för zoom, Alt+Klick för panning)"))
        right_panel.addLayout(zoom_layout)
        
        self.pdf_viewer = PDFViewer()
        self.pdf_viewer.value_selected.connect(self._on_value_selected)
        self.pdf_viewer.table_selected.connect(self._on_table_selected)
        right_panel.addWidget(self.pdf_viewer)
        
        # Status
        self.status_label = QLabel("Välj ett kluster från 'Document Types' för att börja mappning.")
        right_panel.addWidget(self.status_label)
        
        # Layout
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setMaximumWidth(300)
        
        layout.addWidget(left_widget)
        layout.addLayout(right_panel)
    
    def load_cluster(self, cluster_id: str):
        """Laddar ett kluster för mappning."""
        self.current_cluster_id = cluster_id
        
        try:
            # Hämta referensdokument
            ref_doc = self.document_manager.get_reference_document(cluster_id)
            if not ref_doc:
                self.logger.warning(f"Inget referensdokument hittades för kluster: {cluster_id}")
                QMessageBox.warning(
                    self,
                    "Fel",
                    f"Inget referensdokument hittades för klustret '{cluster_id}'.\n\nKontrollera att klustret innehåller PDF:er."
                )
                return
            
            self.current_doc = ref_doc
            
            # Ladda eller skapa template
            try:
                template = self.template_manager.get_template(cluster_id)
                if not template:
                    template = self.template_manager.create_template(
                        cluster_id, ref_doc.file_path
                    )
                self.current_template = template
            except Exception as e:
                log_error_with_context(
                    self.logger, e,
                    {"cluster_id": cluster_id, "file_path": ref_doc.file_path},
                    "Fel vid laddning/skapande av template"
                )
                QMessageBox.critical(
                    self,
                    "Fel",
                    f"Kunde inte ladda eller skapa mappningsmall för klustret.\n\nKontrollera att mappningsmallar är korrekt formaterade."
                )
                return
            
            # Hämta PDF-dimensioner (validera att PDF kan läsas)
            try:
                self.pdf_dimensions = self.pdf_processor.get_pdf_dimensions(ref_doc.file_path)
                if not self.pdf_dimensions:
                    raise ValueError("PDF-dimensioner kunde inte hämtas")
            except Exception as e:
                log_error_with_context(
                    self.logger, e,
                    {"file_path": ref_doc.file_path, "cluster_id": cluster_id},
                    "Fel vid hämtning av PDF-dimensioner"
                )
                QMessageBox.critical(
                    self,
                    "Fel",
                    f"Kunde inte läsa PDF: '{ref_doc.file_path}'.\n\nKontrollera att PDF:en är korruptfri och inte lösenordsskyddad."
                )
                return
            
            # Ladda PDF-bild
            try:
                pdf_image = self.pdf_processor.get_page_image(ref_doc.file_path, 0)
                if pdf_image:
                    # Konvertera PIL Image till QImage
                    # PIL Image -> bytes -> QImage
                    img_bytes = io.BytesIO()
                    pdf_image.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    
                    qimage = QImage()
                    qimage.loadFromData(img_bytes.getvalue())
                    
                    # Konvertera QImage till QPixmap
                    pixmap = QPixmap.fromImage(qimage)
                    self.pdf_viewer.set_pdf_image(pixmap)
                else:
                    self.logger.warning(f"Kunde inte generera PDF-bild för: {ref_doc.file_path}")
                    QMessageBox.warning(
                        self,
                        "Varning",
                        f"Kunde inte visa PDF: '{ref_doc.file_path}'.\n\nPDF:en kan vara skannad - OCR kan krävas."
                    )
            except Exception as e:
                log_error_with_context(
                    self.logger, e,
                    {"file_path": ref_doc.file_path, "cluster_id": cluster_id},
                    "Fel vid laddning av PDF-bild"
                )
                QMessageBox.critical(
                    self,
                    "Fel",
                    f"Kunde inte ladda PDF-bild: '{ref_doc.file_path}'.\n\nKontrollera att Poppler är installerat för PDF-till-bild konvertering."
                )
                return
            
            # Uppdatera fältlista
            self._refresh_field_list()
            
            # Uppdatera mappningar i PDFViewer
            self._update_mappings_display()
            
            # Aktivera knappar
            self.map_value_btn.setEnabled(True)
            self.map_table_btn.setEnabled(True)
            self.test_btn.setEnabled(True)
            self.map_all_btn.setEnabled(True)
            self.save_template_btn.setEnabled(True)
            
            self.status_label.setText(f"Mappar kluster: {cluster_id}")
            
            # Uppdatera zoom-slider
            if self.pdf_viewer.scale_factor:
                zoom_percent = int(self.pdf_viewer.scale_factor * 100)
                self.zoom_slider.setValue(zoom_percent)
                self.zoom_label.setText(f"{zoom_percent}%")
        
        except Exception as e:
            log_error_with_context(
                self.logger, e,
                {"cluster_id": cluster_id},
                "Oväntat fel vid laddning av kluster"
            )
            QMessageBox.critical(
                self,
                "Fel",
                f"Ett oväntat fel inträffade vid laddning av klustret.\n\nLoggar innehåller mer information för debugging."
            )
    
    def _on_zoom_changed(self, value: int):
        """
        Hanterar zoom-ändring från slider.
        
        Synchroniserar zoom-slider med PDFViewer.scale_factor och uppdaterar zoom-label.
        Begränsar zoom till min_scale och max_scale (0.1x - 5.0x).
        """
        if self.pdf_viewer:
            # Konvertera slider-värde (10-500) till scale_factor (0.1-5.0)
            new_scale = value / 100.0
            
            # Begränsa till min_scale och max_scale
            new_scale = max(self.pdf_viewer.min_scale, min(self.pdf_viewer.max_scale, new_scale))
            
            # Uppdatera scale_factor i PDFViewer
            self.pdf_viewer.scale_factor = new_scale
            
            # Trigga omritning
            self.pdf_viewer.update()
            
            # Uppdatera zoom-label med faktisk zoom-nivå
            actual_percent = int(new_scale * 100)
            self.zoom_label.setText(f"{actual_percent}%")
    
    def _update_mappings_display(self):
        """Uppdaterar visningen av mappningar i PDFViewer."""
        if not self.current_template or not self.current_doc:
            return
        
        # Bygg lista över fältmappningar med värden
        field_mappings_display = []
        for fm in self.current_template.field_mappings:
            if fm.value_coords:
                # Hämta extraherat värde om tillgängligt
                extracted_value = ""
                if self.current_doc.extracted_data and "fields" in self.current_doc.extracted_data:
                    extracted_value = self.current_doc.extracted_data["fields"].get(fm.field_name, "")
                
                field_mappings_display.append({
                    "name": fm.field_name,
                    "coords": fm.value_coords,
                    "value": str(extracted_value) if extracted_value else ""
                })
        
        # Bygg lista över tabellmappningar
        table_mappings_display = []
        for tm in self.current_template.table_mappings:
            if tm.table_coords:
                table_mappings_display.append({
                    "name": tm.table_name,
                    "coords": tm.table_coords
                })
        
        # Uppdatera PDFViewer
        self.pdf_viewer.set_mappings(
            field_mappings=field_mappings_display,
            table_mappings=table_mappings_display
        )
    
    def _refresh_field_list(self):
        """Uppdaterar fältlistan."""
        self.field_list.clear()
        
        if not self.current_template:
            return
        
        # Lägg till fördefinierade fält
        predefined_fields = [
            "Fakturanummer", "Datum", "Totalt", "Moms", "Leverantör",
            "Ordernummer", "Projektnummer", "Betalningsvillkor"
        ]
        
        for field_name in predefined_fields:
            # Hitta mappning för detta fält
            field_mapping = next(
                (fm for fm in self.current_template.field_mappings if fm.field_name == field_name),
                None
            )
            
            is_mapped = field_mapping is not None
            icon = "✓" if is_mapped else "○"
            
            # Hämta extraherat värde om tillgängligt
            display_text = f"{icon} {field_name}"
            if is_mapped and self.current_doc and self.current_doc.extracted_data:
                extracted_value = self.current_doc.extracted_data.get("fields", {}).get(field_name, "")
                if extracted_value:
                    # Visa värde (begränsa längd)
                    value_display = str(extracted_value)[:40]
                    if len(str(extracted_value)) > 40:
                        value_display += "..."
                    display_text += f"\n   → {value_display}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, field_name)
            self.field_list.addItem(item)
        
        # Lägg till tabeller
        for table in self.current_template.table_mappings:
            display_text = f"✓ 📊 {table.table_name}"
            # Visa antal kolumner och rader om extraherad data finns
            if self.current_doc and self.current_doc.extracted_data:
                table_data = self.current_doc.extracted_data.get("tables", {}).get(table.table_name, [])
                if table_data:
                    display_text += f"\n   → {len(table_data)} rader, {len(table.columns)} kolumner"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, f"table:{table.table_name}")
            self.field_list.addItem(item)
    
    def _on_field_selected(self, item: QListWidgetItem):
        """Hanterar val av fält."""
        field_name = item.data(Qt.UserRole)
        self.status_label.setText(f"Valt fält: {field_name}. Klicka 'Markera Värde' för att mappa.")
    
    def _start_value_mapping(self):
        """Startar mappning av värde."""
        current_item = self.field_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Välj fält", "Välj ett fält först.")
            return
        
        field_name = current_item.data(Qt.UserRole)
        if field_name.startswith("table:"):
            QMessageBox.warning(self, "Fel", "Använd 'Mappa Tabell' för tabeller.")
            return
        
        self.pdf_viewer.set_selection_mode("value")
        self.status_label.setText(f"Markera VÄRDET för '{field_name}' i PDF:en (dra rektangel).")
    
    def _start_table_mapping(self):
        """Startar mappning av tabell."""
        self.pdf_viewer.set_selection_mode("table")
        self.status_label.setText("Markera tabellområdet i PDF:en (dra rektangel runt hela tabellen).")
    
    def _on_value_selected(self, rect: QRect):
        """Hanterar när användaren markerat ett värde."""
        self.pdf_viewer.set_selection_mode(None)
        
        current_item = self.field_list.currentItem()
        if not current_item:
            return
        
        field_name = current_item.data(Qt.UserRole)
        
        # Validera att PDF-dimensioner finns
        if not self.current_doc:
            self.logger.warning("Inget dokument laddat vid värde-mappning")
            QMessageBox.warning(
                self,
                "Fel",
                "Inget dokument är laddat.\n\nLadda ett kluster först."
            )
            return
        
        if not self.pdf_dimensions:
            self.logger.warning(f"PDF-dimensioner saknas för: {self.current_doc.file_path}")
            QMessageBox.warning(
                self,
                "Fel",
                "Kunde inte hämta PDF-dimensioner.\n\nFörsök ladda klustret igen."
            )
            return
        
        # Extrahera text från markerat område
        extracted_value = ""
        try:
            # Konvertera widget-koordinater till normaliserade koordinater
            # PDFViewer returnerar redan normaliserade koordinater
            coords = {
                "x": rect.x() / 1000.0,
                "y": rect.y() / 1000.0,
                "width": rect.width() / 1000.0,
                "height": rect.height() / 1000.0
            }
            
            extracted_value = self.text_extractor.extract_text_from_region(
                self.current_doc.file_path,
                0,
                coords,
                self.pdf_dimensions[0],
                self.pdf_dimensions[1]
            )
        except Exception as e:
            log_error_with_context(
                self.logger, e,
                {
                    "field_name": field_name,
                    "file_path": self.current_doc.file_path,
                    "coords": coords
                },
                "Fel vid textextraktion från markerat område"
            )
            QMessageBox.critical(
                self,
                "Fel",
                f"Kunde inte extrahera text från markerat område för '{field_name}'.\n\nKontrollera att PDF:en kan läsas korrekt."
            )
            return
        
        # Öppna dialog för rubrikmappning med extraherad text
        dialog = ValueHeaderMappingDialog(self, extracted_value=extracted_value)
        if dialog.exec():
            header_text, is_recurring = dialog.get_result()
            
            try:
                # Skapa fältmappning
                field_mapping = FieldMapping(
                    field_name=field_name,
                    field_type="value_header",
                    value_coords={
                        "x": rect.x() / 1000.0,  # Normalisera
                        "y": rect.y() / 1000.0,
                        "width": rect.width() / 1000.0,
                        "height": rect.height() / 1000.0
                    },
                    header_text=header_text,
                    is_recurring=is_recurring
                )
                
                # Lägg till i template
                # Ta bort befintlig mappning för samma fält
                self.current_template.field_mappings = [
                    fm for fm in self.current_template.field_mappings
                    if fm.field_name != field_name
                ]
                self.current_template.field_mappings.append(field_mapping)
                
                # Testa extraktion för att få värdet att visa
                try:
                    result = self.extraction_engine.extract_data(
                        self.current_doc.file_path,
                        self.current_template
                    )
                    if result and "fields" in result:
                        # Spara extraherade värden temporärt för visning
                        if not self.current_doc.extracted_data:
                            self.current_doc.extracted_data = {}
                        if "fields" not in self.current_doc.extracted_data:
                            self.current_doc.extracted_data["fields"] = {}
                        self.current_doc.extracted_data["fields"][field_name] = result["fields"].get(field_name, extracted_value)
                except Exception as e:
                    # Om extraktion misslyckas, använd det ursprungliga extraherade värdet
                    log_error_with_context(
                        self.logger, e,
                        {"field_name": field_name, "file_path": self.current_doc.file_path},
                        "Fel vid test-extraktion efter mappning"
                    )
                    if not self.current_doc.extracted_data:
                        self.current_doc.extracted_data = {}
                    if "fields" not in self.current_doc.extracted_data:
                        self.current_doc.extracted_data["fields"] = {}
                    self.current_doc.extracted_data["fields"][field_name] = extracted_value
                
                self._refresh_field_list()
                self._update_mappings_display()
                self.status_label.setText(f"Fält '{field_name}' mappat! Extraherad text: {extracted_value[:50]}...")
                
            except Exception as e:
                log_error_with_context(
                    self.logger, e,
                    {"field_name": field_name, "header_text": header_text},
                    "Fel vid skapande av fältmappning"
                )
                QMessageBox.critical(
                    self,
                    "Fel",
                    f"Kunde inte skapa mappning för '{field_name}'.\n\nKontrollera att mappningsmallar är korrekt formaterade."
                )
    
    def _on_table_selected(self, rect: QRect):
        """Hanterar när användaren markerat en tabell."""
        self.pdf_viewer.set_selection_mode(None)
        
        # Validera att PDF-dimensioner finns
        if not self.current_doc:
            self.logger.warning("Inget dokument laddat vid tabell-mappning")
            QMessageBox.warning(
                self,
                "Fel",
                "Inget dokument är laddat.\n\nLadda ett kluster först."
            )
            return
        
        if not self.pdf_dimensions:
            self.logger.warning(f"PDF-dimensioner saknas för: {self.current_doc.file_path}")
            QMessageBox.warning(
                self,
                "Fel",
                "Kunde inte hämta PDF-dimensioner.\n\nFörsök ladda klustret igen."
            )
            return
        
        # Extrahera tabelltext
        table_rows = []
        try:
            table_coords = {
                "x": rect.x() / 1000.0,
                "y": rect.y() / 1000.0,
                "width": rect.width() / 1000.0,
                "height": rect.height() / 1000.0
            }
            
            table_rows = self.text_extractor.extract_table_text(
                self.current_doc.file_path,
                0,
                table_coords,
                self.pdf_dimensions[0],
                self.pdf_dimensions[1]
            )
        except Exception as e:
            log_error_with_context(
                self.logger, e,
                {
                    "file_path": self.current_doc.file_path,
                    "table_coords": table_coords
                },
                "Fel vid tabelltextextraktion"
            )
            QMessageBox.critical(
                self,
                "Fel",
                f"Kunde inte extrahera text från markerat tabellområde.\n\nKontrollera att PDF:en kan läsas korrekt."
            )
            return
        
        # Öppna dialog för kolumnmappning
        dialog = TableMappingDialog(self, table_rows=table_rows)
        if dialog.exec():
            column_mappings = dialog.get_result()
            
            if not column_mappings:
                QMessageBox.warning(
                    self,
                    "Inga kolumner",
                    "Du måste mappa minst en kolumn.\n\nAnge kolumnnamn i dialogfönstret."
                )
                return
            
            try:
                # Skapa tabellmappning
                table_mapping = TableMapping(
                    table_name="Artiklar",
                    table_coords={
                        "x": rect.x() / 1000.0,
                        "y": rect.y() / 1000.0,
                        "width": rect.width() / 1000.0,
                        "height": rect.height() / 1000.0
                    },
                    columns=column_mappings,
                    has_header_row=True
                )
                
                # Ta bort befintlig tabellmappning om den finns
                self.current_template.table_mappings = [
                    tm for tm in self.current_template.table_mappings
                    if tm.table_name != "Artiklar"
                ]
                
                self.current_template.table_mappings.append(table_mapping)
                
                # Testa extraktion för att få tabelldata att visa
                try:
                    result = self.extraction_engine.extract_data(
                        self.current_doc.file_path,
                        self.current_template
                    )
                    if result and "tables" in result:
                        # Spara extraherad data temporärt för visning
                        if not self.current_doc.extracted_data:
                            self.current_doc.extracted_data = {}
                        self.current_doc.extracted_data["tables"] = result["tables"]
                except Exception as e:
                    log_error_with_context(
                        self.logger, e,
                        {"file_path": self.current_doc.file_path, "table_name": "Artiklar"},
                        "Fel vid test-extraktion av tabell"
                    )
                    # Fortsätt även om test-extraktion misslyckas
                
                self._refresh_field_list()
                self._update_mappings_display()
                self.status_label.setText(
                    f"Tabell mappad! {len(column_mappings)} kolumner, {len(table_rows)} rader extraherade."
                )
                
            except Exception as e:
                log_error_with_context(
                    self.logger, e,
                    {"column_mappings": len(column_mappings), "table_rows": len(table_rows)},
                    "Fel vid skapande av tabellmappning"
                )
                QMessageBox.critical(
                    self,
                    "Fel",
                    f"Kunde inte skapa tabellmappning.\n\nKontrollera att mappningsmallar är korrekt formaterade."
                )
    
    def _create_custom_field(self):
        """Skapar ett eget fält."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Nytt Fält")
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("Ange fältnamn:"))
        field_input = QLineEdit()
        layout.addWidget(field_input)
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("Avbryt")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        if dialog.exec():
            field_name = field_input.text()
            if field_name:
                item = QListWidgetItem(f"○ {field_name}")
                item.setData(Qt.UserRole, field_name)
                self.field_list.addItem(item)
    
    def _test_extraction(self):
        """Testar extraktion på nuvarande PDF."""
        if not self.current_doc or not self.current_template:
            self.logger.warning("Test-extraktion: Saknar dokument eller template")
            QMessageBox.warning(
                self,
                "Varning",
                "Inget dokument eller mappningsmall är laddat.\n\nLadda ett kluster först."
            )
            return
        
        # Validera att PDF-dimensioner finns
        if not self.pdf_dimensions:
            self.logger.warning(f"Test-extraktion: PDF-dimensioner saknas för: {self.current_doc.file_path}")
            QMessageBox.warning(
                self,
                "Varning",
                "Kunde inte hämta PDF-dimensioner.\n\nFörsök ladda klustret igen."
            )
            return
        
        try:
            result = self.extraction_engine.extract_data(
                self.current_doc.file_path,
                self.current_template
            )
            
            # Visa resultat
            result_text = "Extraherade fält:\n"
            if result.get("fields"):
                for key, value in result["fields"].items():
                    # Begränsa längd på värden för läsbarhet
                    value_str = str(value)[:100]
                    if len(str(value)) > 100:
                        value_str += "..."
                    result_text += f"  {key}: {value_str}\n"
            else:
                result_text += "  (Inga fält extraherade)\n"
            
            result_text += "\nExtraherade tabeller:\n"
            if result.get("tables"):
                for table_name, rows in result["tables"].items():
                    result_text += f"  {table_name}: {len(rows)} rader\n"
            else:
                result_text += "  (Inga tabeller extraherade)\n"
            
            # Spara extraherad data temporärt för visning
            if not self.current_doc.extracted_data:
                self.current_doc.extracted_data = {}
            self.current_doc.extracted_data.update(result)
            
            # Uppdatera visning
            self._refresh_field_list()
            self._update_mappings_display()
            
            QMessageBox.information(self, "Testresultat", result_text)
            
        except Exception as e:
            # Logga fel med kontext för debugging
            log_error_with_context(
                self.logger, e,
                {
                    "file_path": self.current_doc.file_path,
                    "cluster_id": self.current_cluster_id,
                    "template_fields": len(self.current_template.field_mappings),
                    "template_tables": len(self.current_template.table_mappings)
                },
                "Fel vid test-extraktion"
            )
            
            # Bygg användarvänligt felmeddelande
            error_msg = "Extraktion misslyckades."
            
            # Specifika felmeddelanden baserat på feltyp
            error_str = str(e).lower()
            if "poppler" in error_str or "pdfinfo" in error_str:
                error_msg += "\n\nKontrollera att Poppler är installerat och korrekt konfigurerat.\n\nSe INSTALL_POPPLER.md för installationsinstruktioner."
            elif "tesseract" in error_str or "tesseractnotfounderror" in error_str:
                error_msg += "\n\nKontrollera att Tesseract OCR är installerat och korrekt konfigurerat.\n\nTesseract krävs för OCR-funktionalitet."
            elif "coordinate" in error_str or "koordinat" in error_str:
                error_msg += "\n\nKunde inte mappa koordinater.\n\nFörsök markera området igen eller kontrollera PDF:ens struktur."
            else:
                error_msg += f"\n\nFel: {str(e)[:200]}\n\nLoggar innehåller mer information för debugging."
            
            QMessageBox.critical(self, "Fel vid Extraktion", error_msg)
    
    def _map_all_in_cluster(self):
        """Applicerar mallen på alla PDF:er i klustret."""
        if not self.current_cluster_id or not self.current_template:
            self.logger.warning("Mappa alla: Saknar cluster_id eller template")
            QMessageBox.warning(
                self,
                "Varning",
                "Inget kluster eller mappningsmall är laddat.\n\nLadda ett kluster först."
            )
            return
        
        # Validera att template har några mappningar
        if not self.current_template.field_mappings and not self.current_template.table_mappings:
            QMessageBox.warning(
                self,
                "Varning",
                "Mappningsmallen är tom.\n\nMappa minst ett fält eller en tabell innan du applicerar på alla PDF:er."
            )
            return
        
        reply = QMessageBox.question(
            self,
            "Bekräfta",
            f"Vill du applicera mallen på alla PDF:er i klustret?\n\nDetta kommer att bearbeta alla PDF:er i klustret.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Spara template först
                self.template_manager.save_template(self.current_template)
                self.logger.info(f"Sparat template för kluster: {self.current_cluster_id}")
            except Exception as e:
                log_error_with_context(
                    self.logger, e,
                    {"cluster_id": self.current_cluster_id},
                    "Fel vid sparande av template"
                )
                QMessageBox.critical(
                    self,
                    "Fel",
                    f"Kunde inte spara mappningsmall.\n\nKontrollera att mappningsmallar är korrekt formaterade."
                )
                return
            
            # Extrahera data från alla dokument
            try:
                cluster_docs = self.document_manager.get_cluster_documents(
                    self.current_cluster_id
                )
            except Exception as e:
                log_error_with_context(
                    self.logger, e,
                    {"cluster_id": self.current_cluster_id},
                    "Fel vid hämtning av kluster-dokument"
                )
                QMessageBox.critical(
                    self,
                    "Fel",
                    f"Kunde inte hämta dokument för klustret.\n\nKontrollera att klustret finns."
                )
                return
            
            if not cluster_docs:
                QMessageBox.warning(
                    self,
                    "Varning",
                    "Inga dokument hittades i klustret.\n\nKontrollera att klustret innehåller PDF:er."
                )
                return
            
            # Bearbeta varje dokument
            successful = 0
            failed = 0
            
            for doc in cluster_docs:
                try:
                    result = self.extraction_engine.extract_data(
                        doc.file_path,
                        self.current_template
                    )
                    doc.extracted_data = result
                    doc.status = "mapped"
                    self.document_manager.update_document(doc)
                    successful += 1
                except Exception as e:
                    doc.status = "error"
                    failed += 1
                    log_error_with_context(
                        self.logger, e,
                        {
                            "file_path": doc.file_path,
                            "cluster_id": self.current_cluster_id
                        },
                        "Fel vid extraktion från dokument"
                    )
            
            # Visa resultat
            result_msg = f"Mappning klar!\n\nLyckades: {successful} PDF:er\nMisslyckades: {failed} PDF:er"
            if failed > 0:
                result_msg += f"\n\n{failed} PDF:er kunde inte bearbetas. Kontrollera loggar för detaljer."
            
            # Fråga om granskning
            if successful > 0:
                reply = QMessageBox.question(
                    self,
                    "Granska?",
                    f"{result_msg}\n\nVill du granska resultaten?",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    self.mapping_completed.emit(self.current_cluster_id)
                else:
                    QMessageBox.information(
                        self,
                        "Klar",
                        result_msg
                    )
            else:
                QMessageBox.warning(
                    self,
                    "Varning",
                    f"Ingen PDF kunde bearbetas.\n\nKontrollera loggar för detaljer."
                )
    
    def _save_template(self):
        """Sparar mallen."""
        if not self.current_template:
            self.logger.warning("Spara mall: Inget template att spara")
            QMessageBox.warning(
                self,
                "Varning",
                "Ingen mappningsmall är laddat.\n\nLadda ett kluster först."
            )
            return
        
        try:
            self.template_manager.save_template(self.current_template)
            self.logger.info(f"Template sparad för kluster: {self.current_cluster_id}")
            QMessageBox.information(
                self,
                "Sparat",
                f"Mappningsmall sparad!\n\nKluster: {self.current_cluster_id or 'Okänt'}"
            )
        except Exception as e:
            log_error_with_context(
                self.logger, e,
                {
                    "cluster_id": self.current_cluster_id,
                    "fields": len(self.current_template.field_mappings),
                    "tables": len(self.current_template.table_mappings)
                },
                "Fel vid sparande av template"
            )
            QMessageBox.critical(
                self,
                "Fel",
                f"Kunde inte spara mappningsmall.\n\nKontrollera att mappningsmallar är korrekt formaterade.\n\nLoggar innehåller mer information."
            )
