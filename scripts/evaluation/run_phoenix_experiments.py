"""
Phoenix Experimentation Framework for Retrieval Testing

This script:
1. Loads test cases from YAML files (simple, medium, complex)
2. Runs experiments with different retrieval strategies
3. Adds custom OpenTelemetry spans for non-LLM operations
4. Logs all results to Phoenix for analysis and comparison
5. Generates experiment reports

Usage:
    cd agents && uv run python ../scripts/run_phoenix_experiments.py --test-suite simple
    cd agents && uv run python ../scripts/run_phoenix_experiments.py --test-suite medium
    cd agents && uv run python ../scripts/run_phoenix_experiments.py --test-suite all
"""

import asyncio
import sys
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from agents.retrieval.retrieval_orchestrator_langgraph_v2 import (
    LangGraphRetrievalOrchestrator
)
from agents.retrieval.retrieval_orchestrator import RetrievalOrchestrator
from logger import get_module_logger
from observability.phoenix_tracer import setup_phoenix_tracing

logger = get_module_logger(__name__)


class PhoenixExperimentRunner:
    """
    Runs retrieval experiments with Phoenix observability.
    
    Features:
    - Custom spans for SPARQL, vector search, synthesis
    - Experiment tracking with metadata
    - A/B testing different strategies
    - Comprehensive metrics collection
    """
    
    def __init__(self, test_suite: str = "simple"):
        """Initialize experiment runner."""
        self.test_suite = test_suite
        self.test_cases = self._load_test_cases()
        
        # Setup Phoenix tracing
        setup_phoenix_tracing()
        self.tracer = trace.get_tracer(__name__)
        
        # Initialize orchestrators for A/B testing
        self.orchestrator_v2 = LangGraphRetrievalOrchestrator(
            enable_logging=True,
            checkpoint_path="checkpoints/experiments.db",
        )
        
        self.orchestrator_v1 = RetrievalOrchestrator(
            enable_logging=True,
            enable_react=True,
        )
        
        logger.info(f"Initialized experiment runner for {test_suite} test suite")
    
    def _load_test_cases(self) -> list[dict[str, Any]]:
        """Load test cases from YAML files."""
        test_dir = Path(__file__).parent.parent / "agents" / "tests"
        
        if self.test_suite == "all":
            files = ["test_cases_simple.yaml", "test_cases_medium.yaml"]
        else:
            files = [f"test_cases_{self.test_suite}.yaml"]
        
        all_cases = []
        for file in files:
            file_path = test_dir / file
            if file_path.exists():
                with open(file_path) as f:
                    data = yaml.safe_load(f)
                    cases = data.get("test_cases", [])
                    all_cases.extend(cases)
                    logger.info(f"Loaded {len(cases)} test cases from {file}")
        
        return all_cases
    
    async def run_experiment(
        self,
        test_case: dict[str, Any],
        strategy: str = "langgraph_v2",
    ) -> dict[str, Any]:
        """
        Run a single experiment with custom spans.
        
        Args:
            test_case: Test case configuration
            strategy: "langgraph_v2" or "original"
        """
        question = test_case["question"]
        test_id = test_case["id"]
        
        # Create experiment span
        with self.tracer.start_as_current_span(
            "experiment",
            attributes={
                "experiment.id": test_id,
                "experiment.strategy": strategy,
                "experiment.question": question,
                "experiment.level": test_case.get("level", "unknown"),
                "experiment.category": test_case.get("category", "unknown"),
            }
        ) as experiment_span:
            
            try:
                # Run retrieval with selected strategy
                if strategy == "langgraph_v2":
                    result = await self._run_langgraph_v2(question, test_case)
                else:
                    result = await self._run_original(question, test_case)
                
                # Add result metrics to span
                experiment_span.set_attributes({
                    "result.success": result.get("success", False),
                    "result.confidence": result.get("confidence", 0.0),
                    "result.duration_ms": result.get("total_duration_ms", 0.0),
                    "result.answer_length": len(result.get("answer", "")),
                })
                
                # Evaluate against expected criteria
                evaluation = self._evaluate_result(result, test_case)
                experiment_span.set_attributes({
                    "evaluation.passed": evaluation["passed"],
                    "evaluation.score": evaluation["score"],
                })
                
                experiment_span.set_status(Status(StatusCode.OK))
                
                return {
                    "test_id": test_id,
                    "strategy": strategy,
                    "result": result,
                    "evaluation": evaluation,
                }
                
            except Exception as e:
                logger.error(f"Experiment failed: {e}")
                experiment_span.set_status(Status(StatusCode.ERROR, str(e)))
                experiment_span.record_exception(e)
                
                return {
                    "test_id": test_id,
                    "strategy": strategy,
                    "error": str(e),
                    "evaluation": {"passed": False, "score": 0.0},
                }
    
    async def _run_langgraph_v2(
        self,
        question: str,
        test_case: dict[str, Any]
    ) -> dict[str, Any]:
        """Run with LangGraph V2 orchestrator."""
        with self.tracer.start_as_current_span("langgraph_v2_retrieval"):
            result = await self.orchestrator_v2.retrieve(
                question=question,
                thread_id=f"exp_{test_case['id']}",
            )
            return result
    
    async def _run_original(
        self,
        question: str,
        test_case: dict[str, Any]
    ) -> dict[str, Any]:
        """Run with original orchestrator."""
        with self.tracer.start_as_current_span("original_retrieval"):
            result = await self.orchestrator_v1.retrieve(question=question)
            
            # Convert to dict format
            return {
                "question": result.question,
                "success": result.success,
                "answer": result.answer,
                "confidence": result.confidence,
                "total_duration_ms": result.total_duration_ms,
                "strategy": result.strategy.value if hasattr(result.strategy, 'value') else str(result.strategy),
            }
    
    def _evaluate_result(
        self,
        result: dict[str, Any],
        test_case: dict[str, Any]
    ) -> dict[str, Any]:
        """Evaluate result against expected criteria."""
        score = 0.0
        checks = []
        
        answer = result.get("answer", "").lower()
        confidence = result.get("confidence", 0.0)
        
        # Check confidence threshold
        min_confidence = test_case.get("min_confidence", 0.3)
        if confidence >= min_confidence:
            score += 0.3
            checks.append(f"✓ Confidence {confidence:.2f} >= {min_confidence}")
        else:
            checks.append(f"✗ Confidence {confidence:.2f} < {min_confidence}")
        
        # Check expected keywords (all must be present)
        expected_keywords = test_case.get("expected_keywords", [])
        if expected_keywords:
            found = sum(1 for kw in expected_keywords if kw.lower() in answer)
            keyword_score = found / len(expected_keywords)
            score += keyword_score * 0.3
            checks.append(f"Keywords: {found}/{len(expected_keywords)} found")
        
        # Check expected keywords (any can be present)
        expected_keywords_any = test_case.get("expected_keywords_any", [])
        if expected_keywords_any:
            found_any = any(kw.lower() in answer for kw in expected_keywords_any)
            if found_any:
                score += 0.2
                checks.append("✓ At least one expected keyword found")
            else:
                checks.append("✗ No expected keywords found")
        
        # Check answer is not empty
        if answer and len(answer) > 10:
            score += 0.2
            checks.append(f"✓ Answer provided ({len(answer)} chars)")
        else:
            checks.append("✗ No meaningful answer")
        
        passed = score >= 0.5  # Pass threshold
        
        return {
            "passed": passed,
            "score": score,
            "checks": checks,
            "confidence": confidence,
        }
    
    async def run_all_experiments(self, strategies: list[str] = None):
        """Run all test cases with specified strategies."""
        if strategies is None:
            strategies = ["langgraph_v2", "original"]
        
        results = []
        
        print(f"\n{'='*60}")
        print(f"Running Phoenix Experiments: {self.test_suite.upper()} Test Suite")
        print(f"Strategies: {', '.join(strategies)}")
        print(f"Test Cases: {len(self.test_cases)}")
        print(f"{'='*60}\n")
        
        for i, test_case in enumerate(self.test_cases, 1):
            print(f"\n[{i}/{len(self.test_cases)}] {test_case['name']}")
            print(f"Question: {test_case['question']}")
            print(f"Level: {test_case.get('level', 'unknown')}")
            
            for strategy in strategies:
                print(f"\n  Testing with {strategy}...")
                
                result = await self.run_experiment(test_case, strategy)
                results.append(result)
                
                # Print result
                if "error" in result:
                    print(f"    ✗ ERROR: {result['error']}")
                else:
                    eval_result = result["evaluation"]
                    status = "✓ PASS" if eval_result["passed"] else "✗ FAIL"
                    print(f"    {status} (score: {eval_result['score']:.2f})")
                    print(f"    Confidence: {eval_result['confidence']:.2%}")
                    
                    # Print answer preview
                    answer = result["result"].get("answer", "")
                    if answer:
                        preview = answer[:100] + "..." if len(answer) > 100 else answer
                        print(f"    Answer: {preview}")
        
        # Generate summary
        self._print_summary(results, strategies)
        
        return results
    
    def _print_summary(self, results: list[dict], strategies: list[str]):
        """Print experiment summary."""
        print(f"\n{'='*60}")
        print("EXPERIMENT SUMMARY")
        print(f"{'='*60}\n")
        
        for strategy in strategies:
            strategy_results = [r for r in results if r.get("strategy") == strategy]
            passed = sum(1 for r in strategy_results if r.get("evaluation", {}).get("passed", False))
            total = len(strategy_results)
            avg_score = sum(r.get("evaluation", {}).get("score", 0.0) for r in strategy_results) / total if total > 0 else 0
            
            print(f"{strategy.upper()}:")
            print(f"  Passed: {passed}/{total} ({passed/total*100:.1f}%)")
            print(f"  Average Score: {avg_score:.2f}")
            print()
        
        print(f"{'='*60}")
        print(f"View detailed traces in Phoenix UI: http://localhost:6006")
        print(f"{'='*60}\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Phoenix experiments")
    parser.add_argument(
        "--test-suite",
        choices=["simple", "medium", "complex", "all"],
        default="simple",
        help="Test suite to run"
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        choices=["langgraph_v2", "original"],
        default=["langgraph_v2", "original"],
        help="Strategies to test"
    )
    
    args = parser.parse_args()
    
    runner = PhoenixExperimentRunner(test_suite=args.test_suite)
    results = await runner.run_all_experiments(strategies=args.strategies)
    
    # Save results
    output_file = Path(f"experiment_results_{args.test_suite}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml")
    with open(output_file, "w") as f:
        yaml.dump({"results": results}, f, default_flow_style=False)
    
    print(f"\n✓ Results saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())


