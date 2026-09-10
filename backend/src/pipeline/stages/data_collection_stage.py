"""Data Collection Stage."""

from typing import Dict, Any, List, Optional
from datetime import datetime, date

from src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    ProgressCallback,
)
from src.domain.value_objects import TickerSymbol, DateRange
from src.domain.models import News
from src.domain.models.treated_news import parse_frontmatter
from src.ports.data_source import DataSourcePort, NewsProcessorPort


class DataCollectionStage(PipelineStage):
    """Stage for collecting stock prices and consolidating treated news into News entities."""

    def __init__(
        self,
        data_source: DataSourcePort,
        tickers: List[str],
        sentiment_analyzer: Optional[NewsProcessorPort] = None,
    ):
        """Initialize stage with data source, tickers, and optional sentiment analyzer."""
        super().__init__("data_collection")
        self.data_source = data_source
        self.tickers = tickers
        self._sentiment_analyzer = sentiment_analyzer

    def substages(self) -> List[str]:
        """Subetapas em ordem."""
        return ["coletar_precos", "consolidar_noticias"]

    def execute(
        self,
        input_data: Dict[str, Any],
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineStageResult:
        """Collect stock prices and consolidate treated news with sentiment."""
        start_time = datetime.now()

        try:
            date_range = self._extract_date_range(input_data)

            if not date_range:
                return self._create_failure_result(
                    start_time,
                    datetime.now(),
                    "Invalid date range in input",
                )

            self._report_substage(on_substage, "coletar_precos")
            stock_prices = self._collect_stock_prices(date_range)

            self._report_substage(on_substage, "consolidar_noticias")
            news_items = self._collect_news(input_data, date_range)

            output_data = self._create_output_data(stock_prices, news_items)

            return self._create_success_result(
                start_time,
                datetime.now(),
                output_data,
            )

        except Exception as e:
            return self._create_failure_result(
                start_time,
                datetime.now(),
                str(e),
            )

    def validate(self) -> bool:
        """Validate data source availability."""
        return bool(self.data_source and self.tickers)

    def _extract_date_range(self, input_data: Dict) -> Optional[DateRange]:
        """Extract date range from input."""
        try:
            date_range_data = input_data.get("date_range", {})
            start_date = date_range_data.get("start_date")
            end_date = date_range_data.get("end_date")

            if not start_date or not end_date:
                return None

            return DateRange(start_date=start_date, end_date=end_date)

        except (ValueError, TypeError):
            return None

    def _collect_stock_prices(self, date_range: DateRange) -> Dict[str, list]:
        """Collect stock prices for all tickers."""
        prices_by_ticker = {}

        for ticker_str in self.tickers:
            ticker = TickerSymbol(ticker_str)
            prices = self.data_source.get_stock_prices(ticker, date_range)
            prices_by_ticker[ticker_str] = prices or []

        return prices_by_ticker

    def _collect_news(
        self,
        input_data: Dict[str, Any],
        date_range: DateRange,
    ) -> List[News]:
        """Consolidate news from treated Docling markdowns."""
        markdowns = input_data.get("news_markdowns")

        if markdowns:
            return self._consolidate_markdown_news(markdowns)

        return []

    def _consolidate_markdown_news(self, markdowns: list) -> List[News]:
        """Parse treated markdown into News entities with sentiment scores."""
        news_items: List[News] = []

        for entry in markdowns:
            if not entry.get("success"):
                continue

            news = self._entry_to_news(entry)
            if news is not None:
                news_items.append(news)

        return news_items

    def _entry_to_news(self, entry: Dict[str, Any]) -> Optional[News]:
        """Convert a single treated markdown entry to a News entity."""
        markdown = entry.get("markdown", "")
        meta, body = parse_frontmatter(markdown)

        title = meta.get("title", "").strip()
        url = meta.get("url") or entry.get("url", "")
        date_str = meta.get("date", "")
        source = entry.get("site") or self._domain_from_url(url)

        if not title or not body:
            return None

        published_date = self._parse_date(date_str)
        if published_date is None:
            return None

        try:
            news = News(
                title=title,
                content=body,
                source=source or "desconhecido",
                published_date=published_date,
                url=url or "",
            )
        except ValueError:
            return None

        if self._sentiment_analyzer is not None:
            sentiment = self._sentiment_analyzer.analyze_sentiment(body)
            if sentiment is not None:
                news.set_sentiment(sentiment)

        return news

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse DD-MM-AAAA string to datetime; returns None on failure."""
        if not date_str:
            return None

        try:
            return datetime.strptime(date_str.strip(), "%d-%m-%Y")
        except ValueError:
            return None

    def _domain_from_url(self, url: str) -> str:
        """Extract domain name from URL as fallback source label."""
        if not url:
            return ""

        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc or ""
        except Exception:
            return ""

    def _create_output_data(
        self,
        stock_prices: Dict[str, list],
        news_items: List[News],
    ) -> Dict[str, Any]:
        """Create output data for next stage."""
        return {
            "stock_prices": stock_prices,
            "news_items": news_items,
            "collection_timestamp": datetime.now().isoformat(),
        }
