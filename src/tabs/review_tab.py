"""
Review Tab - Granskar och korrigerar extraherad data.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QMessageBox, QGroupBox, QTextEdit,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from typing import Optional, List
from ..core.document_manager import DocumentManager, PDFDocument
from ..core.template_manager import TemplateManager
from ..core.clustering_engine import ClusteringEngine
from ..core.extraction_engine import ExtractionEngine
from ..core.pdf_processor import PDFProcessor


class ReviewTab(QWidget):
    """Flik för granskning och korrigering."""
    
    review_completed = Signal(str)  # cluster_id
    
    def __init__(
        self,
        document_manager: DocumentManager,
        template_manager: TemplateManager
    ):
        super().__init__()
        self.document_manager = document_manager
        self.template_manager = template_manager
        self.clustering_engine = ClusteringEngine()
        self.pdf_processor = PDFProcessor()
        self.extraction_engine = ExtractionEngine(self.pdf_processor)
        
        self.current_cluster_id: Optional[str] = None
        self.current_doc: Optional[PDFDocument] = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Skapar UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("👁️ Review")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(header)
        
        # Kontroller
        control_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Uppdatera")
        self.refresh_btn.clicked.connect(self._refresh_review)
        control_layout.addWidget(self.refresh_btn)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # Dokumentlista
        doc_group = QGroupBox("Dokument")
        doc_layout = QVBoxLayout()
        
        self.doc_table = QTableWidget()
        self.doc_table.setColumnCount(5)
        self.doc_table.setHorizontalHeaderLabels([
            "Status", "Fil", "Fält", "Tabellrader", "Åtgärd"
        ])
        self.doc_table.horizontalHeader().setStretchLastSection(True)
        self.doc_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.doc_table.itemDoubleClicked.connect(self._on_doc_double_clicked)
        doc_layout.addWidget(self.doc_table)
        
        doc_group.setLayout(doc_layout)
        layout.addWidget(doc_group)
        
        # Detaljvy
        detail_group = QGroupBox("Detaljer")
        detail_layout = QVBoxLayout()
        
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text)
        
        detail_btn_layout = QHBoxLayout()
        self.correct_btn = QPushButton("🔧 Korrigera Mappning")
        self.correct_btn.clicked.connect(self._correct_mapping)
        self.correct_btn.setEnabled(False)
        detail_btn_layout.addWidget(self.correct_btn)
        
        detail_btn_layout.addStretch()
        detail_layout.addLayout(detail_btn_layout)
        
        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)
        
        # Status
        self.status_label = QLabel("Välj ett kluster från 'Document Types' och klicka 'Granska' efter mappning.")
        layout.addWidget(self.status_label)
    
    def load_cluster(self, cluster_id: str):
        """Laddar ett kluster för granskning."""
        self.current_cluster_id = cluster_id
        self._refresh_review()
    
    def _refresh_review(self):
        """Uppdaterar granskningslistan."""
        if not self.current_cluster_id:
            # Visa alla mappade dokument
            all_docs = self.document_manager.get_all_documents()
            cluster_docs = [d for d in all_docs if d.status == "mapped"]
        else:
            cluster_docs = self.document_manager.get_cluster_documents(
                self.current_cluster_id
            )
        
        self.doc_table.setRowCount(len(cluster_docs))
        
        for row, doc in enumerate(cluster_docs):
            # Status
            status_icon = "✅" if doc.status == "mapped" else "❌"
            status_item = QTableWidgetItem(status_icon)
            status_item.setData(Qt.UserRole, doc.file_path)
            self.doc_table.setItem(row, 0, status_item)
            
            # Fil
            file_name = doc.file_path.split("/")[-1] if "/" in doc.file_path else doc.file_path.split("\\")[-1]
            self.doc_table.setItem(row, 1, QTableWidgetItem(file_name))
            
            # Antal fält
            field_count = len(doc.extracted_data.get("fields", {}))
            self.doc_table.setItem(row, 2, QTableWidgetItem(str(field_count)))
            
            # Antal tabellrader
            total_rows = sum(
                len(rows) for rows in doc.extracted_data.get("tables", {}).values()
            )
            self.doc_table.setItem(row, 3, QTableWidgetItem(str(total_rows)))
            
            # Åtgärd
            action_btn = QPushButton("🔧 Korrigera")
            action_btn.clicked.connect(
                lambda checked, fp=doc.file_path: self._select_document(fp)
            )
            self.doc_table.setCellWidget(row, 4, action_btn)
        
        self.status_label.setText(f"Visar {len(cluster_docs)} dokument")
    
    def _on_doc_double_clicked(self, item: QTableWidgetItem):
        """Hanterar dubbelklick på dokument."""
        file_path = item.data(Qt.UserRole)
        if file_path:
            self._select_document(file_path)
    
    def _select_document(self, file_path: str):
        """Väljer ett dokument för detaljvisning."""
        doc = self.document_manager.get_document(file_path)
        if not doc:
            return
        
        self.current_doc = doc
        self.correct_btn.setEnabled(True)
        
        # Visa detaljer
        detail_text = f"Fil: {doc.file_path}\n"
        detail_text += f"Status: {doc.status}\n"
        detail_text += f"Kluster: {doc.cluster_id}\n\n"
        
        detail_text += "Extraherade fält:\n"
        for key, value in doc.extracted_data.get("fields", {}).items():
            detail_text += f"  {key}: {value}\n"
        
        detail_text += "\nExtraherade tabeller:\n"
        for table_name, rows in doc.extracted_data.get("tables", {}).items():
            detail_text += f"\n{table_name} ({len(rows)} rader):\n"
            if rows:
                # Visa första raden som exempel
                first_row = rows[0]
                detail_text += "  Kolumner: " + ", ".join(first_row.keys()) + "\n"
                detail_text += f"  Första rad: {first_row}\n"
        
        self.detail_text.setText(detail_text)
    
    def _correct_mapping(self):
        """Korrigerar mappningen för ett dokument."""
        if not self.current_doc:
            return
        
        # Emit signal för att öppna mapping-fliken
        # (Detta hanteras av main_window)
        self.review_completed.emit(self.current_doc.cluster_id or "")
        
        # Hitta liknande dokument
        all_docs = self.document_manager.get_all_documents()
        similar_docs = self.clustering_engine.find_similar_documents(
            self.current_doc,
            all_docs,
            threshold=0.7
        )
        
        if similar_docs:
            reply = QMessageBox.question(
                self,
                "Liknande dokument",
                f"Hittade {len(similar_docs)} liknande dokument. "
                "Vill du applicera samma korrigering på dem?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Applicera korrigering på liknande dokument
                template = self.template_manager.get_template(
                    self.current_doc.cluster_id or ""
                )
                if template:
                    for similar_doc in similar_docs:
                        try:
                            result = self.extraction_engine.extract_data(
                                similar_doc.file_path,
                                template
                            )
                            similar_doc.extracted_data = result
                            similar_doc.status = "mapped"
                            self.document_manager.update_document(similar_doc)
                        except Exception as e:
                            similar_doc.status = "error"
                            print(f"Fel vid re-extraktion: {e}")
                    
                    QMessageBox.information(
                        self,
                        "Klar",
                        f"Korrigering applicerad på {len(similar_docs)} dokument."
                    )
                    self._refresh_review()
