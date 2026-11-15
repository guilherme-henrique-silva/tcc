"""Confounding Handler Stage — controles fixos e dataset de análise por pregão."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    ProgressCallback,
)
from src.domain.services.confounding_handler_service import ConfoundingHandlerService
from app.core.config import Config
from app.core.logger import get_logger

logger = get_logger(__name__)

_DATE = "date"


class ConfoundingHandlerStage(PipelineStage):
    """Stage that builds the fixed control variables and the analysis dataset.

    Os controles entram sempre, sem seleção por significância. O teste de Granger fica na
    etapa seguinte (``granger_causality``).
    """

    def __init__(
        self,
        bcb_adapter=None,
        copom_decision_dates: Optional[List[str]] = None,
    ):
        """Initialize confounding handler service; the Copom calendar comes from Config."""
        super().__init__("confounding_handling")
        dates = Config.COPOM_DECISION_DATES if copom_decision_dates is None else copom_decision_dates
        self.service = ConfoundingHandlerService(bcb_adapter, dates)

    def substages(self) -> List[str]:
        """Subetapas em ordem."""
        return ["coletar_dolar", "indicador_copom", "montar_dataset"]

    def execute(
        self,
        input_data: Dict[str, Any],
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineStageResult:
        """Build the controls and the analysis dataset."""
        start_time = datetime.now()

        try:
            missing = self._missing_inputs(input_data)
            if missing:
                return self._create_failure_result(
                    start_time,
                    datetime.now(),
                    f"Entradas ausentes ({', '.join(missing)}) — habilite feature_engineering.",
                )

            sessions: List[date] = input_data["sessions"]
            warnings: List[str] = []
            controls: Dict[str, pd.Series] = {}

            self._report_substage(on_substage, "coletar_dolar")
            usd = self._usd_control(sessions, warnings)

            self._report_substage(on_substage, "indicador_copom")
            copom = self.service.copom_indicator(sessions)

            self._report_substage(on_substage, "montar_dataset")
            controls.update(self._market_controls(input_data, sessions, warnings))
            if usd is not None:
                controls["d_usdbrl"] = usd
            commod = self.service.commodity_control(
                input_data.get("commodity_prices") or {}, sessions
            )
            if commod is not None:
                controls["ret_commod"] = commod
            else:
                warnings.append("Sem commodities coletadas: ret_commod removida do modelo.")
            controls["copom"] = copom

            dataset, build_warnings = self.service.build_analysis_dataset(
                self._target_frame(input_data),
                pd.DataFrame(input_data.get("news_features") or []),
                controls,
            )
            warnings.extend(build_warnings)

            return self._create_success_result(
                start_time,
                datetime.now(),
                self._create_output_data(dataset, controls, warnings),
            )

        except Exception as e:
            return self._create_failure_result(
                start_time,
                datetime.now(),
                str(e),
            )

    def validate(self) -> bool:
        """Validate service availability."""
        return self.service is not None

    @staticmethod
    def _missing_inputs(input_data: Dict[str, Any]) -> List[str]:
        """Chaves que a etapa 3 deveria ter entregue."""
        required = ("sessions", "stock_features", "target_ticker")
        return [key for key in required if not input_data.get(key)]

    def _usd_control(self, sessions: List[date], warnings: List[str]) -> Optional[pd.Series]:
        """``d_usdbrl``; falha de rede/API vira aviso e a variável sai do modelo."""
        try:
            return self.service.usd_brl_control(sessions)

        except Exception as exc:  # noqa: BLE001 — API externa: degrada com aviso explícito
            logger.warning("Falha ao obter a PTAX: %s", exc)
            warnings.append(f"PTAX indisponível ({exc}): d_usdbrl removida do modelo.")
            return None

    @staticmethod
    def _market_controls(
        input_data: Dict[str, Any],
        sessions: List[date],
        warnings: List[str],
    ) -> Dict[str, pd.Series]:
        """``ret_ibov`` e concorrentes (``ret_peers`` ou ``ret_<ticker>``), vindos da etapa 3."""
        controls: Dict[str, pd.Series] = {}

        index_returns = pd.DataFrame(input_data.get("index_returns") or [])
        if index_returns.empty:
            warnings.append("Sem retorno do índice: ret_ibov removida do modelo.")
        else:
            controls["ret_ibov"] = index_returns.set_index(_DATE)["ret_ibov"]

        peer_returns = pd.DataFrame(input_data.get("peer_returns") or [])
        if peer_returns.empty:
            warnings.append("Sem concorrentes com cotação: ret_peers removida do modelo.")
        else:
            for column in peer_returns.columns:
                if column != _DATE:
                    controls[column] = peer_returns.set_index(_DATE)[column]

        return controls

    @staticmethod
    def _target_frame(input_data: Dict[str, Any]) -> pd.DataFrame:
        """Features do alvo (retornos, volatilidade, volume) como DataFrame."""
        return pd.DataFrame(input_data["stock_features"][input_data["target_ticker"]])

    def _create_output_data(
        self,
        dataset: pd.DataFrame,
        controls: Dict[str, pd.Series],
        warnings: List[str],
    ) -> Dict[str, Any]:
        """Create output data for next stage."""
        control_frame = pd.DataFrame(controls).rename_axis(_DATE).reset_index()

        return {
            "control_variables": _serialize(control_frame),
            "analysis_dataset": _serialize(dataset),
            "analysis_warnings": warnings,
            "confounding_timestamp": datetime.now().isoformat(),
        }


def _serialize(frame: pd.DataFrame) -> List[dict]:
    """DataFrame -> records com ``date`` em ISO (JSON-safe) e NaN como None."""
    if frame.empty:
        return []

    out = frame.copy()
    out[_DATE] = out[_DATE].map(lambda d: d.isoformat() if hasattr(d, "isoformat") else str(d))
    out = out.astype(object).where(out.notna(), None)
    return out.to_dict(orient="records")
