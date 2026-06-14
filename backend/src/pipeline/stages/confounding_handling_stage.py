"""Confounding Handler Stage."""

from typing import Dict, Any, List, Optional

from datetime import datetime

from src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    ProgressCallback,
)
from src.domain.services.confounding_handler_service import ConfoundingHandlerService
from src.domain.value_objects import DateRange


class ConfoundingHandlerStage(PipelineStage):
    """Stage for handling confounding variables and Granger testing (Rule 7: small entity)."""

    def __init__(self):
        """Initialize confounding handler service."""
        super().__init__("confounding_handling")
        self.service = ConfoundingHandlerService()

    def substages(self) -> List[str]:
        """Subetapas em ordem."""
        return ["coletar_selic", "coletar_dolar", "coletar_commodities", "teste_granger"]

    def execute(
        self,
        input_data: Dict[str, Any],
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineStageResult:
        """Handle confounding variables and test causality (Rule 1)."""
        start_time = datetime.now()

        try:
            date_range = self._extract_date_range(input_data)

            if not date_range:
                return self._create_failure_result(
                    start_time,
                    datetime.now(),
                    "Invalid date range",
                )

            self._report_substage(on_substage, "coletar_selic")
            self._report_substage(on_substage, "coletar_dolar")
            self._report_substage(on_substage, "coletar_commodities")
            control_variables = self.service.get_control_variables(date_range)

            self._report_substage(on_substage, "teste_granger")
            granger_results = self._apply_granger_tests(input_data)

            output_data = self._create_output_data(control_variables, granger_results)
            
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
    
    def _extract_date_range(self, input_data: Dict) -> DateRange:
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
    
    def _apply_granger_tests(self, input_data: Dict[str, Any]) -> Dict[str, any]:
        """Apply Granger causality tests (Rule 1)."""
        # TODO: Extract sentiment and prices from input_data
        # For now, return empty results
        return {
            "granger_test_results": [],
            "significant_relationships": [],
        }
    
    def _create_output_data(
        self,
        control_variables,
        granger_results: Dict,
    ) -> Dict[str, Any]:
        """Create output data for next stage (Rule 1)."""
        control_vars_dict = control_variables.to_dict() if hasattr(control_variables, 'to_dict') else {}
        
        return {
            "control_variables": control_vars_dict,
            "granger_results": granger_results,
            "confounding_timestamp": datetime.now().isoformat(),
        }
