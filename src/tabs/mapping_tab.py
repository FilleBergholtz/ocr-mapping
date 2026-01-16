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
        
        self.setMouseTracking(True)
    
    def set_pdf_image(self, pixmap: QPixmap):
        """Sätter PDF-bilden."""
        self.pdf_image = pixmap
        self.original_image = pixmap
        # Skala för att passa i widget
        if pixmap:
            self.scale_factor = min(
                self.width() / pixmap.width(),
                self.height() / pixmap.height()
            ) * 0.9
            self.pan_offset = QPoint(0, 0)
        self.update()
    
    def set_selection_mode(self, mode: Optional[str]):
        """Sätter läge för markering (None, 'value', 'table')."""
        self.selection_mode = mode
        self.selection_rect = None
    
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
        """Hanterar musrörelse."""
        if self.is_panning and self.pan_start_pos:
            # Panning
            delta = event.pos() - self.pan_start_pos
            self.pan_offset += delta
            self.pan_start_pos = event.pos()
            self.update()
        elif self.selection_mode and self.selection_rect is not None:
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
        Konverterar rektangel till normaliserade koordinater (0.0-1.0).
        
        Förbättrad version som hanterar olika PDF-storlekar, DPI-inställningar och panning korrekt.
        """
        if not self.pdf_image:
            return rect
        
        # Hämta faktisk bildstorlek (inte widget-storlek)
        img_width = self.pdf_image.width()
        img_height = self.pdf_image.height()
        
        if img_width <= 0 or img_height <= 0:
            return rect
        
        # Beräkna skalad bildstorlek i widget
        scaled_width = img_width * self.scale_factor
        scaled_height = img_height * self.scale_factor
        
        # Beräkna offset för centrerad bild (inklusive panning)
        x_offset = max(0, (self.width() - scaled_width) / 2) + self.pan_offset.x()
        y_offset = max(0, (self.height() - scaled_height) / 2) + self.pan_offset.y()
        
        # Konvertera widget-koordinater till bild-koordinater
        # Subtrahera offset och dividera med scale_factor för att få pixel-koordinater
        adj_x = (rect.x() - x_offset) / self.scale_factor
        adj_y = (rect.y() - y_offset) / self.scale_factor
        adj_width = rect.width() / self.scale_factor
        adj_height = rect.height() / self.scale_factor
        
        # Säkerställ att koordinaterna är inom bildens gränser
        adj_x = max(0, min(img_width, adj_x))
        adj_y = max(0, min(img_height, adj_y))
        adj_width = max(0, min(img_width - adj_x, adj_width))
        adj_height = max(0, min(img_height - adj_y, adj_height))
        
        # Normalisera till 0.0-1.0 baserat på faktisk bildstorlek
        normalized_x = adj_x / img_width
        normalized_y = adj_y / img_height
        normalized_width = adj_width / img_width
        normalized_height = adj_height / img_height
        
        # Säkerställ att värdena är inom [0, 1]
        normalized_x = max(0.0, min(1.0, normalized_x))
        normalized_y = max(0.0, min(1.0, normalized_y))
        normalized_width = max(0.0, min(1.0 - normalized_x, normalized_width))
        normalized_height = max(0.0, min(1.0 - normalized_y, normalized_height))
        
        # Returnera som QRect med normaliserade värden (multiplicerade med 1000 för precision)
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
            
            # Rita markering om aktiv
            if self.selection_rect:
                pen = QPen(QColor(255, 0, 0), 2)
                painter.setPen(pen)
                painter.drawRect(self.selection_rect)


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
        
        # Hämta referensdokument
        ref_doc = self.document_manager.get_reference_document(cluster_id)
        if not ref_doc:
            QMessageBox.warning(self, "Fel", "Inget referensdokument hittades för klustret.")
            return
        
        self.current_doc = ref_doc
        
        # Ladda eller skapa template
        template = self.template_manager.get_template(cluster_id)
        if not template:
            template = self.template_manager.create_template(
                cluster_id, ref_doc.file_path
            )
        self.current_template = template
        
        # Hämta PDF-dimensioner
        self.pdf_dimensions = self.pdf_processor.get_pdf_dimensions(ref_doc.file_path)
        
        # Ladda PDF-bild
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
        
        # Uppdatera fältlista
        self._refresh_field_list()
        
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
    
    def _on_zoom_changed(self, value: int):
        """Hanterar zoom-ändring från slider."""
        if self.pdf_viewer:
            self.pdf_viewer.scale_factor = value / 100.0
            self.pdf_viewer.update()
            self.zoom_label.setText(f"{value}%")
    
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
            # Kolla om fältet redan är mappat
            is_mapped = any(
                fm.field_name == field_name
                for fm in self.current_template.field_mappings
            )
            icon = "✓" if is_mapped else "○"
            item = QListWidgetItem(f"{icon} {field_name}")
            item.setData(Qt.UserRole, field_name)
            self.field_list.addItem(item)
        
        # Lägg till tabeller
        for table in self.current_template.table_mappings:
            item = QListWidgetItem(f"✓ 📊 {table.table_name}")
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
        
        # Extrahera text från markerat område
        extracted_value = ""
        if self.current_doc and self.pdf_dimensions:
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
        
        # Öppna dialog för rubrikmappning med extraherad text
        dialog = ValueHeaderMappingDialog(self, extracted_value=extracted_value)
        if dialog.exec():
            header_text, is_recurring = dialog.get_result()
            
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
            
            self._refresh_field_list()
            self.status_label.setText(f"Fält '{field_name}' mappat! Extraherad text: {extracted_value[:50]}...")
    
    def _on_table_selected(self, rect: QRect):
        """Hanterar när användaren markerat en tabell."""
        self.pdf_viewer.set_selection_mode(None)
        
        # Extrahera tabelltext
        table_rows = []
        if self.current_doc and self.pdf_dimensions:
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
        
        # Öppna dialog för kolumnmappning
        dialog = TableMappingDialog(self, table_rows=table_rows)
        if dialog.exec():
            column_mappings = dialog.get_result()
            
            if not column_mappings:
                QMessageBox.warning(self, "Inga kolumner", "Du måste mappa minst en kolumn.")
                return
            
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
            self._refresh_field_list()
            self.status_label.setText(
                f"Tabell mappad! {len(column_mappings)} kolumner, {len(table_rows)} rader extraherade."
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
            return
        
        try:
            result = self.extraction_engine.extract_data(
                self.current_doc.file_path,
                self.current_template
            )
            
            # Visa resultat
            result_text = "Extraherade fält:\n"
            if result["fields"]:
                for key, value in result["fields"].items():
                    result_text += f"  {key}: {value}\n"
            else:
                result_text += "  (Inga fält extraherade)\n"
            
            result_text += "\nExtraherade tabeller:\n"
            if result["tables"]:
                for table_name, rows in result["tables"].items():
                    result_text += f"  {table_name}: {len(rows)} rader\n"
            else:
                result_text += "  (Inga tabeller extraherade)\n"
            
            QMessageBox.information(self, "Testresultat", result_text)
        except Exception as e:
            error_msg = f"Fel vid extraktion: {str(e)}"
            if "poppler" in str(e).lower():
                error_msg += "\n\nKontrollera att Poppler är installerat och korrekt konfigurerat."
            elif "tesseract" in str(e).lower():
                error_msg += "\n\nKontrollera att Tesseract OCR är installerat och korrekt konfigurerat."
            QMessageBox.critical(self, "Fel vid Extraktion", error_msg)
    
    def _map_all_in_cluster(self):
        """Applicerar mallen på alla PDF:er i klustret."""
        if not self.current_cluster_id or not self.current_template:
            return
        
        reply = QMessageBox.question(
            self,
            "Bekräfta",
            f"Vill du applicera mallen på alla PDF:er i klustret?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Spara template först
            self.template_manager.save_template(self.current_template)
            
            # Extrahera data från alla dokument
            cluster_docs = self.document_manager.get_cluster_documents(
                self.current_cluster_id
            )
            
            for doc in cluster_docs:
                try:
                    result = self.extraction_engine.extract_data(
                        doc.file_path,
                        self.current_template
                    )
                    doc.extracted_data = result
                    doc.status = "mapped"
                    self.document_manager.update_document(doc)
                except Exception as e:
                    doc.status = "error"
                    from ..core.logger import get_logger
                    logger = get_logger()
                    logger.error(f"Fel vid extraktion från {doc.file_path}: {e}", exc_info=True)
            
            # Fråga om granskning
            reply = QMessageBox.question(
                self,
                "Granska?",
                "Vill du granska resultaten?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.mapping_completed.emit(self.current_cluster_id)
            
            QMessageBox.information(
                self,
                "Klar",
                f"Mappning klar för {len(cluster_docs)} PDF:er!"
            )
    
    def _save_template(self):
        """Sparar mallen."""
        if self.current_template:
            self.template_manager.save_template(self.current_template)
            QMessageBox.information(self, "Sparat", "Mall sparad!")
