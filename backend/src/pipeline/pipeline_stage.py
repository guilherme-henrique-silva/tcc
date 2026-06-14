"""Abstract base class for pipeline stages (Rule 7: Keep entities small)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime


@dataclass(frozen=True)
class PipelineStageResult:
    """Encapsulates result of pipeline stage execution (Rule 4: First Class Collection)."""

    stage_name: str
    status: str  # "SUCCESS", "FAILED", "SKIPPED"
    start_time: datetime
    end_time: datetime
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class SubStageTag:
    """Identifica uma subetapa para fins de progresso e logging."""

    stage_name: str
    substage_name: str
    order: int          # 1-based: ordem da subetapa atual
    total: int          # total de subetapas da etapa

    @property
    def order_ratio(self) -> float:
        """Razão ordem_atual / total (ex.: 2/4 = 0.5)."""
        if self.total <= 0:
            return 0.0
        return self.order / self.total

    @property
    def label(self) -> str:
        """Rótulo legível p/ stqdm: 'data_collection · coletar_precos (1/2)'."""
        return f"{self.stage_name} · {self.substage_name} ({self.order}/{self.total})"


# Callback opcional de progresso injetado na execução de cada estágio.
ProgressCallback = Callable[[SubStageTag], None]


class PipelineStage(ABC):
    """Abstract base for all pipeline stages (Rule 7: small entities)."""

    def __init__(self, stage_name: str):
        """Initialize stage with name."""
        self.stage_name = stage_name

    @abstractmethod
    def execute(
        self,
        input_data: Dict[str, Any],
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineStageResult:
        """
        Execute stage with input data.

        Args:
            input_data: Dados de entrada vindos da etapa anterior.
            on_substage: Callback opcional para reportar cada SubStageTag.

        Returns PipelineStageResult with status and output.
        """
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate stage prerequisites (Rule 2: no else, early return)."""
        pass

    def substages(self) -> List[str]:
        """Nomes das subetapas, em ordem de execução. Sobrescrito por cada etapa."""
        return []

    def _report_substage(
        self,
        on_substage: Optional[ProgressCallback],
        substage_name: str,
    ) -> None:
        """Emite uma SubStageTag para o callback de progresso (Rule 1: delegate)."""
        if not on_substage:
            return

        substages = self.substages()

        if substage_name not in substages:
            return

        order = substages.index(substage_name) + 1
        on_substage(
            SubStageTag(
                stage_name=self.stage_name,
                substage_name=substage_name,
                order=order,
                total=len(substages),
            )
        )

    def _create_success_result(
        self,
        start_time: datetime,
        end_time: datetime,
        data: Dict[str, Any],
    ) -> PipelineStageResult:
        """Create success result (Rule 1: delegate to helper)."""
        return PipelineStageResult(
            stage_name=self.stage_name,
            status="SUCCESS",
            start_time=start_time,
            end_time=end_time,
            data=data,
        )

    def _create_failure_result(
        self,
        start_time: datetime,
        end_time: datetime,
        error_message: str,
    ) -> PipelineStageResult:
        """Create failure result (Rule 1)."""
        return PipelineStageResult(
            stage_name=self.stage_name,
            status="FAILED",
            start_time=start_time,
            end_time=end_time,
            error_message=error_message,
        )

    def create_skipped_result(self) -> PipelineStageResult:
        """Create skipped result for a disabled stage."""
        now = datetime.now()
        return PipelineStageResult(
            stage_name=self.stage_name,
            status="SKIPPED",
            start_time=now,
            end_time=now,
            data=None,
        )
