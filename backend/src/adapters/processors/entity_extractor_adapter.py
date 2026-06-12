"""Entity Extraction Adapter using spaCy."""

from typing import Set, List

from src.ports.data_source import NewsProcessorPort


class EntityExtractorAdapter(NewsProcessorPort):
    """Adapter for named entity recognition using spaCy (Rule 7: small entity)."""
    
    def __init__(self):
        """Initialize entity extractor."""
        self.nlp = self._load_spacy_model()
        self.target_entities = self._get_target_entities()
    
    def analyze_sentiment(self, text: str) -> None:
        """Not implemented in this adapter."""
        return None
    
    def extract_entities(self, text: str) -> Set[str]:
        """Extract relevant entities (banks, government, commodities) from text."""
        try:
            if not text or not isinstance(text, str):
                return set()
            
            entities = self._extract_spacy_entities(text)
            
            if not entities:
                entities = self._extract_keyword_entities(text)
            
            return entities
        
        except Exception:
            return set()
    
    def calculate_tfidf(self, documents: list, n_components: int) -> None:
        """Calculate TF-IDF (delegated to TfIdfAdapter)."""
        pass
    
    def _load_spacy_model(self):
        """Load spaCy Portuguese model (Rule 1)."""
        try:
            import spacy
            
            # Try to load Portuguese model
            return spacy.load("pt_core_news_sm")
        
        except (ImportError, OSError):
            return None
    
    def _get_target_entities(self) -> Set[str]:
        """Get list of target entity types (Rule 1)."""
        return {
            "ORG",  # Organizations (banks, government)
            "MISC",  # Miscellaneous (commodities)
            "PER",  # Persons (rarely needed)
        }
    
    def _extract_spacy_entities(self, text: str) -> Set[str]:
        """Extract entities using spaCy NER (Rule 1)."""
        if not self.nlp:
            return set()
        
        doc = self.nlp(text)
        entities = set()
        
        for ent in doc.ents:
            if ent.label_ in self.target_entities:
                entities.add(ent.text)
        
        return entities
    
    def _extract_keyword_entities(self, text: str) -> Set[str]:
        """Extract entities using keyword matching as fallback (Rule 1)."""
        entities = set()
        text_lower = text.lower()
        
        bank_keywords = {
            "banco do brasil", "bb", "bbas3", "bbas",
            "itaú", "itub4", "itub",
            "bradesco", "bbdc4", "bbdc",
            "santander", "sanb11", "sanb",
        }
        
        government_keywords = {
            "banco central", "bacen", "cmn", "copom",
            "governo", "ministério", "presidência",
        }
        
        commodity_keywords = {
            "soja", "milho", "boi", "café",
            "agronegócio", "agricultura", "grãos",
        }
        
        for keyword in bank_keywords | government_keywords | commodity_keywords:
            if keyword in text_lower:
                entities.add(keyword)
        
        return entities
