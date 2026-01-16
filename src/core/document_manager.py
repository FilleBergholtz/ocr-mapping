"""
Document Manager - Hanterar PDF-dokument och deras metadata.
"""

import os
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class PDFDocument:
    """Representerar ett PDF-dokument med dess metadata."""
    file_path: str
    cluster_id: Optional[str] = None
    fingerprint: Dict = field(default_factory=dict)
    extracted_text: str = ""
    extracted_data: Dict = field(default_factory=dict)
    is_reference: bool = False
    status: str = "pending"  # pending, processed, mapped, reviewed, error
    
    def to_dict(self) -> Dict:
        """Konverterar till dictionary för serialisering."""
        return {
            "file_path": self.file_path,
            "cluster_id": self.cluster_id,
            "fingerprint": self.fingerprint,
            "extracted_text": self.extracted_text,
            "extracted_data": self.extracted_data,
            "is_reference": self.is_reference,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PDFDocument':
        """Skapar från dictionary."""
        doc = cls(
            file_path=data["file_path"],
            cluster_id=data.get("cluster_id"),
            fingerprint=data.get("fingerprint", {}),
            extracted_text=data.get("extracted_text", ""),
            extracted_data=data.get("extracted_data", {}),
            is_reference=data.get("is_reference", False),
            status=data.get("status", "pending")
        )
        return doc


class DocumentManager:
    """Hanterar alla PDF-dokument i applikationen."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.documents: Dict[str, PDFDocument] = {}
        self.clusters: Dict[str, List[str]] = {}  # cluster_id -> [file_paths]
        self.reference_docs: Dict[str, str] = {}  # cluster_id -> reference_file_path
        
        self._load_data()
    
    def add_documents(self, file_paths: List[str]) -> List[PDFDocument]:
        """Lägger till PDF-dokument."""
        new_docs = []
        for file_path in file_paths:
            if file_path not in self.documents:
                doc = PDFDocument(file_path=file_path)
                self.documents[file_path] = doc
                new_docs.append(doc)
        self._save_data()
        return new_docs
    
    def get_document(self, file_path: str) -> Optional[PDFDocument]:
        """Hämtar ett dokument."""
        return self.documents.get(file_path)
    
    def get_all_documents(self) -> List[PDFDocument]:
        """Hämtar alla dokument."""
        return list(self.documents.values())
    
    def get_cluster_documents(self, cluster_id: str) -> List[PDFDocument]:
        """Hämtar alla dokument i ett kluster."""
        file_paths = self.clusters.get(cluster_id, [])
        return [self.documents[fp] for fp in file_paths if fp in self.documents]
    
    def get_reference_document(self, cluster_id: str) -> Optional[PDFDocument]:
        """Hämtar referensdokumentet för ett kluster."""
        ref_path = self.reference_docs.get(cluster_id)
        if ref_path:
            return self.documents.get(ref_path)
        return None
    
    def set_cluster(self, cluster_id: str, file_paths: List[str], reference_path: str):
        """Sätter kluster och referensdokument."""
        self.clusters[cluster_id] = file_paths
        
        # Markera referensdokument
        for doc in self.documents.values():
            doc.is_reference = (doc.file_path == reference_path)
            if doc.file_path in file_paths:
                doc.cluster_id = cluster_id
        
        self.reference_docs[cluster_id] = reference_path
        self._save_data()
    
    def update_document(self, doc: PDFDocument):
        """Uppdaterar ett dokument."""
        self.documents[doc.file_path] = doc
        self._save_data()
    
    def _save_data(self):
        """Sparar data till disk."""
        data_file = self.data_dir / "documents.json"
        data = {
            "documents": {fp: doc.to_dict() for fp, doc in self.documents.items()},
            "clusters": self.clusters,
            "reference_docs": self.reference_docs
        }
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _load_data(self):
        """Laddar data från disk."""
        data_file = self.data_dir / "documents.json"
        if data_file.exists():
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.documents = {
                fp: PDFDocument.from_dict(doc_data)
                for fp, doc_data in data.get("documents", {}).items()
            }
            self.clusters = data.get("clusters", {})
            self.reference_docs = data.get("reference_docs", {})
