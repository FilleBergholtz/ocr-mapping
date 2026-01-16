"""
Visual Table Mapping Dialog - Dialog för visuell mappning av tabellkolumner och rader.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QLineEdit, QHeaderView,
    QMessageBox, QGroupBox, QTextEdit, QSpinBox, QCheckBox,
    QListWidget, QListWidgetItem, QSplitter, QWidget
)
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QColor, QPainter, QPen
from typing import List, Dict, Optional, Tuple
from ..core.text_extractor import TextExtractor
from ..core.pdf_processor import PDFProcessor


class VisualTableMappingDialog(QDialog):
    """Dialog för visuell mappning av tabellkolumner och rader."""
    
    def __init__(self, parent=None, pdf_path: str = None, pdf_dimensions: Tuple[float, float] = None, 
                 table_coords: Dict = None, text_extractor: TextExtractor = None, ocr_language: str = "swe+eng"):
        super().__init__(parent)
        self.setWindowTitle("Visuell Tabellmappning")
        self.setModal(True)
        self.setMinimumSize(1200, 800)
        
        self.pdf_path = pdf_path
        self.pdf_dimensions = pdf_dimensions or (612.0, 792.0)
        self.table_coords = table_coords or {}
        self.text_extractor = text_extractor
        self.ocr_language = ocr_language
        
        # Kolumn- och radmappningar
        self.column_mappings: List[Dict] = []  # [{"name": str, "coords": {...}, "index": int}, ...]
        self.row_mappings: List[Dict] = []  # [{"coords": {...}, "index": int, "is_header": bool}, ...]
        self.header_row_index: Optional[int] = None
        
        # Extraherade cellvärden
        self.extracted_cells: Dict[Tuple[int, int], str] = {}  # {(row_idx, col_idx): "value"}
        
        self._setup_ui()
        self._load_pdf_image()
        
        # Om table_coords redan finns, visa dem
        if self.table_coords and self.table_coords_label:
            self.table_coords_label.setText(
                f"X: {self.table_coords.get('x', 0):.3f}, Y: {self.table_coords.get('y', 0):.3f}\n"
                f"Bredd: {self.table_coords.get('width', 0):.3f}, Höjd: {self.table_coords.get('height', 0):.3f}"
            )
            # Aktivera kolumn- och radmarkering om tabellområde redan markerat
            self.mark_column_btn.setEnabled(True)
            self.mark_row_btn.setEnabled(True)
    
    def _setup_ui(self):
        """Skapar UI."""
        layout = QVBoxLayout(self)
        
        # Instruktioner
        info_label = QLabel(
            "<b>Instruktioner:</b><br>"
            "1. Markera tabellområdet först (hela tabellen)<br>"
            "2. Markera kolumner genom att dra lodräta rektanglar<br>"
            "3. Markera rader genom att dra vågräta rektanglar<br>"
            "4. Välj header-rad från markerade rader<br>"
            "5. Granska och redigera extraherade värden i förhandsvisningen<br>"
            "6. Ange kolumnnamn för varje kolumn"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("background-color: #e8f4f8; padding: 8px; border-radius: 4px;")
        layout.addWidget(info_label)
        
        # Huvudsplitter: PDF-visare till höger, kontroller till vänster
        splitter = QSplitter(Qt.Horizontal)
        
        # Vänster panel: Kontroller och listor
        left_panel = QVBoxLayout()
        
        # Tabellområde (markera hela tabellen)
        table_group = QGroupBox("Tabellområde")
        table_layout = QVBoxLayout()
        self.mark_table_btn = QPushButton("📍 Markera Tabellområde")
        self.mark_table_btn.clicked.connect(self._start_table_selection)
        table_layout.addWidget(self.mark_table_btn)
        self.table_coords_label = QLabel("Inte markerat")
        table_layout.addWidget(self.table_coords_label)
        table_group.setLayout(table_layout)
        left_panel.addWidget(table_group)
        
        # Kolumner
        col_group = QGroupBox("Kolumner")
        col_layout = QVBoxLayout()
        col_btn_layout = QHBoxLayout()
        self.mark_column_btn = QPushButton("↕️ Markera Kolumn")
        self.mark_column_btn.clicked.connect(self._start_column_selection)
        self.mark_column_btn.setEnabled(False)
        col_btn_layout.addWidget(self.mark_column_btn)
        
        self.remove_column_btn = QPushButton("🗑️ Ta Bort")
        self.remove_column_btn.clicked.connect(self._remove_selected_column)
        col_btn_layout.addWidget(self.remove_column_btn)
        
        col_layout.addLayout(col_btn_layout)
        
        self.column_list = QListWidget()
        self.column_list.itemSelectionChanged.connect(self._on_column_selected)
        col_layout.addWidget(self.column_list)
        
        # Kolumnnamn-input
        col_name_layout = QHBoxLayout()
        col_name_layout.addWidget(QLabel("Kolumnnamn:"))
        self.column_name_input = QLineEdit()
        self.column_name_input.setPlaceholderText("T.ex. Art.nr, Benämning, Antal...")
        self.column_name_input.textChanged.connect(self._update_column_name)
        col_name_layout.addWidget(self.column_name_input)
        col_layout.addLayout(col_name_layout)
        
        col_group.setLayout(col_layout)
        left_panel.addWidget(col_group)
        
        # Rader
        row_group = QGroupBox("Rader")
        row_layout = QVBoxLayout()
        row_btn_layout = QHBoxLayout()
        self.mark_row_btn = QPushButton("↔️ Markera Rad")
        self.mark_row_btn.clicked.connect(self._start_row_selection)
        self.mark_row_btn.setEnabled(False)
        row_btn_layout.addWidget(self.mark_row_btn)
        
        self.set_header_btn = QPushButton("📋 Sätt som Header")
        self.set_header_btn.clicked.connect(self._set_header_row)
        self.set_header_btn.setEnabled(False)
        row_btn_layout.addWidget(self.set_header_btn)
        
        self.remove_row_btn = QPushButton("🗑️ Ta Bort")
        self.remove_row_btn.clicked.connect(self._remove_selected_row)
        row_btn_layout.addWidget(self.remove_row_btn)
        
        row_layout.addLayout(row_btn_layout)
        
        self.row_list = QListWidget()
        self.row_list.itemSelectionChanged.connect(self._on_row_selected)
        row_layout.addWidget(self.row_list)
        
        row_group.setLayout(row_layout)
        left_panel.addWidget(row_group)
        
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setMaximumWidth(300)
        splitter.addWidget(left_widget)
        
        # Höger panel: PDF-visare och förhandsvisning
        right_panel = QVBoxLayout()
        
        # PDF-visare (använd PDFViewer från mapping_tab)
        from .mapping_tab import PDFViewer
        self.pdf_viewer = PDFViewer()
        self.pdf_viewer.table_selected.connect(self._on_table_selected)
        self.pdf_viewer.column_selected.connect(self._on_column_selected_dialog)
        self.pdf_viewer.row_selected.connect(self._on_row_selected_dialog)
        right_panel.addWidget(self.pdf_viewer)
        
        # Förhandsvisning
        preview_group = QGroupBox("Förhandsvisning - Extraherade värden")
        preview_layout = QVBoxLayout()
        
        preview_info = QLabel(
            "Förhandsvisning av extraherade värden. Redigera celler om värden är felaktiga."
        )
        preview_info.setWordWrap(True)
        preview_layout.addWidget(preview_info)
        
        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setMaximumHeight(200)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.itemChanged.connect(self._on_cell_edited)
        preview_layout.addWidget(self.preview_table)
        
        # Uppdatera-knapp
        self.update_preview_btn = QPushButton("🔄 Uppdatera Förhandsvisning")
        self.update_preview_btn.clicked.connect(self._update_preview)
        self.update_preview_btn.setEnabled(False)
        preview_layout.addWidget(self.update_preview_btn)
        
        preview_group.setLayout(preview_layout)
        right_panel.addWidget(preview_group)
        
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        splitter.addWidget(right_widget)
        
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
        # Knappar
        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self._validate_and_accept)
        self.ok_btn.setEnabled(False)
        self.cancel_btn = QPushButton("Avbryt")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
    
    def _load_pdf_image(self):
        """Laddar PDF-bild i visaren."""
        if not self.pdf_path:
            return
        
        try:
            pdf_processor = PDFProcessor()
            pdf_image = pdf_processor.get_page_image(self.pdf_path, 0)
            if pdf_image:
                # Konvertera PIL Image till QPixmap (samma metod som i mapping_tab)
                import io
                from PySide6.QtGui import QPixmap, QImage
                
                img_bytes = io.BytesIO()
                pdf_image.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                
                qimage = QImage()
                qimage.loadFromData(img_bytes.getvalue())
                
                pixmap = QPixmap.fromImage(qimage)
                self.pdf_viewer.set_pdf_image(pixmap)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Fel",
                f"Kunde inte ladda PDF-bild: {str(e)}"
            )
    
    def _start_table_selection(self):
        """Startar markering av tabellområde."""
        self.pdf_viewer.set_selection_mode("table")
    
    def _start_column_selection(self):
        """Startar markering av kolumn."""
        self.pdf_viewer.set_selection_mode("column")
    
    def _start_row_selection(self):
        """Startar markering av rad."""
        self.pdf_viewer.set_selection_mode("row")
    
    def _on_table_selected(self, rect: QRect):
        """Hanterar när tabellområde markerats."""
        self.pdf_viewer.set_selection_mode(None)
        
        # Konvertera till normaliserade koordinater
        coords = {
            "x": rect.x() / 1000.0,
            "y": rect.y() / 1000.0,
            "width": rect.width() / 1000.0,
            "height": rect.height() / 1000.0
        }
        self.table_coords = coords
        
        self.table_coords_label.setText(
            f"X: {coords['x']:.3f}, Y: {coords['y']:.3f}\n"
            f"Bredd: {coords['width']:.3f}, Höjd: {coords['height']:.3f}"
        )
        
        # Aktivera kolumn- och radmarkering
        self.mark_column_btn.setEnabled(True)
        self.mark_row_btn.setEnabled(True)
    
    def _on_column_selected_dialog(self, rect: QRect):
        """Hanterar när kolumn markerats."""
        self.pdf_viewer.set_selection_mode(None)
        
        # Konvertera till normaliserade koordinater
        coords = {
            "x": rect.x() / 1000.0,
            "y": self.table_coords.get("y", 0),
            "width": rect.width() / 1000.0,
            "height": self.table_coords.get("height", 0)
        }
        
        # Lägg till kolumn
        col_index = len(self.column_mappings)
        col_mapping = {
            "name": f"Kolumn {col_index + 1}",
            "coords": coords,
            "index": col_index
        }
        self.column_mappings.append(col_mapping)
        
        # Uppdatera listan
        item = QListWidgetItem(f"{col_index + 1}. {col_mapping['name']}")
        item.setData(Qt.UserRole, col_index)
        self.column_list.addItem(item)
        
        # Uppdatera PDF-visare
        self._update_pdf_viewer_mappings()
        
        # Aktivera uppdatering
        self.update_preview_btn.setEnabled(True)
    
    def _on_row_selected_dialog(self, rect: QRect):
        """Hanterar när rad markerats."""
        self.pdf_viewer.set_selection_mode(None)
        
        # Konvertera till normaliserade koordinater
        coords = {
            "x": self.table_coords.get("x", 0),
            "y": rect.y() / 1000.0,
            "width": self.table_coords.get("width", 0),
            "height": rect.height() / 1000.0
        }
        
        # Lägg till rad
        row_index = len(self.row_mappings)
        row_mapping = {
            "coords": coords,
            "index": row_index,
            "is_header": False
        }
        self.row_mappings.append(row_mapping)
        
        # Uppdatera listan
        item = QListWidgetItem(f"Rad {row_index + 1}")
        if row_mapping["is_header"]:
            item.setText(f"📋 {item.text()} (Header)")
        item.setData(Qt.UserRole, row_index)
        self.row_list.addItem(item)
        
        # Uppdatera PDF-visare
        self._update_pdf_viewer_mappings()
        
        # Aktivera uppdatering
        self.update_preview_btn.setEnabled(True)
    
    def _on_column_selected(self):
        """Hanterar val av kolumn i listan."""
        current_item = self.column_list.currentItem()
        if current_item:
            col_index = current_item.data(Qt.UserRole)
            if col_index is not None and col_index < len(self.column_mappings):
                col_mapping = self.column_mappings[col_index]
                self.column_name_input.setText(col_mapping.get("name", ""))
    
    def _on_row_selected(self):
        """Hanterar val av rad i listan."""
        current_item = self.row_list.currentItem()
        if current_item:
            self.set_header_btn.setEnabled(True)
            self.remove_row_btn.setEnabled(True)
        else:
            self.set_header_btn.setEnabled(False)
            self.remove_row_btn.setEnabled(False)
    
    def _update_column_name(self, text: str):
        """Uppdaterar namn för vald kolumn."""
        current_item = self.column_list.currentItem()
        if current_item:
            col_index = current_item.data(Qt.UserRole)
            if col_index is not None and col_index < len(self.column_mappings):
                self.column_mappings[col_index]["name"] = text
                current_item.setText(f"{col_index + 1}. {text}")
    
    def _remove_selected_column(self):
        """Tar bort vald kolumn."""
        current_item = self.column_list.currentItem()
        if not current_item:
            return
        
        col_index = current_item.data(Qt.UserRole)
        if col_index is None:
            return
        
        reply = QMessageBox.question(
            self,
            "Bekräfta",
            f"Vill du ta bort kolumn '{self.column_mappings[col_index].get('name')}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Ta bort kolumn
            self.column_mappings.pop(col_index)
            
            # Uppdatera index
            for i, col in enumerate(self.column_mappings):
                col["index"] = i
            
            # Uppdatera lista
            self.column_list.clear()
            for i, col in enumerate(self.column_mappings):
                item = QListWidgetItem(f"{i + 1}. {col['name']}")
                item.setData(Qt.UserRole, i)
                self.column_list.addItem(item)
            
            # Uppdatera PDF-visare
            self._update_pdf_viewer_mappings()
            
            # Rensa extraherade celler för denna kolumn
            self.extracted_cells = {
                (r, c): v for (r, c), v in self.extracted_cells.items()
                if c != col_index
            }
            
            # Uppdatera förhandsvisning
            self._update_preview()
    
    def _remove_selected_row(self):
        """Tar bort vald rad."""
        current_item = self.row_list.currentItem()
        if not current_item:
            return
        
        row_index = current_item.data(Qt.UserRole)
        if row_index is None:
            return
        
        reply = QMessageBox.question(
            self,
            "Bekräfta",
            f"Vill du ta bort rad {row_index + 1}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Ta bort rad
            self.row_mappings.pop(row_index)
            
            # Om det var header-rad, rensa
            if self.header_row_index == row_index:
                self.header_row_index = None
            
            # Uppdatera index
            for i, row in enumerate(self.row_mappings):
                row["index"] = i
                if self.header_row_index == i + 1:
                    self.header_row_index = i
            
            # Uppdatera lista
            self.row_list.clear()
            for i, row in enumerate(self.row_mappings):
                item_text = f"Rad {i + 1}"
                if row.get("is_header", False) or self.header_row_index == i:
                    item_text = f"📋 {item_text} (Header)"
                    row["is_header"] = True
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, i)
                self.row_list.addItem(item)
            
            # Uppdatera PDF-visare
            self._update_pdf_viewer_mappings()
            
            # Rensa extraherade celler för denna rad
            self.extracted_cells = {
                (r, c): v for (r, c), v in self.extracted_cells.items()
                if r != row_index
            }
            
            # Uppdatera förhandsvisning
            self._update_preview()
    
    def _set_header_row(self):
        """Sätter vald rad som header-rad."""
        current_item = self.row_list.currentItem()
        if not current_item:
            return
        
        row_index = current_item.data(Qt.UserRole)
        if row_index is None:
            return
        
        # Sätt header
        self.header_row_index = row_index
        for i, row in enumerate(self.row_mappings):
            row["is_header"] = (i == row_index)
        
        # Uppdatera lista
        for i in range(self.row_list.count()):
            item = self.row_list.item(i)
            item_row_index = item.data(Qt.UserRole)
            if item_row_index == row_index:
                item.setText(f"📋 Rad {item_row_index + 1} (Header)")
            else:
                item.setText(f"Rad {item_row_index + 1}")
    
    def _update_pdf_viewer_mappings(self):
        """Uppdaterar mappningar i PDF-visaren."""
        # Konvertera kolumner till format för PDFViewer
        column_mappings_display = []
        for col in self.column_mappings:
            column_mappings_display.append({
                "name": col.get("name", ""),
                "coords": col.get("coords", {}),
                "index": col.get("index", 0)
            })
        
        # Konvertera rader till format för PDFViewer
        row_mappings_display = []
        for row in self.row_mappings:
            row_mappings_display.append({
                "coords": row.get("coords", {}),
                "index": row.get("index", 0),
                "is_header": row.get("is_header", False)
            })
        
        self.pdf_viewer.set_column_mappings(column_mappings_display)
        self.pdf_viewer.set_row_mappings(row_mappings_display)
    
    def _update_preview(self):
        """Uppdaterar förhandsvisning med extraherade värden."""
        if not self.column_mappings or not self.row_mappings:
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(0)
            return
        
        if not self.text_extractor or not self.pdf_path:
            QMessageBox.warning(
                self,
                "Varning",
                "TextExtractor eller PDF-sökväg saknas. Kan inte uppdatera förhandsvisning."
            )
            return
        
        # Sortera kolumner och rader
        sorted_columns = sorted(self.column_mappings, key=lambda c: c.get("index", 0))
        sorted_rows = sorted(self.row_mappings, key=lambda r: r.get("coords", {}).get("y", 0))
        
        # Sätt upp tabell
        self.preview_table.setColumnCount(len(sorted_columns))
        self.preview_table.setRowCount(len(sorted_rows))
        
        # Sätt kolumnnamn
        column_names = [col.get("name", f"Kolumn {i+1}") for i, col in enumerate(sorted_columns)]
        self.preview_table.setHorizontalHeaderLabels(column_names)
        
        # Extrahera värden från varje cell
        pdf_width, pdf_height = self.pdf_dimensions
        
        for row_idx, row_info in enumerate(sorted_rows):
            row_coords = row_info.get("coords", {})
            row_y = row_coords.get("y", 0)
            row_height = row_coords.get("height", 0)
            
            for col_idx, col_info in enumerate(sorted_columns):
                col_coords = col_info.get("coords", {})
                
                # Beräkna cellkoordinater
                cell_coords = {
                    "x": col_coords.get("x", 0),
                    "y": row_y,
                    "width": col_coords.get("width", 0),
                    "height": row_height
                }
                
                # Extrahera text från cell
                cell_value = ""
                if (row_idx, col_idx) in self.extracted_cells:
                    # Använd redigerat värde om det finns
                    cell_value = self.extracted_cells[(row_idx, col_idx)]
                else:
                    # Extrahera från PDF
                    try:
                        cell_value = self.text_extractor.extract_table_cell(
                            self.pdf_path,
                            0,
                            cell_coords,
                            pdf_width,
                            pdf_height,
                            self.ocr_language
                        )
                        self.extracted_cells[(row_idx, col_idx)] = cell_value
                    except Exception as e:
                        cell_value = f"[Fel: {str(e)}]"
                
                # Skapa tabellitem
                item = QTableWidgetItem(cell_value)
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                
                # Färgkodning
                if not cell_value.strip():
                    item.setBackground(QColor(255, 255, 200))  # Gul = tom
                elif "[Fel" in cell_value:
                    item.setBackground(QColor(255, 200, 200))  # Röd = fel
                else:
                    item.setBackground(QColor(200, 255, 200))  # Grön = OK
                
                # Markera header-rad
                if row_info.get("is_header", False):
                    item.setBackground(QColor(200, 230, 255))  # Blå = header
                
                self.preview_table.setItem(row_idx, col_idx, item)
        
        # Aktivera OK-knapp om vi har minst en kolumn
        if len(sorted_columns) > 0:
            self.ok_btn.setEnabled(True)
    
    def _on_cell_edited(self, item: QTableWidgetItem):
        """Hanterar redigering av cell i förhandsvisning."""
        row = item.row()
        col = item.column()
        value = item.text()
        
        # Spara redigerat värde
        self.extracted_cells[(row, col)] = value
        
        # Uppdatera färg
        if not value.strip():
            item.setBackground(QColor(255, 255, 200))  # Gul = tom
        else:
            item.setBackground(QColor(200, 255, 200))  # Grön = OK
    
    def _validate_and_accept(self):
        """Validerar och accepterar dialog."""
        if not self.column_mappings:
            QMessageBox.warning(
                self,
                "Inga kolumner",
                "Du måste mappa minst en kolumn."
            )
            return
        
        # Validera att alla kolumner har namn
        for col in self.column_mappings:
            if not col.get("name", "").strip():
                QMessageBox.warning(
                    self,
                    "Saknade namn",
                    f"Kolumn {col.get('index', 0) + 1} saknar namn. Ange ett namn för alla kolumner."
                )
                return
        
        if not self.row_mappings:
            QMessageBox.warning(
                self,
                "Inga rader",
                "Du måste mappa minst en rad."
            )
            return
        
        self.accept()
    
    def get_result(self) -> tuple:
        """
        Returnerar mappningsresultat.
        
        Returns:
            Tuple med (column_mappings, row_coords, header_row_coords, has_header_row)
        """
        # Konvertera till format för TableMapping
        column_mappings = []
        for col in sorted(self.column_mappings, key=lambda c: c.get("index", 0)):
            column_mappings.append({
                "name": col.get("name", ""),
                "index": col.get("index", 0),
                "coords": col.get("coords", {})
            })
        
        # Konvertera rader
        row_coords = []
        header_row_coords = None
        
        sorted_rows = sorted(self.row_mappings, key=lambda r: r.get("coords", {}).get("y", 0))
        for row_info in sorted_rows:
            row_coords.append({
                "y": row_info.get("coords", {}).get("y", 0),
                "height": row_info.get("coords", {}).get("height", 0),
                "index": row_info.get("index", 0)
            })
            
            # Sätt header-koordinater
            if row_info.get("is_header", False) or self.header_row_index == row_info.get("index", -1):
                header_row_coords = row_info.get("coords", {})
        
        has_header = header_row_coords is not None
        
        return (column_mappings, row_coords, header_row_coords, has_header)
