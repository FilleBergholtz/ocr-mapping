"""
Table Mapping Dialog - Dialog för mappning av tabellkolumner.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QLineEdit, QHeaderView,
    QMessageBox, QGroupBox, QTextEdit, QSpinBox, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from typing import List, Dict, Optional


class TableMappingDialog(QDialog):
    """Dialog för mappning av tabellkolumner."""
    
    def __init__(self, parent=None, table_rows: List[List[str]] = None):
        super().__init__(parent)
        self.setWindowTitle("Mappa Tabell - Kolumner")
        self.setModal(True)
        self.setMinimumSize(800, 600)
        
        self.table_rows = table_rows or []
        self.column_mappings: List[Dict] = []
        self.column_inputs: List = []  # Initialisera tidigt för att undvika AttributeError
        self.detected_header_row: Optional[int] = None
        
        self._setup_ui()
        self._populate_table()
        self._detect_header_row()
    
    def _setup_ui(self):
        """Skapar UI."""
        layout = QVBoxLayout(self)
        
        # Instruktioner
        info_label = QLabel(
            "<b>Instruktioner:</b><br>"
            "1. Tabellen visar extraherade rader från PDF:en<br>"
            "2. Systemet försöker automatiskt identifiera header-rad<br>"
            "3. För varje kolumn, ange kolumnnamn (förslag kommer från header-rad om den hittas)<br>"
            "4. Du kan manuellt välja header-rad om automatisk detektering inte fungerar"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Header-rad val
        header_group = QGroupBox("Header-rad")
        header_layout = QHBoxLayout()
        
        header_layout.addWidget(QLabel("Header-rad index:"))
        self.header_row_spinbox = QSpinBox()
        self.header_row_spinbox.setMinimum(0)
        self.header_row_spinbox.setMaximum(10)
        self.header_row_spinbox.setValue(0)
        self.header_row_spinbox.valueChanged.connect(self._on_header_row_changed)
        header_layout.addWidget(self.header_row_spinbox)
        
        self.has_header_checkbox = QCheckBox("Tabellen har header-rad")
        self.has_header_checkbox.setChecked(True)
        self.has_header_checkbox.toggled.connect(self._on_has_header_toggled)
        header_layout.addWidget(self.has_header_checkbox)
        
        header_layout.addStretch()
        header_group.setLayout(header_layout)
        layout.addWidget(header_group)
        
        # Tabell med extraherade rader
        table_group = QGroupBox("Extraherade rader från tabellen")
        table_layout = QVBoxLayout()
        
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(10)  # Max 10 kolumner för nu
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.setAlternatingRowColors(True)
        table_layout.addWidget(self.table_widget)
        
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)
        
        # Kolumnmappning
        mapping_group = QGroupBox("Kolumnmappning")
        mapping_layout = QVBoxLayout()
        
        mapping_info = QLabel(
            "Ange kolumnnamn för varje kolumn. Lämna tomt för kolumner du inte vill inkludera."
        )
        mapping_layout.addWidget(mapping_info)
        
        self.column_names_layout = QVBoxLayout()
        mapping_layout.addLayout(self.column_names_layout)
        
        mapping_group.setLayout(mapping_layout)
        layout.addWidget(mapping_group)
        
        # Knappar
        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self._validate_and_accept)
        self.cancel_btn = QPushButton("Avbryt")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
    
    def _populate_table(self):
        """Fyller tabellen med extraherade rader."""
        if not self.table_rows:
            self.table_widget.setRowCount(0)
            return
        
        # Hitta max antal kolumner
        max_cols = max(len(row) for row in self.table_rows) if self.table_rows else 0
        max_cols = min(max_cols, 10)  # Begränsa till 10 kolumner
        
        self.table_widget.setColumnCount(max_cols)
        self.table_widget.setRowCount(len(self.table_rows))
        
        # Fyll i data
        for row_idx, row_data in enumerate(self.table_rows):
            for col_idx in range(max_cols):
                if col_idx < len(row_data):
                    item = QTableWidgetItem(row_data[col_idx])
                else:
                    item = QTableWidgetItem("")
                self.table_widget.setItem(row_idx, col_idx, item)
        
        # Skapa kolumnnamn-inputs
        self.column_inputs = []
        for col_idx in range(max_cols):
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(f"Kolumn {col_idx + 1}:"))
            
            col_input = QLineEdit()
            # Försök identifiera kolumnnamn från header-rad (om den hittats)
            header_row_idx = self.header_row_spinbox.value() if self.has_header_checkbox.isChecked() else -1
            if header_row_idx >= 0 and header_row_idx < len(self.table_rows) and col_idx < len(self.table_rows[header_row_idx]):
                suggested_name = self.table_rows[header_row_idx][col_idx].strip()
                if suggested_name:
                    # Auto-fylla om det ser ut som ett kolumnnamn (inte för långt, inte nummer)
                    if len(suggested_name) < 50 and not suggested_name.replace('.', '').replace(',', '').strip().isdigit():
                        col_input.setText(suggested_name)
                    else:
                        col_input.setPlaceholderText(f"T.ex. '{suggested_name[:30]}'")
            
            self.column_inputs.append(col_input)
            row_layout.addWidget(col_input)
            row_layout.addStretch()
            
            self.column_names_layout.addLayout(row_layout)
    
    def _validate_and_accept(self):
        """Validerar och accepterar dialog."""
        # Skapa kolumnmappningar
        self.column_mappings = []
        
        for col_idx, col_input in enumerate(self.column_inputs):
            col_name = col_input.text().strip()
            if col_name:
                self.column_mappings.append({
                    "index": col_idx,
                    "name": col_name
                })
        
        if not self.column_mappings:
            QMessageBox.warning(
                self,
                "Inga kolumner",
                "Du måste ange minst ett kolumnnamn."
            )
            return
        
        self.accept()
    
    def get_result(self) -> tuple:
        """
        Returnerar kolumnmappningar och header-rad information.
        
        Returns:
            Tuple med (column_mappings, has_header_row, header_row_index)
        """
        has_header = self.has_header_checkbox.isChecked()
        header_row_idx = self.header_row_spinbox.value() if has_header else -1
        return (self.column_mappings, has_header, header_row_idx)
    
    def _detect_header_row(self):
        """
        Försöker automatiskt identifiera header-rad baserat på mönster.
        
        Kriterier:
        - Header-rad innehåller ofta unika värden (inte siffror eller tomma strängar)
        - Header-rad är ofta en av de första raderna
        - Header-rader har ofta fler kolumner än data-rader
        """
        if not self.table_rows or len(self.table_rows) < 2:
            self.detected_header_row = 0 if self.table_rows else None
            if self.detected_header_row is not None:
                self.header_row_spinbox.setValue(self.detected_header_row)
            return
        
        # Försök identifiera header-rad baserat på mönster
        best_header_candidate = 0
        best_score = -1
        
        # Analysera första 3 raderna (header är ofta i början)
        for row_idx in range(min(3, len(self.table_rows))):
            row = self.table_rows[row_idx]
            if not row:
                continue
            
            score = 0
            
            # Kriterium 1: Header innehåller ofta text (inte bara siffror)
            text_count = 0
            for cell in row:
                cell_str = cell.strip() if cell else ""
                # Räkna celler som ser ut som text (inte bara siffror/datum)
                if cell_str and not cell_str.replace('.', '').replace(',', '').replace('-', '').replace(':', '').strip().isdigit():
                    text_count += 1
            
            score += text_count * 2  # Text-celler är stark indikation på header
            
            # Kriterium 2: Header har ofta fler icke-tomma kolumner
            non_empty_count = sum(1 for cell in row if cell and cell.strip())
            score += non_empty_count
            
            # Kriterium 3: Header är ofta första raden
            if row_idx == 0:
                score += 3
            
            # Kriterium 4: Header-celler är ofta kortare (namn, inte data)
            avg_length = sum(len(cell) for cell in row if cell) / max(len(row), 1)
            if avg_length < 20:  # Korta värden = mer troligt header
                score += 2
            
            if score > best_score:
                best_score = score
                best_header_candidate = row_idx
        
        self.detected_header_row = best_header_candidate
        if self.has_header_checkbox.isChecked():
            self.header_row_spinbox.setValue(self.detected_header_row)
            # Markera header-rad visuellt i tabellen
            self._highlight_header_row()
    
    def _highlight_header_row(self):
        """Markerar header-rad visuellt i tabellen."""
        header_row_idx = self.header_row_spinbox.value() if self.has_header_checkbox.isChecked() else -1
        if header_row_idx < 0 or header_row_idx >= self.table_widget.rowCount():
            return
        
        # Markera header-rad med annan bakgrundsfärg
        for col_idx in range(self.table_widget.columnCount()):
            item = self.table_widget.item(header_row_idx, col_idx)
            if item:
                item.setBackground(QColor(200, 230, 255))  # Ljusblå bakgrund
                item.setForeground(QColor(0, 0, 0))  # Svart text
    
    def _on_header_row_changed(self, value: int):
        """Hanterar när header-rad ändras."""
        # Återställ färger för alla rader
        for row_idx in range(self.table_widget.rowCount()):
            for col_idx in range(self.table_widget.columnCount()):
                item = self.table_widget.item(row_idx, col_idx)
                if item:
                    item.setBackground(QColor(255, 255, 255))  # Vit bakgrund
                    item.setForeground(QColor(0, 0, 0))  # Svart text
        
        # Uppdatera kolumnnamn-förslag från ny header-rad
        if self.has_header_checkbox.isChecked() and value < len(self.table_rows):
            for col_idx, col_input in enumerate(self.column_inputs):
                if col_idx < len(self.table_rows[value]):
                    suggested_name = self.table_rows[value][col_idx].strip()
                    if suggested_name and not col_input.text().strip():
                        # Uppdatera endast om input är tom
                        if len(suggested_name) < 50 and not suggested_name.replace('.', '').replace(',', '').strip().isdigit():
                            col_input.setText(suggested_name)
                        else:
                            col_input.setPlaceholderText(f"T.ex. '{suggested_name[:30]}'")
        
        # Markera ny header-rad
        self._highlight_header_row()
    
    def _on_has_header_toggled(self, checked: bool):
        """Hanterar när has_header checkbox ändras."""
        self.header_row_spinbox.setEnabled(checked)
        if checked:
            self.header_row_spinbox.setValue(self.detected_header_row or 0)
            self._highlight_header_row()
        else:
            # Återställ färger
            for row_idx in range(self.table_widget.rowCount()):
                for col_idx in range(self.table_widget.columnCount()):
                    item = self.table_widget.item(row_idx, col_idx)
                    if item:
                        item.setBackground(QColor(255, 255, 255))
                        item.setForeground(QColor(0, 0, 0))
