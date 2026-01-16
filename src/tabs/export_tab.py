"""
Export Tab - Exporterar extraherad data till Excel, CSV eller JSON.
"""

import json
import csv
from pathlib import Path
from typing import List, Dict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QFileDialog, QMessageBox, QGroupBox,
    QHeaderView, QAbstractItemView, QCheckBox
)
from PySide6.QtCore import Qt
import pandas as pd
from ..core.document_manager import DocumentManager
from ..core.template_manager import TemplateManager


class ExportTab(QWidget):
    """Flik för export av extraherad data."""
    
    def __init__(
        self,
        document_manager: DocumentManager,
        template_manager: TemplateManager
    ):
        super().__init__()
        self.document_manager = document_manager
        self.template_manager = template_manager
        
        self._setup_ui()
        self._refresh_clusters()
    
    def _setup_ui(self):
        """Skapar UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("📦 Extract & Export")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(header)
        
        # Klusteröversikt
        cluster_group = QGroupBox("Klusteröversikt")
        cluster_layout = QVBoxLayout()
        
        self.cluster_table = QTableWidget()
        self.cluster_table.setColumnCount(4)
        self.cluster_table.setHorizontalHeaderLabels([
            "Välj", "Kluster", "Status", "Referensfil"
        ])
        self.cluster_table.horizontalHeader().setStretchLastSection(True)
        self.cluster_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        cluster_layout.addWidget(self.cluster_table)
        
        cluster_group.setLayout(cluster_layout)
        layout.addWidget(cluster_group)
        
        # Export-knappar
        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        
        self.export_selected_btn = QPushButton("📦 Exportera Valt Kluster")
        self.export_selected_btn.clicked.connect(self._export_selected_cluster)
        btn_layout.addWidget(self.export_selected_btn)
        
        self.export_all_btn = QPushButton("🚀 Exportera Alla Valda Kluster")
        self.export_all_btn.clicked.connect(self._export_all_selected)
        btn_layout.addWidget(self.export_all_btn)
        
        export_layout.addLayout(btn_layout)
        
        # Format-val
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        
        self.format_excel = QCheckBox("Excel (.xlsx)")
        self.format_excel.setChecked(True)
        format_layout.addWidget(self.format_excel)
        
        self.format_csv = QCheckBox("CSV (.csv)")
        format_layout.addWidget(self.format_csv)
        
        self.format_json = QCheckBox("JSON (.json)")
        format_layout.addWidget(self.format_json)
        
        format_layout.addStretch()
        export_layout.addLayout(format_layout)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        # Status
        self.status_label = QLabel("Välj kluster och klicka på export-knappen.")
        layout.addWidget(self.status_label)
    
    def _refresh_clusters(self):
        """Uppdaterar klusterlistan."""
        clusters = self.document_manager.clusters
        
        self.cluster_table.setRowCount(len(clusters))
        
        for row, (cluster_id, file_paths) in enumerate(clusters.items()):
            # Checkbox för val
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            self.cluster_table.setCellWidget(row, 0, checkbox)
            
            # Kluster-ID
            self.cluster_table.setItem(row, 1, QTableWidgetItem(cluster_id))
            
            # Status
            template = self.template_manager.get_template(cluster_id)
            if template:
                status = f"✓ Mall klar ({len(template.field_mappings)} fält, {len(template.table_mappings)} tabeller)"
            else:
                status = "⚠ Mall saknas"
            self.cluster_table.setItem(row, 2, QTableWidgetItem(status))
            
            # Referensfil
            ref_doc = self.document_manager.get_reference_document(cluster_id)
            if ref_doc:
                ref_file = ref_doc.file_path.split("/")[-1] if "/" in ref_doc.file_path else ref_doc.file_path.split("\\")[-1]
            else:
                ref_file = "Saknas"
            self.cluster_table.setItem(row, 3, QTableWidgetItem(ref_file))
    
    def _get_selected_clusters(self) -> List[str]:
        """Hämtar valda kluster."""
        selected = []
        for row in range(self.cluster_table.rowCount()):
            checkbox = self.cluster_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                cluster_id = self.cluster_table.item(row, 1).text()
                selected.append(cluster_id)
        return selected
    
    def _export_selected_cluster(self):
        """Exporterar valt kluster."""
        selected = self._get_selected_clusters()
        if not selected:
            QMessageBox.warning(self, "Inget valt", "Välj minst ett kluster.")
            return
        
        if len(selected) > 1:
            QMessageBox.warning(
                self,
                "För många valda",
                "Välj endast ett kluster för denna funktion."
            )
            return
        
        cluster_id = selected[0]
        self._export_cluster(cluster_id)
    
    def _export_all_selected(self):
        """Exporterar alla valda kluster."""
        selected = self._get_selected_clusters()
        if not selected:
            QMessageBox.warning(self, "Inget valt", "Välj minst ett kluster.")
            return
        
        for cluster_id in selected:
            self._export_cluster(cluster_id)
        
        QMessageBox.information(
            self,
            "Klar",
            f"Exporterat {len(selected)} kluster."
        )
    
    def _export_cluster(self, cluster_id: str):
        """Exporterar ett kluster."""
        cluster_docs = self.document_manager.get_cluster_documents(cluster_id)
        
        if not cluster_docs:
            QMessageBox.warning(self, "Inga dokument", "Klustret innehåller inga dokument.")
            return
        
        # Välj filplats
        base_path, _ = QFileDialog.getSaveFileName(
            self,
            "Spara som",
            f"{cluster_id}.xlsx",
            "Excel Files (*.xlsx);;CSV Files (*.csv);;JSON Files (*.json)"
        )
        
        if not base_path:
            return
        
        # Förbered data
        export_data = []
        
        for doc in cluster_docs:
            if doc.status != "mapped":
                continue
            
            # Hämta fält
            fields = doc.extracted_data.get("fields", {})
            
            # Hämta tabeller
            tables = doc.extracted_data.get("tables", {})
            
            # Skapa en rad per tabellrad (eller en rad om inga tabeller)
            if tables:
                for table_name, rows in tables.items():
                    for row in rows:
                        row_data = {
                            "Källfil": doc.file_path,
                            "Kluster": cluster_id,
                            **fields,
                            **row  # Tabellkolumner
                        }
                        export_data.append(row_data)
            else:
                # Inga tabeller, bara fält
                row_data = {
                    "Källfil": doc.file_path,
                    "Kluster": cluster_id,
                    **fields
                }
                export_data.append(row_data)
        
        if not export_data:
            QMessageBox.warning(
                self,
                "Ingen data",
                "Ingen data att exportera. Kontrollera att dokumenten är mappade."
            )
            return
        
        # Exportera baserat på filtyp
        file_path = Path(base_path)
        
        if self.format_excel.isChecked() or file_path.suffix == ".xlsx":
            self._export_excel(export_data, base_path)
        
        if self.format_csv.isChecked() or file_path.suffix == ".csv":
            csv_path = base_path.replace(".xlsx", ".csv").replace(".json", ".csv")
            self._export_csv(export_data, csv_path)
        
        if self.format_json.isChecked() or file_path.suffix == ".json":
            json_path = base_path.replace(".xlsx", ".json").replace(".csv", ".json")
            self._export_json(export_data, json_path)
        
        QMessageBox.information(
            self,
            "Klar",
            f"Exporterat {len(export_data)} rader från {len(cluster_docs)} dokument."
        )
    
    def _export_excel(self, data: List[Dict], file_path: str):
        """Exporterar till Excel."""
        df = pd.DataFrame(data)
        df.to_excel(file_path, index=False, engine='openpyxl')
    
    def _export_csv(self, data: List[Dict], file_path: str):
        """Exporterar till CSV."""
        if not data:
            return
        
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
    
    def _export_json(self, data: List[Dict], file_path: str):
        """Exporterar till JSON."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
