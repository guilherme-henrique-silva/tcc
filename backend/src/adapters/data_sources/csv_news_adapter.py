"""CSV News Data Source Adapter."""

from typing import List
import pandas as pd
from datetime import datetime

from src.domain.models import News
from src.domain.value_objects import DateRange, SentimentScore
from src.ports.data_source import DataSourcePort


class CsvNewsAdapter(DataSourcePort):
    """Adapter for loading news from CSV files (Rule 7: small entity)."""
    
    def __init__(self, csv_path: str = None):
        """Initialize with optional CSV file path."""
        self.csv_path = csv_path
    
    def get_stock_prices(self, ticker, date_range: DateRange) -> List:
        """Not implemented in this adapter."""
        return []
    
    def get_news(self, date_range: DateRange, csv_path: str = None) -> List[News]:
        """Load news from CSV file within date range."""
        path = csv_path or self.csv_path
        
        if not path:
            return []
        
        try:
            df = pd.read_csv(path)
            news_items = self._convert_to_news_items(df, date_range)
            return news_items
        
        except (FileNotFoundError, pd.errors.ParserError):
            return []
    
    def get_macroeconomic_data(self, indicators: List[str], date_range: DateRange) -> List:
        """Not implemented in this adapter."""
        return []
    
    def _convert_to_news_items(
        self,
        df: pd.DataFrame,
        date_range: DateRange,
    ) -> List[News]:
        """Convert CSV rows to News objects (Rule 1)."""
        news_items = []
        
        for idx, row in df.iterrows():
            news_item = self._create_news_from_row(row, date_range)
            
            if news_item:
                news_items.append(news_item)
        
        return news_items
    
    def _create_news_from_row(self, row, date_range: DateRange) -> News:
        """Create News from CSV row (Rule 1)."""
        try:
            created_at = self._parse_date(row.get("date", ""))
            
            if not self._is_within_date_range(created_at, date_range):
                return None
            
            title = str(row.get("title", ""))
            content = str(row.get("content", ""))
            source = str(row.get("source", "Unknown"))
            url = str(row.get("url", ""))
            
            if not title or not content:
                return None
            
            sentiment_value = row.get("sentiment", 0)
            sentiment_score = self._parse_sentiment(sentiment_value)
            
            news = News(
                title=title,
                content=content,
                source=source,
                created_at=created_at,
                url=url,
            )
            
            if sentiment_score:
                news = news.set_sentiment(sentiment_score)
            
            return news
        
        except (ValueError, KeyError, TypeError):
            return None
    
    def _parse_date(self, date_str) -> datetime:
        """Parse date string to datetime (Rule 1)."""
        if isinstance(date_str, datetime):
            return date_str
        
        if isinstance(date_str, pd.Timestamp):
            return date_str.to_pydatetime()
        
        # Try common date formats
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"]:
            try:
                return datetime.strptime(str(date_str), fmt)
            except ValueError:
                continue
        
        return datetime.now()
    
    def _is_within_date_range(self, date: datetime, date_range: DateRange) -> bool:
        """Check if date is within range (Rule 1)."""
        return date_range.contains(date.date())
    
    def _parse_sentiment(self, value) -> SentimentScore:
        """Parse sentiment value to SentimentScore (Rule 1)."""
        try:
            sentiment_int = int(value)
            
            if sentiment_int == -1:
                return SentimentScore(value=-1)
            elif sentiment_int == 1:
                return SentimentScore(value=1)
            elif sentiment_int == 0:
                return SentimentScore(value=0)
            
            return None
        
        except (ValueError, TypeError):
            return None
