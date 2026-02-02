"""
Phoenix Datasets and Experiments Integration

This module provides functionality to:
1. Create Phoenix datasets from YAML test cases
2. Run experiments and track results
3. Compare different model configurations
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    # Try different Phoenix client import paths
    try:
        from phoenix.client import Client
    except ImportError:
        try:
            from arize.phoenix.client import Client
        except ImportError:
            # Phoenix client may not be available for self-hosted
            Client = None
    PHOENIX_AVAILABLE = Client is not None
except Exception:
    PHOENIX_AVAILABLE = False
    Client = None

from logger import get_module_logger

logger = get_module_logger(__name__)


class PhoenixDatasetManager:
    """Manages Phoenix datasets and experiments for evaluation."""
    
    def __init__(
        self,
        phoenix_host: str = "http://localhost:6006",
        project_name: str = "contract-kg-evaluation",
    ):
        """
        Initialize Phoenix dataset manager.
        
        Args:
            phoenix_host: Phoenix server URL
            project_name: Project name for organizing datasets/experiments
        """
        if not PHOENIX_AVAILABLE:
            raise ImportError(
                "Phoenix client not available. Install with: pip install arize-phoenix"
            )
        
        self.phoenix_host = phoenix_host
        self.project_name = project_name
        
        # Initialize Phoenix client
        # For self-hosted Phoenix, we connect via the host URL
        try:
            # Phoenix client can connect to self-hosted instance
            # If no endpoint specified, it uses default localhost:6006
            if phoenix_host and phoenix_host != "http://localhost:6006":
                # For custom endpoints, we may need to set environment variable
                import os
                os.environ.setdefault("PHOENIX_ENDPOINT", phoenix_host)
            
            self.client = Client()
            logger.info(f"Initialized Phoenix client (endpoint: {phoenix_host})")
        except Exception as e:
            logger.warning(f"Could not initialize Phoenix client: {e}")
            logger.info("Datasets/experiments will be created when Phoenix is available")
            self.client = None
    
    def create_dataset_from_test_cases(
        self,
        test_cases: list[dict[str, Any]],
        dataset_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a Phoenix dataset from test cases.
        
        Args:
            test_cases: List of test case dictionaries
            dataset_name: Name for the dataset (auto-generated if not provided)
            
        Returns:
            Dataset ID if successful, None otherwise
        """
        if not self.client:
            logger.warning("Phoenix client not available, skipping dataset creation")
            return None
        
        if not dataset_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dataset_name = f"{self.project_name}_dataset_{timestamp}"
        
        try:
            # Prepare data for Phoenix dataset
            # Phoenix expects inputs and outputs
            inputs = []
            outputs = []
            metadata = []
            
            for test_case in test_cases:
                # Input: the question/query
                inputs.append({
                    "question": test_case.get("question", ""),
                    "test_id": test_case.get("id", ""),
                    "category": test_case.get("category", ""),
                    "level": test_case.get("level", ""),
                })
                
                # Output: expected results (for reference)
                outputs.append({
                    "expected_keywords": test_case.get("expected_keywords", []),
                    "expected_keywords_any": test_case.get("expected_keywords_any", []),
                    "min_confidence": test_case.get("min_confidence", 0.0),
                    "min_kg_facts": test_case.get("min_kg_facts", 0),
                })
                
                # Metadata: additional test case info
                metadata.append({
                    "name": test_case.get("name", ""),
                    "description": test_case.get("description", ""),
                    "tags": test_case.get("tags", []),
                })
            
            # Create dataset using Phoenix client API
            # Phoenix expects inputs and outputs as lists of dicts
            dataset = self.client.datasets.create_dataset(
                name=dataset_name,
                inputs=inputs,
                outputs=outputs,
            )
            
            dataset_id = dataset.id if hasattr(dataset, 'id') else getattr(dataset, 'name', dataset_name)
            logger.info(f"Created Phoenix dataset: {dataset_name} (ID: {dataset_id})")
            return dataset_id
            
        except Exception as e:
            logger.error(f"Failed to create Phoenix dataset: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def create_experiment(
        self,
        experiment_name: str,
        dataset_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Create a Phoenix experiment.
        
        Note: Phoenix experiments are typically created by running experiments on datasets.
        This method prepares the experiment structure.
        
        Args:
            experiment_name: Name for the experiment
            dataset_id: Optional dataset ID to use
            description: Experiment description
            
        Returns:
            Experiment info dict if successful, None otherwise
        """
        if not self.client:
            logger.warning("Phoenix client not available, skipping experiment creation")
            return None
        
        try:
            # Get dataset if dataset_id provided
            dataset = None
            if dataset_id:
                try:
                    dataset = self.client.datasets.get_dataset(dataset=dataset_id)
                except Exception as e:
                    logger.warning(f"Could not get dataset {dataset_id}: {e}")
            
            # Return experiment info (actual experiment is created when running)
            experiment_info = {
                "name": experiment_name,
                "dataset": dataset,
                "description": description or f"Evaluation experiment: {experiment_name}",
            }
            
            logger.info(f"Prepared Phoenix experiment: {experiment_name}")
            return experiment_info
            
        except Exception as e:
            logger.error(f"Failed to create Phoenix experiment: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def log_experiment_result(
        self,
        experiment_info: dict[str, Any],
        test_case_id: str,
        query: str,
        answer: str,
        metrics: dict[str, Any],
    ) -> bool:
        """
        Log a result to a Phoenix experiment.
        
        Note: Results are tracked via OpenTelemetry traces automatically.
        This method adds metadata to help identify experiment runs.
        
        Args:
            experiment_info: Experiment info dict from create_experiment
            test_case_id: Test case identifier
            query: Input query
            answer: Generated answer
            metrics: Evaluation metrics (confidence, kg_facts, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        # Phoenix automatically tracks results via OpenTelemetry traces
        # We just need to ensure traces are being sent with proper metadata
        # The traces will be visible in Phoenix UI and can be used to create datasets/experiments
        
        try:
            # Add experiment metadata to current trace if available
            from opentelemetry import trace
            tracer = trace.get_tracer(__name__)
            span = tracer.start_span("experiment_result")
            span.set_attribute("experiment_name", experiment_info.get("name", ""))
            span.set_attribute("test_case_id", test_case_id)
            span.set_attribute("query", query)
            span.set_attribute("answer", answer[:200])  # Truncate long answers
            for key, value in metrics.items():
                span.set_attribute(f"metric.{key}", str(value))
            span.end()
            return True
            
        except Exception as e:
            logger.warning(f"Failed to log experiment result: {e}")
            return False


def create_phoenix_dataset_manager(
    phoenix_host: Optional[str] = None,
    project_name: str = "contract-kg-evaluation",
) -> Optional[PhoenixDatasetManager]:
    """
    Factory function to create a Phoenix dataset manager.
    
    Args:
        phoenix_host: Phoenix server URL (defaults to localhost:6006)
        project_name: Project name for datasets/experiments
        
    Returns:
        PhoenixDatasetManager instance or None if Phoenix is not available
    """
    if not PHOENIX_AVAILABLE:
        logger.warning("Phoenix client not installed, datasets/experiments disabled")
        return None
    
    if not phoenix_host:
        phoenix_host = os.getenv("PHOENIX_HOST", "http://localhost:6006")
    
    try:
        return PhoenixDatasetManager(
            phoenix_host=phoenix_host,
            project_name=project_name,
        )
    except Exception as e:
        logger.warning(f"Could not initialize Phoenix dataset manager: {e}")
        return None
