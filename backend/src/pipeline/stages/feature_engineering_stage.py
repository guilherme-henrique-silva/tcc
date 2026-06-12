"""Feature Engineering Stage."""

from typing import Dict, Any, List, Optional

from datetime import datetime

from src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    ProgressCallback,
)
from src.domain.services.feature_engineering_service import FeatureEngineeringService
from src.domain.value_objects import TickerSymbol


class FeatureEngineeringStage(PipelineStage):
    """Stage for calculating features from stock and news data (Rule 7: small entity)."""

    def __init__(self):
        """Initialize feature engineering service."""
        super().__init__("feature_engineering")
        self.service = FeatureEngineeringService()

    def substages(self) -> List[str]:
        """Subetapas em ordem (Seção 3 do spec)."""
        return ["features_acoes", "features_noticias", "features_concorrentes"]

    def execute(
        self,
        input_data: Dict[str, Any],
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineStageResult:
        """Calculate features (Rule 1: delegate)."""
        start_time = datetime.now()

        try:
            stock_prices = self._extract_stock_prices(input_data)
            news_items = self._extract_news_items(input_data)

            if not stock_prices:
                return self._create_failure_result(
                    start_time,
                    datetime.now(),
                    "No stock prices available",
                )

            self._report_substage(on_substage, "features_acoes")
            stock_features = self._calculate_stock_features(stock_prices)

            self._report_substage(on_substage, "features_noticias")
            news_features = self._calculate_news_features(news_items, input_data)

            self._report_substage(on_substage, "features_concorrentes")
            competitor_features = self._calculate_competitor_features(stock_prices)
            
            output_data = self._create_output_data(
                stock_features,
                news_features,
                competitor_features,
            )
            
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
        """Validate service availability (Rule 2)."""
        return self.service is not None
    
    def _extract_stock_prices(self, input_data: Dict[str, Any]) -> Dict[str, list]:
        """Extract stock prices from input (Rule 1)."""
        return input_data.get("stock_prices", {})
    
    def _extract_news_items(self, input_data: Dict[str, Any]) -> list:
        """Extract news items from input (Rule 1)."""
        return input_data.get("news_items", [])
    
    def _calculate_stock_features(self, stock_prices: Dict[str, list]) -> Dict[str, any]:
        """Calculate stock features for all tickers (Rule 1)."""
        features_by_ticker = {}
        
        for ticker_str, prices in stock_prices.items():
            if not prices:
                continue
            
            ticker = TickerSymbol(ticker_str)
            features_df = self.service.calculate_stock_features(ticker, prices)
            features_by_ticker[ticker_str] = features_df.to_dict() if not features_df.empty else {}
        
        return features_by_ticker
    
    def _calculate_news_features(
        self,
        news_items: list,
        input_data: Dict[str, Any],
    ) -> Dict[str, any]:
        """Calculate news features (Rule 1)."""
        if not news_items:
            return {}
        
        try:
            date_range_data = input_data.get("date_range", {})
            
            # TODO: Create DateRange from input and calculate features
            return {}
        
        except Exception:
            return {}
    
    def _calculate_competitor_features(self, stock_prices: Dict[str, list]) -> Dict[str, any]:
        """Calculate competitor features (Rule 1)."""
        try:
            tickers = [TickerSymbol(t) for t in stock_prices.keys()]
            features_df = self.service.calculate_competitor_features(tickers, stock_prices)
            
            return features_df.to_dict() if not features_df.empty else {}
        
        except Exception:
            return {}
    
    def _create_output_data(
        self,
        stock_features: Dict,
        news_features: Dict,
        competitor_features: Dict,
    ) -> Dict[str, Any]:
        """Create output data for next stage (Rule 1)."""
        return {
            "stock_features": stock_features,
            "news_features": news_features,
            "competitor_features": competitor_features,
            "feature_timestamp": datetime.now().isoformat(),
        }
