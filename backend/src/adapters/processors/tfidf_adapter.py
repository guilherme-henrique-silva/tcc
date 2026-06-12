"""TF-IDF Adapter using scikit-learn."""

from typing import List, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import PCA

from src.ports.data_source import NewsProcessorPort


class TfIdfAdapter(NewsProcessorPort):
    """Adapter for TF-IDF feature extraction using scikit-learn (Rule 7: small entity)."""
    
    def __init__(self, n_components: int = 20):
        """Initialize TF-IDF extractor with target dimensionality."""
        self.n_components = n_components
        self.vectorizer = self._create_vectorizer()
        self.pca = self._create_pca()
    
    def analyze_sentiment(self, text: str) -> None:
        """Not implemented in this adapter."""
        return None
    
    def extract_entities(self, text: str) -> set:
        """Not implemented in this adapter."""
        return set()
    
    def calculate_tfidf(self, documents: List[str], n_components: int = None) -> Optional[np.ndarray]:
        """Calculate TF-IDF features for documents with PCA dimensionality reduction."""
        try:
            if not documents or not isinstance(documents, list):
                return None
            
            n_comp = n_components or self.n_components
            
            # Filter empty documents
            clean_docs = self._filter_empty_documents(documents)
            
            if not clean_docs:
                return None
            
            # Calculate TF-IDF
            tfidf_matrix = self._compute_tfidf(clean_docs)
            
            if tfidf_matrix is None or tfidf_matrix.shape[0] == 0:
                return None
            
            # Apply PCA
            reduced_features = self._apply_pca(tfidf_matrix, n_comp)
            
            return reduced_features
        
        except Exception:
            return None
    
    def _create_vectorizer(self):
        """Create TfidfVectorizer instance (Rule 1)."""
        return TfidfVectorizer(
            max_features=100,
            stop_words=self._get_portuguese_stopwords(),
            lowercase=True,
            min_df=1,
            max_df=0.9,
        )
    
    def _create_pca(self):
        """Create PCA instance (Rule 1)."""
        return PCA(n_components=self.n_components)
    
    def _get_portuguese_stopwords(self) -> List[str]:
        """Get Portuguese stopwords (Rule 1)."""
        try:
            from nltk.corpus import stopwords
            
            return stopwords.words("portuguese")
        
        except ImportError:
            # Fallback to common Portuguese stopwords
            return [
                "o", "a", "os", "as", "de", "do", "da", "dos", "das",
                "e", "ou", "em", "para", "com", "por", "que", "este",
                "esse", "aquele", "é", "são", "ser", "está", "estão",
            ]
    
    def _filter_empty_documents(self, documents: List[str]) -> List[str]:
        """Filter out empty or whitespace-only documents (Rule 1)."""
        clean_docs = []
        
        for doc in documents:
            if isinstance(doc, str) and doc.strip():
                clean_docs.append(doc.strip())
        
        return clean_docs
    
    def _compute_tfidf(self, documents: List[str]) -> Optional[np.ndarray]:
        """Compute TF-IDF matrix (Rule 1)."""
        try:
            matrix = self.vectorizer.fit_transform(documents)
            return matrix.toarray()
        
        except Exception:
            return None
    
    def _apply_pca(self, tfidf_matrix: np.ndarray, n_components: int) -> Optional[np.ndarray]:
        """Apply PCA dimensionality reduction (Rule 1)."""
        try:
            # Ensure n_components doesn't exceed matrix dimensions
            n_comp = min(n_components, tfidf_matrix.shape[0], tfidf_matrix.shape[1])
            
            if n_comp <= 0:
                return tfidf_matrix
            
            pca_instance = PCA(n_components=n_comp)
            reduced = pca_instance.fit_transform(tfidf_matrix)
            
            return reduced
        
        except Exception:
            return tfidf_matrix
