"""Data Collection Stage."""

from typing import Dict, Any, List, Optional

from datetime import datetime

from src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    ProgressCallback,
)
from src.domain.value_objects import TickerSymbol, DateRange
from src.ports.data_source import DataSourcePort


class DataCollectionStage(PipelineStage):
    """Stage for collecting stock prices and news data (Rule 7: small entity)."""

    def __init__(
        self,
        data_source: DataSourcePort,
        tickers: List[str],
    ):
        """Initialize stage with data source and tickers."""
        super().__init__("data_collection")
        self.data_source = data_source
        self.tickers = tickers

    def substages(self) -> List[str]:
        """Subetapas em ordem."""
        return ["coletar_precos", "consolidar_noticias"]

    def execute(
        self,
        input_data: Dict[str, Any],
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineStageResult:
        """Collect stock and news data (Rule 1: delegate)."""
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
        """Validate data source availability (Rule 2: no else)."""
        if not self.data_source:
            return False
        
        if not self.tickers:
            return False
        
        return True
    
    def _extract_date_range(self, input_data: Dict) -> Optional[DateRange]:
        """Extract date range from input (Rule 1)."""
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
        """Collect stock prices for all tickers (Rule 1)."""
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
    ) -> list:
        """Consolidate news from Docling markdowns or CSV file (Rule 1)."""
        markdowns = input_data.get("news_markdowns")

        if markdowns:
            return self._consolidate_markdown_news(markdowns)

        return []

    def _consolidate_markdown_news(self, markdowns: list) -> list:
        """Normalize Docling markdown outputs into news records (Rule 1)."""
        news_items = []

        for entry in markdowns:
            if not entry.get("success"):
                continue

            news_items.append(
                {
                    "url": entry.get("url"),
                    "site": entry.get("site"),
                    "markdown": entry.get("markdown", ""),
                }
            )

        return news_items
    
    def _create_output_data(
        self,
        stock_prices: Dict[str, list],
        news_items: list,
    ) -> Dict[str, Any]:
        """Create output data for next stage (Rule 1)."""
        return {
            "stock_prices": stock_prices,
            "news_items": news_items,
            "collection_timestamp": datetime.now().isoformat(),
        }
