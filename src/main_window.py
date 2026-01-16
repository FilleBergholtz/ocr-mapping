"""
Huvudfönster för OCR PDF-applikationen.
Hanterar alla flikar och huvudnavigering.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QStatusBar, QMessageBox
)
from PySide6.QtCore import Qt
from .tabs.document_types_tab import DocumentTypesTab
from .tabs.mapping_tab import MappingTab
from .tabs.review_tab import ReviewTab
from .tabs.export_tab import ExportTab
from .core.document_manager import DocumentManager
from .core.clustering_engine import ClusteringEngine
from .core.template_manager import TemplateManager


class MainWindow(QMainWindow):
    """Huvudfönster med flikar för alla funktioner."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCR PDF - Fakturaextraktion")
        self.setMinimumSize(1200, 800)
        
        # Core managers
        self.document_manager = DocumentManager()
        self.clustering_engine = ClusteringEngine()
        self.template_manager = TemplateManager()
        
        # Setup UI
        self._setup_ui()
        self._connect_signals()
        
        # Status bar
        self.statusBar().showMessage("Redo")
    
    def _setup_ui(self):
        """Skapar UI-komponenter."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Skapa flikar
        self.document_types_tab = DocumentTypesTab(
            self.document_manager,
            self.clustering_engine,
            self.template_manager
        )
        self.mapping_tab = MappingTab(
            self.document_manager,
            self.template_manager
        )
        self.review_tab = ReviewTab(
            self.document_manager,
            self.template_manager
        )
        self.export_tab = ExportTab(
            self.document_manager,
            self.template_manager
        )
        
        # Lägg till flikar
        self.tabs.addTab(self.document_types_tab, "📄 Document Types")
        self.tabs.addTab(self.mapping_tab, "🗺️ Mapping")
        self.tabs.addTab(self.review_tab, "👁️ Review")
        self.tabs.addTab(self.export_tab, "📦 Extract & Export")
    
    def _connect_signals(self):
        """Kopplar signaler mellan komponenter."""
        # När ett kluster väljs i Document Types, öppna Mapping
        self.document_types_tab.cluster_selected.connect(
            self._on_cluster_selected
        )
        
        # När mappning är klar, uppdatera Document Types
        self.mapping_tab.mapping_completed.connect(
            self._on_mapping_completed
        )
        
        # När granskning är klar, öppna mapping för korrigering
        self.review_tab.review_completed.connect(
            self._on_review_completed
        )
    
    def _on_cluster_selected(self, cluster_id: str):
        """Hanterar när ett kluster väljs."""
        # Växla till Mapping-fliken
        self.tabs.setCurrentIndex(1)
        # Ladda klustret i Mapping-fliken
        self.mapping_tab.load_cluster(cluster_id)
    
    def _on_mapping_completed(self, cluster_id: str):
        """Hanterar när mappning är klar."""
        self.document_types_tab.refresh_clusters()
        # Växla till Review-fliken
        self.tabs.setCurrentIndex(2)
        self.review_tab.load_cluster(cluster_id)
    
    def _on_review_completed(self, cluster_id: str):
        """Hanterar när granskning är klar - öppna mapping för korrigering."""
        if cluster_id:
            self.tabs.setCurrentIndex(1)
            self.mapping_tab.load_cluster(cluster_id)
    
    def closeEvent(self, event):
        """Hanterar stängning av applikationen."""
        # Spara eventuella ändringar
        reply = QMessageBox.question(
            self,
            "Bekräfta avslut",
            "Vill du spara ändringar innan du avslutar?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )
        
        if reply == QMessageBox.Cancel:
            event.ignore()
        elif reply == QMessageBox.Yes:
            # Spara mallar och data
            self.template_manager.save_all_templates()
            event.accept()
        else:
            event.accept()
