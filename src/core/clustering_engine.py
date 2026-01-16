"""
Clustering Engine - Grupperar liknande PDF:er med maskininlärning.
"""

import re
from typing import List, Dict, Tuple, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from .document_manager import PDFDocument


class ClusteringEngine:
    """Motor för klustering av PDF-dokument."""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=500,
            stop_words=None,  # Vi hanterar svenska stop words manuellt
            ngram_range=(1, 2),
            min_df=2
        )
    
    def create_fingerprint(self, text: str) -> Dict:
        """
        Skapar ett fingeravtryck för en PDF baserat på text.
        Fingeravtrycket inkluderar:
        - Text i toppen och botten av sidan
        - Nyckelord (faktura, total, moms, etc.)
        - Layout och positioner
        """
        lines = text.split('\n')
        
        # Top och bottom text (första och sista 10 raderna)
        top_text = ' '.join(lines[:10])
        bottom_text = ' '.join(lines[-10:])
        
        # Extrahera nyckelord
        keywords = self._extract_keywords(text)
        
        # Skapa feature-vektor
        fingerprint = {
            "top_text": top_text,
            "bottom_text": bottom_text,
            "keywords": keywords,
            "total_words": len(text.split()),
            "total_lines": len(lines),
            "has_table": self._detect_table(text),
            "full_text": text  # För TF-IDF
        }
        
        return fingerprint
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extraherar nyckelord från text."""
        # Svenska och engelska nyckelord för fakturor
        keyword_patterns = [
            r'\bfaktura\w*\b',
            r'\binvoice\w*\b',
            r'\btotal\w*\b',
            r'\bmoms\w*\b',
            r'\bvat\w*\b',
            r'\bdatum\w*\b',
            r'\bdate\w*\b',
            r'\bnummer\w*\b',
            r'\bnumber\w*\b',
            r'\bordernr\w*\b',
            r'\border\s*no\w*\b',
            r'\bartikel\w*\b',
            r'\bitem\w*\b',
            r'\bpris\w*\b',
            r'\bprice\w*\b',
            r'\bantal\w*\b',
            r'\bquantity\w*\b',
            r'\bsumma\w*\b',
            r'\bsum\w*\b',
        ]
        
        found_keywords = []
        text_lower = text.lower()
        
        for pattern in keyword_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            found_keywords.extend(matches)
        
        return list(set(found_keywords))
    
    def _detect_table(self, text: str) -> bool:
        """Detekterar om texten innehåller en tabell."""
        lines = text.split('\n')
        # Enkel heuristik: om flera rader har flera kolumner (separerade med flera mellanslag eller tabs)
        table_indicators = 0
        for line in lines:
            # Räkna antal kolumner (flera whitespace-separerade delar)
            parts = re.split(r'\s{2,}|\t', line.strip())
            if len(parts) >= 3:  # Minst 3 kolumner
                table_indicators += 1
        
        return table_indicators >= 3
    
    def cluster_documents(
        self,
        documents: List[PDFDocument],
        n_clusters: Optional[int] = None
    ) -> Dict[str, List[str]]:
        """
        Klustrar dokument baserat på likhet.
        Returnerar: {cluster_id: [file_paths]}
        """
        if len(documents) < 2:
            # För få dokument för klustering
            if documents:
                return {"cluster_0": [documents[0].file_path]}
            return {}
        
        # Skapa feature-vektorer från fingeravtryck
        texts = []
        for doc in documents:
            fingerprint_text = self._fingerprint_to_text(doc.fingerprint)
            texts.append(fingerprint_text)
        
        # TF-IDF vektorisering
        try:
            tfidf_matrix = self.vectorizer.fit_transform(texts)
        except ValueError:
            # Om alla dokument är identiska eller för få features
            return {"cluster_0": [doc.file_path for doc in documents]}
        
        # Beräkna cosine similarity
        similarity_matrix = cosine_similarity(tfidf_matrix)
        
        # Bestäm antal kluster adaptivt om inte specificerat
        if n_clusters is None:
            # Använd genomsnittlig similarity för att bestämma antal kluster
            avg_similarity = np.mean(similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)])
            if avg_similarity > 0.7:
                n_clusters = max(1, len(documents) // 3)
            else:
                n_clusters = max(1, len(documents) // 2)
        
        n_clusters = min(n_clusters, len(documents))
        
        # Agglomerative Clustering
        clustering = AgglomerativeClustering(
            n_clusters=n_clusters,
            metric='precomputed',
            linkage='average'
        )
        
        # Konvertera similarity till distance
        distance_matrix = 1 - similarity_matrix
        np.fill_diagonal(distance_matrix, 0)
        
        cluster_labels = clustering.fit_predict(distance_matrix)
        
        # Gruppera dokument efter kluster
        clusters = {}
        for i, doc in enumerate(documents):
            cluster_id = f"cluster_{cluster_labels[i]}"
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append(doc.file_path)
        
        return clusters
    
    def _fingerprint_to_text(self, fingerprint: Dict) -> str:
        """Konverterar fingeravtryck till text för TF-IDF."""
        parts = [
            fingerprint.get("top_text", ""),
            fingerprint.get("bottom_text", ""),
            " ".join(fingerprint.get("keywords", [])),
            fingerprint.get("full_text", "")
        ]
        return " ".join(parts)
    
    def find_most_complete_document(
        self,
        documents: List[PDFDocument]
    ) -> PDFDocument:
        """
        Hittar den mest kompletta PDF:en i ett kluster.
        Baserat på: flest ord, flest keywords, mest struktur.
        """
        if not documents:
            raise ValueError("Inga dokument att välja från")
        
        scores = []
        for doc in documents:
            fp = doc.fingerprint
            score = (
                fp.get("total_words", 0) * 0.4 +
                len(fp.get("keywords", [])) * 10 * 0.3 +
                (fp.get("total_lines", 0) / 10) * 0.2 +
                (1 if fp.get("has_table", False) else 0) * 100 * 0.1
            )
            scores.append((score, doc))
        
        # Sortera efter score (högst först)
        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[0][1]
    
    def find_similar_documents(
        self,
        reference_doc: PDFDocument,
        all_documents: List[PDFDocument],
        threshold: float = 0.7
    ) -> List[PDFDocument]:
        """
        Hittar dokument som liknar referensdokumentet.
        Returnerar dokument med similarity > threshold.
        """
        ref_text = self._fingerprint_to_text(reference_doc.fingerprint)
        
        similar_docs = []
        for doc in all_documents:
            if doc.file_path == reference_doc.file_path:
                continue
            
            doc_text = self._fingerprint_to_text(doc.fingerprint)
            
            # Beräkna similarity
            try:
                vectors = self.vectorizer.transform([ref_text, doc_text])
                similarity = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
                
                if similarity >= threshold:
                    similar_docs.append(doc)
            except:
                # Om vektorisering misslyckas, hoppa över
                continue
        
        return similar_docs
