"""
Example Usage of the Production-Grade Logging System

This file demonstrates how to use the new logging system in various scenarios.
"""

# Example 1: Basic Usage
from logger import get_module_logger

logger = get_module_logger(__name__)
logger.info("Basic logging example")


# Example 2: With Context Binding
def process_document(doc_id: str):
    """Example function with context binding."""
    logger = get_module_logger(__name__).bind(
        function="process_document",
        doc_id=doc_id
    )
    
    logger.info("Starting document processing")
    
    try:
        # Simulate work
        logger.debug("Processing step 1")
        logger.debug("Processing step 2")
        logger.info("Document processed successfully", pages=10)
    except Exception as e:
        logger.exception("Failed to process document", error=str(e))
        raise


# Example 3: Using ServiceFactory (Dependency Injection)
from service_factory import get_service_factory


class ExampleService:
    """Example service using dependency injection for logging."""
    
    def __init__(self, logger=None):
        if logger is None:
            factory = get_service_factory()
            logger = factory.get_logger(self.__class__.__name__)
        self.logger = logger
    
    def do_work(self):
        """Example method with logging."""
        self.logger.info("Doing work")
        self.logger = self.logger.bind(operation="do_work")
        self.logger.info("Work in progress")
        self.logger.info("Work completed")


# Example 4: Performance Metrics
import time


def example_with_metrics():
    """Example with performance metrics."""
    logger = get_module_logger(__name__)
    
    start = time.time()
    # Simulate work
    time.sleep(0.1)
    duration_ms = (time.time() - start) * 1000
    
    logger.log_performance("example_operation", duration_ms)
    logger.log_metric("items_processed", 42, batch_id="batch123")


# Example 5: JSON Format for Analytics
def example_json_logging():
    """Example with JSON format for analytics."""
    logger = get_module_logger(__name__, enable_json=True)
    
    logger.info(
        "Query executed",
        query_type="SPARQL",
        duration_ms=150.5,
        result_count=42,
        graph_id="doc123"
    )


# Example 6: Module-Level Logger
class GraphManager:
    """Example class using module logger."""
    
    def __init__(self):
        self.logger = get_module_logger(__name__)
    
    def load_graph(self, graph_id: str):
        """Load a graph with logging."""
        logger = self.logger.bind(graph_id=graph_id)
        logger.info("Loading graph")
        
        try:
            # Simulate loading
            triple_count = 150
            logger.info("Graph loaded", triple_count=triple_count)
        except Exception as e:
            logger.exception("Failed to load graph", error=str(e))
            raise


if __name__ == "__main__":
    # Run examples
    print("Example 1: Basic Usage")
    logger = get_module_logger(__name__)
    logger.info("This is a test message")
    
    print("\nExample 2: Context Binding")
    process_document("doc123")
    
    print("\nExample 3: Dependency Injection")
    service = ExampleService()
    service.do_work()
    
    print("\nExample 4: Performance Metrics")
    example_with_metrics()
    
    print("\nExample 5: JSON Format")
    example_json_logging()
    
    print("\nExample 6: Module-Level")
    gm = GraphManager()
    gm.load_graph("graph123")
