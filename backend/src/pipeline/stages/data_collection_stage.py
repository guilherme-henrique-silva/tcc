"""Data Collection Stage."""

from typing import Dict, Any, List, Optional, Sequence
from datetime import datetime, time

from src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    ProgressCallback,
)
from src.domain.value_objects import TickerSymbol, DateRange
from src.domain.models import News
from src.domain.models.treated_news import parse_frontmatter
from src.ports.data_source import DataSourcePort, NewsProcessorPort
from app.core.logger import get_logger

logger = get_logger(__name__)


class DataCollectionError(Exception):
    """Falha que impede o teste de Granger (alvo ou índice sem cotações)."""


class DataCollectionStage(PipelineStage):
    """Stage for collecting market data and consolidating treated news into News entities.

    Coleta, em subetapas próprias: alvo + concorrentes, índice de mercado e contratos
    futuros de commodities. Sem cotações do **alvo** ou do **índice** não há teste, e a
    etapa falha; concorrentes ou commodities vazios apenas geram aviso (a variável é
    removida do modelo adiante).
    """

    def __init__(
        self,
        data_source: DataSourcePort,
        tickers: List[str],
        sentiment_analyzer: Optional[NewsProcessorPort] = None,
        *,
        target_ticker: str = "BBAS3.SA",
        index_ticker: str = "^BVSP",
        commodity_tickers: Sequence[str] = (),
    ):
        """Initialize stage with data source, tickers, and optional sentiment analyzer."""
        super().__init__("data_collection")
        self.data_source = data_source
        self.tickers = tickers
        self._sentiment_analyzer = sentiment_analyzer
        self.target_ticker = target_ticker
        self.index_ticker = index_ticker
        self.commodity_tickers = list(commodity_tickers)

    def substages(self) -> List[str]:
        """Subetapas em ordem."""
        return [
            "coletar_precos",
            "coletar_indice",
            "coletar_commodities",
            "consolidar_noticias",
        ]

    def execute(
        self,
        input_data: Dict[str, Any],
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineStageResult:
        """Collect market data and consolidate treated news with sentiment."""
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

            self._report_substage(on_substage, "coletar_indice")
            index_prices = self._collect_index_prices(date_range)

            self._report_substage(on_substage, "coletar_commodities")
            commodity_prices = self._collect_commodity_prices(date_range)

            self._ensure_required_series(stock_prices, index_prices)

            self._report_substage(on_substage, "consolidar_noticias")
            news_items = self._collect_news(input_data, date_range)

            output_data = self._create_output_data(
                stock_prices,
                index_prices,
                commodity_prices,
                news_items,
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
        """Collect prices for the target and its competitors."""
        prices_by_ticker = {}

        for ticker_str in self.tickers:
            prices = self._fetch(ticker_str, date_range)
            prices_by_ticker[ticker_str] = prices

            if not prices and ticker_str != self.target_ticker:
                logger.warning(
                    "Sem cotações de %s: o concorrente sai do controle ret_peers", ticker_str
                )

        return prices_by_ticker

    def _collect_index_prices(self, date_range: DateRange) -> list:
        """Collect the market index (Ibovespa) prices."""
        return self._fetch(self.index_ticker, date_range)

    def _collect_commodity_prices(self, date_range: DateRange) -> Dict[str, list]:
        """Collect each commodity futures contract; empty ones are dropped with a warning."""
        collected: Dict[str, list] = {}

        for ticker_str in self.commodity_tickers:
            prices = self._fetch(ticker_str, date_range)

            if prices:
                collected[ticker_str] = prices
            else:
                logger.warning(
                    "Sem cotações de %s: a commodity sai de ret_commod", ticker_str
                )

        if self.commodity_tickers and not collected:
            logger.warning("Nenhuma commodity coletada: ret_commod sai do modelo")

        return collected

    def _fetch(self, ticker_str: str, date_range: DateRange) -> list:
        """Download one series; failures return an empty list after a warning."""
        ticker = TickerSymbol(ticker_str)
        prices = self.data_source.get_stock_prices(ticker, date_range) or []

        if not prices:
            logger.warning("Nenhuma cotação baixada para %s em %s", ticker_str, date_range)

        return prices

    def _ensure_required_series(self, stock_prices: Dict[str, list], index_prices: list) -> None:
        """Fail when the target or the index came back empty — there is no test without them."""
        if not stock_prices.get(self.target_ticker):
            raise DataCollectionError(
                f"Sem cotações do ativo alvo {self.target_ticker}: "
                "não há calendário de pregões nem variável dependente."
            )

        if not index_prices:
            raise DataCollectionError(
                f"Sem cotações do índice {self.index_ticker}: "
                "o controle ret_ibov é obrigatório."
            )

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
        source = entry.get("site") or self._domain_from_url(url)

        if not title or not body:
            return None

        published_date = self._resolve_published_date(meta, entry, url)
        if published_date is None:
            return None

        try:
            news = News(
                title=title,
                content=body,
                source=source or "desconhecido",
                published_date=published_date,
                url=url or "",
                published_time=self._parse_time(entry.get("news_time")),
            )
        except ValueError:
            return None

        if self._sentiment_analyzer is not None:
            sentiment = self._sentiment_analyzer.analyze_sentiment(body)
            if sentiment is not None:
                news.set_sentiment(sentiment)

        return news

    def _resolve_published_date(
        self,
        meta: Dict[str, str],
        entry: Dict[str, Any],
        url: str,
    ) -> Optional[datetime]:
        """Frontmatter date wins; fall back to the user-informed `news_date` (ISO).

        O horário não segue essa regra: vem **somente** do JSON de entrada (`news_time`).
        """
        from_frontmatter = self._parse_date(meta.get("date", ""))
        from_user = self._parse_iso_date(entry.get("news_date"))

        if from_frontmatter is None:
            return from_user

        if from_user is not None and from_user != from_frontmatter:
            logger.warning(
                "Data divergente em %s: frontmatter=%s, informada=%s (usando frontmatter)",
                url,
                from_frontmatter.date().isoformat(),
                from_user.date().isoformat(),
            )

        return from_frontmatter

    def _parse_time(self, value: Optional[str]) -> Optional[time]:
        """Parse "HH:MM" to time; returns None when absent or invalid."""
        if not value:
            return None

        try:
            return time.fromisoformat(str(value).strip())
        except ValueError:
            return None

    def _parse_iso_date(self, value: Optional[str]) -> Optional[datetime]:
        """Parse YYYY-MM-DD string to datetime; returns None when absent or invalid."""
        if not value:
            return None

        try:
            return datetime.strptime(str(value).strip(), "%Y-%m-%d")
        except ValueError:
            return None

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
        index_prices: list,
        commodity_prices: Dict[str, list],
        news_items: List[News],
    ) -> Dict[str, Any]:
        """Create output data for next stage."""
        return {
            "stock_prices": stock_prices,
            "index_prices": index_prices,
            "commodity_prices": commodity_prices,
            "news_items": news_items,
            "collection_timestamp": datetime.now().isoformat(),
        }
