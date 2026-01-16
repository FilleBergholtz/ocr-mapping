"""
Table Mapping Dialog - Dialog för mappning av tabellkolumner.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QLineEdit, QHeaderView,
    QMessageBox, QGroupBox, QTextEdit
)
from PySide6.QtCore import Qt
from typing import List, Dict


class TableMappingDialog(QDialog):
    """Dialog för mappning av tabellkolumner."""
    
    def __init__(self, parent=None, table_rows: List[List[str]] = None):
        super().__init__(parent)
        self.setWindowTitle("Mappa Tabell - Kolumner")
        self.setModal(True)
        self.setMinimumSize(800, 600)
        
        self.table_rows = table_rows or []
        self.column_mappings: List[Dict] = []
        
        self._setup_ui()
        self._populate_table()
    
    def _setup_ui(self):
        """Skapar UI."""
        layout = QVBoxLayout(self)
        
        # Instruktioner
        info_label = QLabel(
            "<b>Instruktioner:</b><br>"
            "1. Tabellen visar extraherade rader från PDF:en<br>"
            "2. För varje kolumn, ange kolumnnamn i första raden<br>"
            "3. Systemet identifierar automatiskt kolumnpositioner baserat på första raden"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
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
            # Försök identifiera kolumnnamn från första raden
            if self.table_rows and col_idx < len(self.table_rows[0]):
                suggested_name = self.table_rows[0][col_idx].strip()
                if suggested_name:
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
    
    def get_result(self) -> List[Dict]:
        """Returnerar kolumnmappningar."""
        return self.column_mappings
