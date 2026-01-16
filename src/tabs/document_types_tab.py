"""
Document Types Tab - Hanterar PDF-uppladdning och klustering.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QFileDialog, QProgressDialog, QMessageBox,
    QGroupBox, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QColor
from typing import List
from ..core.document_manager import DocumentManager, PDFDocument
from ..core.clustering_engine import ClusteringEngine
from ..core.template_manager import TemplateManager
from ..core.pdf_processor import (
    PDFProcessor,
    check_tesseract_available,
    check_poppler_available,
    get_tesseract_installation_guide,
    get_poppler_installation_guide
)
from ..core.logger import get_logger

logger = get_logger()


class ProcessingThread(QThread):
    """Tråd för bakgrundsbehandling av PDF:er."""
    progress = Signal(int, str)  # progress, message
    finished = Signal()
    
    def __init__(self, documents: List[PDFDocument], pdf_processor: PDFProcessor,
                 clustering_engine: ClusteringEngine):
        super().__init__()
        self.documents = documents
        self.pdf_processor = pdf_processor
        self.clustering_engine = clustering_engine
    
    def run(self):
        """Bearbetar dokument i bakgrunden."""
        total = len(self.documents)
        
        # Steg 1: Extrahera text och skapa fingeravtryck
        for i, doc in enumerate(self.documents):
            self.progress.emit(
                int((i / total) * 50),
                f"Extraherar text från {doc.file_path}..."
            )
            
            # Extrahera text
            text = self.pdf_processor.extract_text(doc.file_path)
            doc.extracted_text = text
            
            # Skapa fingeravtryck
            doc.fingerprint = self.clustering_engine.create_fingerprint(text)
            doc.status = "processed"
        
        # Steg 2: Klustra dokument
        self.progress.emit(50, "Klustrar dokument...")
        clusters = self.clustering_engine.cluster_documents(self.documents)
        
        # Steg 3: Välj referensdokument för varje kluster
        for cluster_id, file_paths in clusters.items():
            cluster_docs = [d for d in self.documents if d.file_path in file_paths]
            if cluster_docs:
                ref_doc = self.clustering_engine.find_most_complete_document(cluster_docs)
                ref_doc.is_reference = True
        
        self.progress.emit(100, "Klar!")
        self.finished.emit()


class DocumentTypesTab(QWidget):
    """Flik för hantering av dokumenttyper och kluster."""
    
    cluster_selected = Signal(str)  # cluster_id
    
    def __init__(
        self,
        document_manager: DocumentManager,
        clustering_engine: ClusteringEngine,
        template_manager: TemplateManager
    ):
        super().__init__()
        self.document_manager = document_manager
        self.clustering_engine = clustering_engine
        self.template_manager = template_manager
        self.pdf_processor = PDFProcessor()
        
        # Kontrollera dependencies
        self.tesseract_available, _ = check_tesseract_available()
        self.poppler_available, _ = check_poppler_available()
        self._dependency_warning_shown = False
        
        self._setup_ui()
        self._update_dependency_status()
        self.refresh_clusters()
    
    def _setup_ui(self):
        """Skapar UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("📄 Document Types")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(header)
        
        # Knappar
        button_layout = QHBoxLayout()
        
        self.add_pdfs_btn = QPushButton("➕ Lägg till PDF:er")
        self.add_pdfs_btn.clicked.connect(self._add_pdfs)
        button_layout.addWidget(self.add_pdfs_btn)
        
        self.scan_btn = QPushButton("🔍 Skanna")
        self.scan_btn.clicked.connect(self._scan_documents)
        self.scan_btn.setEnabled(False)
        button_layout.addWidget(self.scan_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Klusterlista
        cluster_group = QGroupBox("Kluster (Document Types)")
        cluster_layout = QVBoxLayout()
        
        self.cluster_list = QListWidget()
        self.cluster_list.itemDoubleClicked.connect(self._on_cluster_double_clicked)
        self.cluster_list.itemClicked.connect(self._on_cluster_clicked)
        cluster_layout.addWidget(self.cluster_list)
        
        # Klusterinfo
        self.cluster_info = QTextEdit()
        self.cluster_info.setReadOnly(True)
        self.cluster_info.setMaximumHeight(150)
        cluster_layout.addWidget(QLabel("Klusterinformation:"))
        cluster_layout.addWidget(self.cluster_info)
        
        cluster_group.setLayout(cluster_layout)
        layout.addWidget(cluster_group)
        
        # Dependency status
        self.dependency_status = QGroupBox("Systemstatus")
        dependency_layout = QVBoxLayout()
        
        self.dependency_info = QTextEdit()
        self.dependency_info.setReadOnly(True)
        self.dependency_info.setMaximumHeight(120)
        self.dependency_info.setStyleSheet("background-color: #f5f5f5; font-size: 11px;")
        dependency_layout.addWidget(self.dependency_info)
        
        self.dependency_status.setLayout(dependency_layout)
        layout.addWidget(self.dependency_status)
        
        # Status
        self.status_label = QLabel("Inga PDF:er laddade")
        layout.addWidget(self.status_label)
    
    def _add_pdfs(self):
        """Lägger till PDF-filer."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Välj PDF-filer",
            "",
            "PDF Files (*.pdf)"
        )
        
        if file_paths:
            docs = self.document_manager.add_documents(file_paths)
            self.status_label.setText(f"{len(docs)} PDF:er laddade. Klicka 'Skanna' för att börja.")
            # Enable scan button även om Poppler saknas (textbaserade PDF:er fungerar)
            self.scan_btn.setEnabled(True)
    
    def _scan_documents(self):
        """Skannar och klustrar dokument."""
        documents = self.document_manager.get_all_documents()
        
        if not documents:
            QMessageBox.warning(self, "Inga dokument", "Lägg till PDF:er först.")
            return
        
        # Skapa progress dialog
        progress = QProgressDialog("Bearbetar PDF:er...", "Avbryt", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(True)
        
        # Skapa och starta processing thread
        self.processing_thread = ProcessingThread(
            documents,
            self.pdf_processor,
            self.clustering_engine
        )
        
        self.processing_thread.progress.connect(
            lambda p, m: (progress.setValue(p), progress.setLabelText(m))
        )
        self.processing_thread.finished.connect(
            lambda: (progress.setValue(100), self._on_processing_finished())
        )
        
        self.processing_thread.start()
    
    def _on_processing_finished(self):
        """Hanterar när bearbetning är klar."""
        # Uppdatera kluster i document manager
        documents = self.document_manager.get_all_documents()
        clusters = self.clustering_engine.cluster_documents(documents)
        
        for cluster_id, file_paths in clusters.items():
            # Hitta referensdokument
            cluster_docs = [d for d in documents if d.file_path in file_paths]
            if cluster_docs:
                ref_doc = self.clustering_engine.find_most_complete_document(cluster_docs)
                self.document_manager.set_cluster(
                    cluster_id, file_paths, ref_doc.file_path
                )
        
        self.refresh_clusters()
        self.status_label.setText(f"{len(clusters)} kluster skapade från {len(documents)} PDF:er.")
    
    def _on_cluster_clicked(self, item: QListWidgetItem):
        """Hanterar klick på kluster."""
        cluster_id = item.data(Qt.UserRole)
        self._show_cluster_info(cluster_id)
    
    def _on_cluster_double_clicked(self, item: QListWidgetItem):
        """Hanterar dubbelklick på kluster - öppnar mapping."""
        cluster_id = item.data(Qt.UserRole)
        self.cluster_selected.emit(cluster_id)
    
    def _show_cluster_info(self, cluster_id: str):
        """Visar information om klustret."""
        cluster_docs = self.document_manager.get_cluster_documents(cluster_id)
        ref_doc = self.document_manager.get_reference_document(cluster_id)
        template = self.template_manager.get_template(cluster_id)
        
        info = f"Kluster: {cluster_id}\n"
        info += f"Antal filer: {len(cluster_docs)}\n"
        
        if ref_doc:
            info += f"Referensfil: {ref_doc.file_path}\n"
        
        if template:
            info += f"Status: ✓ Mall klar ({len(template.field_mappings)} fält, {len(template.table_mappings)} tabeller)\n"
        else:
            info += "Status: ⚠ Mall saknas\n"
        
        info += "\nFiler:\n"
        for doc in cluster_docs[:10]:  # Visa första 10
            status_icon = "✓" if doc.status == "mapped" else "○"
            info += f"  {status_icon} {doc.file_path}\n"
        
        if len(cluster_docs) > 10:
            info += f"  ... och {len(cluster_docs) - 10} fler\n"
        
        self.cluster_info.setText(info)
    
    def refresh_clusters(self):
        """Uppdaterar klusterlistan."""
        self.cluster_list.clear()
        
        clusters = self.document_manager.clusters
        
        for cluster_id, file_paths in clusters.items():
            cluster_docs = self.document_manager.get_cluster_documents(cluster_id)
            template = self.template_manager.get_template(cluster_id)
            
            # Skapa list item
            status_icon = "✓" if template else "⚠"
            item_text = f"{status_icon} {cluster_id} ({len(cluster_docs)} filer)"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, cluster_id)
            self.cluster_list.addItem(item)
        
        if not clusters:
            self.status_label.setText("Inga kluster. Lägg till PDF:er och klicka 'Skanna'.")
    
    def _update_dependency_status(self):
        """Uppdaterar dependency status i UI."""
        status_lines = []
        
        # Tesseract status
        if self.tesseract_available:
            status_lines.append("✓ Tesseract OCR: Installerad och tillgänglig")
        else:
            status_lines.append("⚠ Tesseract OCR: Saknas - OCR-funktionalitet kommer inte att fungera")
            status_lines.append("   Textbaserade PDF:er fungerar fortfarande")
        
        status_lines.append("")  # Tom rad
        
        # Poppler status
        if self.poppler_available:
            status_lines.append("✓ Poppler: Installerad och tillgänglig")
        else:
            status_lines.append("⚠ Poppler: Saknas - PDF-visualisering kommer inte att fungera")
            status_lines.append("   PDF-extraktion från text-lager fungerar fortfarande")
        
        self.dependency_info.setText("\n".join(status_lines))
        
        # Varna användaren om dependencies saknas (endast första gången)
        if not self._dependency_warning_shown and (not self.tesseract_available or not self.poppler_available):
            self._dependency_warning_shown = True
            missing = []
            if not self.tesseract_available:
                missing.append("Tesseract OCR")
            if not self.poppler_available:
                missing.append("Poppler")
            
            warning_msg = (
                f"Varning: Följande dependencies saknas: {', '.join(missing)}\n\n"
            )
            
            if not self.tesseract_available:
                warning_msg += "Tesseract OCR: " + get_tesseract_installation_guide() + "\n\n"
            
            if not self.poppler_available:
                warning_msg += "Poppler: " + get_poppler_installation_guide() + "\n\n"
            
            warning_msg += (
                "Applikationen fungerar fortfarande med textbaserade PDF:er, "
                "men vissa funktioner kommer inte att vara tillgängliga.\n\n"
                "Klicka 'OK' för att fortsätta eller stäng denna dialog."
            )
            
            QMessageBox.warning(
                self,
                "Saknade Dependencies",
                warning_msg
            )