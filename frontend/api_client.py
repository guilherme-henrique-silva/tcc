"""HTTP Client wrapper for backend API communication."""

import requests
import pandas as pd
from typing import Dict, List, Optional, Any
import os

class APIClient:
    """Client for communicating with FastAPI backend."""
    
    def __init__(self, base_url: str = None):
        """Initialize API client."""
        self.base_url = base_url or os.getenv("API_BASE_URL", "http://localhost:8000")
    
    def execute_pipeline(self, config: Dict) -> Dict:
        """
        Run the pipeline synchronously honoring the feature toggle.

        Returns:
            The full run response (pipeline_id, status, stage_results, ...).
        """
        response = requests.post(
            f"{self.base_url}/api/pipeline/execute",
            json=config,
            timeout=600,
        )
        response.raise_for_status()
        return response.json()

    def get_proc_news(self, url: str) -> Optional[Dict]:
        """Return the PIPELINE_PROC_NEWS record for a URL, or None (Seção 8.5)."""
        response = requests.get(
            f"{self.base_url}/api/pipeline/proc_news",
            params={"url": url},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    
    def get_pipeline_status(self, job_id: str) -> Dict:
        """Get pipeline execution status."""
        response = requests.get(
            f"{self.base_url}/api/pipeline/status",
            params={"job_id": job_id},
            timeout=5,
        )
        response.raise_for_status()
        return response.json()
    
    def resume_from_checkpoint(self, checkpoint_id: str) -> str:
        """Resume pipeline from checkpoint."""
        response = requests.post(
            f"{self.base_url}/api/pipeline/resume",
            json={"checkpoint_id": checkpoint_id},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["job_id"]
    
    def upload_file(self, file_path: str) -> str:
        """Upload CSV file."""
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(
                f"{self.base_url}/api/data/upload",
                files=files,
                timeout=30,
            )
        response.raise_for_status()
        return response.json()["file_id"]
    
    def validate_data(self, df: pd.DataFrame) -> Dict:
        """Validate dataset."""
        # Convert DataFrame to JSON for transmission
        data_json = df.to_json()
        
        response = requests.post(
            f"{self.base_url}/api/data/validate",
            json={"data": data_json},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    
    def get_features(self, feature_type: str) -> Dict:
        """Get calculated features."""
        response = requests.get(
            f"{self.base_url}/api/data/features",
            params={"type": feature_type},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> Dict:
        """Check backend health."""
        response = requests.get(
            f"{self.base_url}/health",
            timeout=5,
        )
        response.raise_for_status()
        return response.json()

    def health_check_db(self) -> Dict:
        """Check database connectivity, returning status + reason on failure (Seção 7)."""
        response = requests.get(
            f"{self.base_url}/health/db",
            timeout=5,
        )
        response.raise_for_status()
        return response.json()

    def convert_link(self, url: str) -> Dict:
        """Convert a single news link into Markdown on demand (Seção 10)."""
        response = requests.post(
            f"{self.base_url}/api/pipeline/convert_link",
            json={"url": url},
            timeout=600,
        )
        response.raise_for_status()
        return response.json()

    def treat_news(self, markdown: str, model_path: Optional[str] = None) -> str:
        """Treat one news Markdown via the configured LLM (Seções 10/11)."""
        response = requests.post(
            f"{self.base_url}/api/pipeline/treat_news",
            json={"markdown": markdown, "model_path": model_path},
            timeout=600,
        )
        response.raise_for_status()
        return response.json()["treated_markdown"]

    def save_treated_news(
        self,
        url: str,
        treated_markdown: str,
        proc_id: Optional[str] = None,
    ) -> Dict:
        """Persist a treated news document edited/validated in the UI (Seção 10)."""
        response = requests.post(
            f"{self.base_url}/api/pipeline/treated_news",
            json={"url": url, "treated_markdown": treated_markdown, "proc_id": proc_id},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_treated_news(self, url: str) -> Optional[Dict]:
        """Return the treated news document for a URL, or None (Seção 10)."""
        response = requests.get(
            f"{self.base_url}/api/pipeline/treated_news",
            params={"url": url},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def list_llm_models(self) -> List[Dict]:
        """List the LLM_MODELS catalog with on-disk status (Seção 12)."""
        response = requests.get(
            f"{self.base_url}/api/pipeline/llm_models",
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def download_model(self, model_path: str) -> Dict:
        """Trigger an on-demand download of the selected model (Seção 12)."""
        response = requests.post(
            f"{self.base_url}/api/pipeline/download_model",
            json={"model_path": model_path},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
