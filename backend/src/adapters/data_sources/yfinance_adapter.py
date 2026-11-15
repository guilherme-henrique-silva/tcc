"""YFinance Data Source Adapter."""

from datetime import timedelta
from typing import List
import yfinance as yf
import pandas as pd

from src.domain.models import StockPrice
from src.domain.value_objects import TickerSymbol, DateRange
from src.ports.data_source import DataSourcePort
from app.core.logger import get_logger

logger = get_logger(__name__)


class YFinanceAdapter(DataSourcePort):
    """Adapter for fetching stock data from yfinance."""
    
    def __init__(self):
        """Initialize adapter."""
        pass
    
    def get_stock_prices(
        self,
        ticker: TickerSymbol,
        date_range: DateRange,
    ) -> List[StockPrice]:
        """Fetch stock prices from yfinance and convert to domain model."""
        try:
            ticker_str = str(ticker)
            ticker_data = yf.Ticker(ticker_str)
            
            hist_df = self._fetch_history(
                ticker_data,
                date_range.start_date,
                date_range.end_date,
            )
            
            if hist_df.empty:
                return []
            
            stock_prices = self._convert_to_stock_prices(hist_df, ticker)
            dropped = len(hist_df) - len(stock_prices)
            if dropped:
                logger.warning(
                    "%s: %d linha(s) do yfinance descartada(s) por OHLC inconsistente",
                    ticker, dropped,
                )
            return stock_prices

        except Exception as exc:  # noqa: BLE001 — falha de rede/ticker não derruba a coleta
            logger.warning("Falha ao baixar %s do yfinance: %s", ticker, exc)
            return []
    
    def get_news(self, date_range: DateRange) -> List:
        """Not implemented in this adapter."""
        return []
    
    def get_macroeconomic_data(self, indicators: List[str], date_range: DateRange) -> List:
        """Not implemented in this adapter."""
        return []
    
    def _fetch_history(self, ticker_obj, start_date, end_date) -> pd.DataFrame:
        """Fetch historical data from yfinance.

        ``Ticker.history()`` devolve preços **ajustados** (``auto_adjust=True`` é o padrão
        do yfinance): ``Close`` já considera dividendos e desdobramentos. É o preço de
        fechamento ajustado exigido pelo retorno logarítmico do TCC.

        O ``end`` do yfinance é **exclusivo**; por isso pedimos ``end_date + 1 dia`` para
        que o último dia do período (inclusivo no ``DateRange``) seja devolvido.
        """
        return ticker_obj.history(
            start=start_date,
            end=end_date + timedelta(days=1),
            auto_adjust=True,
        )
    
    def _convert_to_stock_prices(
        self,
        df: pd.DataFrame,
        ticker: TickerSymbol,
    ) -> List[StockPrice]:
        """Convert DataFrame to StockPrice objects."""
        stock_prices = []
        
        for date, row in df.iterrows():
            stock_price = self._create_stock_price_from_row(row, ticker, date)
            
            if stock_price:
                stock_prices.append(stock_price)
        
        return stock_prices
    
    def _create_stock_price_from_row(self, row, ticker: TickerSymbol, date) -> StockPrice:
        """Create StockPrice from DataFrame row."""
        try:
            return StockPrice(
                ticker=ticker,
                date=pd.Timestamp(date).to_pydatetime(),
                open_price=float(row.get("Open", 0.0)),
                high_price=float(row.get("High", 0.0)),
                low_price=float(row.get("Low", 0.0)),
                close_price=float(row.get("Close", 0.0)),
                volume=int(row.get("Volume", 0)),
            )
        except (ValueError, KeyError, TypeError):
            return None
