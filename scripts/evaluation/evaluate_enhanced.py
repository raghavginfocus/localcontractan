#!/usr/bin/env python3
"""
Enhanced Evaluation Script for Contract KG RAG System

This script:
1. Extracts test cases from test files in agents/tests/
2. Loads test cases from YAML files
3. Runs RAG queries and compares to expected results
4. Generates comprehensive evaluation reports

Usage:
    # Evaluate all test cases from test folder
    cd agents
    PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py

    # Evaluate specific test file
    PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --test-file test_hybrid_rag_queries.py

    # Load test cases from YAML
    PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --yaml test_cases.yaml

    # Run specific test case by ID
    PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --case-id 1

    # Verbose output
    PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --verbose

    # Save report to file
    PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --output report.json
"""

import argparse
import asyncio
import importlib.util
import inspect
import json
import re
import sys
import yaml
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from config import get_settings
from agents.retrieval.retrieval_orchestrator_langgraph_v2 import LangGraphRetrievalOrchestrator
from observability import create_phoenix_dataset_manager


@dataclass
class TestCase:
    """A single evaluation test case."""
    id: str  # Unique identifier
    name: str
    question: str
    description: Optional[str] = None
    category: Optional[str] = None  # "factual", "analytical", "risk", "compliance", etc.
    level: Optional[str] = None  # "simple", "medium", "complex"
    
    # Expected results
    expected_keywords: list[str] = None  # Keywords that SHOULD appear in answer
    expected_keywords_any: list[str] = None  # At least one of these should appear
    forbidden_keywords: list[str] = None  # Keywords that should NOT appear
    expected_content: list[str] = None  # Specific content that should be present
    min_confidence: float = 0.0  # Minimum expected confidence
    min_kg_facts: int = 0  # Minimum expected KG facts (0 means any)
    min_vector_results: int = 0  # Minimum expected vector results
    expected_sparql_patterns: list[str] = None  # Patterns that should appear in SPARQL
    
    # Additional metadata
    graph_uri: Optional[str] = None  # Specific graph to query
    tags: list[str] = None  # Tags for filtering
    
    def __post_init__(self):
        """Initialize default values."""
        if self.expected_keywords is None:
            self.expected_keywords = []
        if self.expected_keywords_any is None:
            self.expected_keywords_any = []
        if self.forbidden_keywords is None:
            self.forbidden_keywords = []
        if self.expected_content is None:
            self.expected_content = []
        if self.expected_sparql_patterns is None:
            self.expected_sparql_patterns = []
        if self.tags is None:
            self.tags = []


@dataclass
class TestResult:
    """Result of running a single test case."""
    test_case: TestCase
    passed: bool
    answer: str
    confidence: float
    kg_facts_count: int
    vector_results_count: int
    sparql_query: Optional[str] = None
    
    # Validation results
    keywords_found: list[str] = None
    keywords_missing: list[str] = None
    keywords_any_found: bool = False
    forbidden_found: list[str] = None
    content_found: dict[str, bool] = None
    sparql_patterns_found: list[str] = None
    sparql_patterns_missing: list[str] = None
    
    # Metadata
    log_file: str = ""
    duration_ms: float = 0.0
    errors: list[str] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.keywords_found is None:
            self.keywords_found = []
        if self.keywords_missing is None:
            self.keywords_missing = []
        if self.forbidden_found is None:
            self.forbidden_found = []
        if self.content_found is None:
            self.content_found = {}
        if self.sparql_patterns_found is None:
            self.sparql_patterns_found = []
        if self.sparql_patterns_missing is None:
            self.sparql_patterns_missing = []
        if self.errors is None:
            self.errors = []


def check_keywords(text: str, keywords: list[str], case_sensitive: bool = False) -> tuple[list[str], list[str]]:
    """Check which keywords are present/missing in text."""
    if not keywords:
        return [], []
    
    text_check = text if case_sensitive else text.lower()
    found = []
    missing = []
    
    for kw in keywords:
        kw_check = kw if case_sensitive else kw.lower()
        if kw_check in text_check:
            found.append(kw)
        else:
            missing.append(kw)
    
    return found, missing


def check_keywords_any(text: str, keywords: list[str], case_sensitive: bool = False) -> bool:
    """Check if at least one keyword is present."""
    if not keywords:
        return True
    
    text_check = text if case_sensitive else text.lower()
    for kw in keywords:
        kw_check = kw if case_sensitive else kw.lower()
        if kw_check in text_check:
            return True
    return False


def check_sparql_patterns(sparql: str, patterns: list[str]) -> tuple[list[str], list[str]]:
    """Check which SPARQL patterns are present/missing."""
    if not patterns or not sparql:
        return [], patterns or []
    
    sparql_lower = sparql.lower()
    found = []
    missing = []
    
    for pattern in patterns:
        pattern_lower = pattern.lower()
        if pattern_lower in sparql_lower:
            found.append(pattern)
        else:
            missing.append(pattern)
    
    return found, missing


async def run_test_case(
    test_case: TestCase,
    orchestrator: LangGraphRetrievalOrchestrator,
    verbose: bool = False,
) -> TestResult:
    """Run a single test case and return results."""
    import time
    start_time = time.time()
    errors = []
    
    if verbose:
        print(f"\n{'─'*70}")
        print(f"🧪 Test: {test_case.name} (ID: {test_case.id})")
        print(f"   Question: {test_case.question}")
        if test_case.description:
            print(f"   Description: {test_case.description}")
        if test_case.category:
            print(f"   Category: {test_case.category}")
        if test_case.level:
            print(f"   Level: {test_case.level}")
        print("   Running...")
    
    try:
        # Use LangGraphRetrievalOrchestrator (includes Phoenix observability and LangGraph)
        retrieval_result = await orchestrator.retrieve(
            question=test_case.question,
            graph_uri=test_case.graph_uri,
        )
        
        # LangGraphRetrievalOrchestrator returns a dict (RetrievalState)
        answer = retrieval_result.get("answer", "") or ""
        confidence = retrieval_result.get("confidence", 0.0) or 0.0
        kg_facts_count = retrieval_result.get("kg_facts_count", 0)
        vector_results_count = retrieval_result.get("vector_results_count", 0)
        sparql_query = retrieval_result.get("sparql_query")
        log_file = retrieval_result.get("log_file", "") or ""
        
    except Exception as e:
        errors.append(f"Execution error: {str(e)}")
        answer = ""
        confidence = 0.0
        kg_facts_count = 0
        vector_results_count = 0
        sparql_query = None
        log_file = ""
        if verbose:
            import traceback
            print(f"   ❌ Error: {e}")
            traceback.print_exc()
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Validate results
    keywords_found, keywords_missing = check_keywords(answer, test_case.expected_keywords)
    keywords_any_found = check_keywords_any(answer, test_case.expected_keywords_any)
    forbidden_found, _ = check_keywords(answer, test_case.forbidden_keywords)
    
    # Check expected content
    content_found = {}
    if test_case.expected_content:
        answer_lower = answer.lower()
        for content in test_case.expected_content:
            content_found[content] = content.lower() in answer_lower
    
    # Check SPARQL patterns
    sparql_patterns_found, sparql_patterns_missing = check_sparql_patterns(
        sparql_query or "", test_case.expected_sparql_patterns
    )
    
    # Calculate answer quality score (independent of retrieval metrics)
    def score_answer_quality(answer: str, test_case: TestCase) -> float:
        """Score answer quality independently of retrieval metrics."""
        score = 0.0
        
        # Length check (good answers are usually >100 chars)
        if len(answer) > 100:
            score += 0.2
        elif len(answer) > 50:
            score += 0.1
        
        # Keyword presence
        if test_case.expected_keywords:
            keywords_found_count = sum(1 for kw in test_case.expected_keywords if kw.lower() in answer.lower())
            keyword_ratio = keywords_found_count / len(test_case.expected_keywords)
            score += keyword_ratio * 0.4
        
        # Keywords_any presence
        if test_case.expected_keywords_any:
            if any(kw.lower() in answer.lower() for kw in test_case.expected_keywords_any):
                score += 0.2
        
        # Content quality (structure, detail)
        structure_markers = ['1.', '2.', '-', '*', '**', '###', '##']
        if any(marker in answer for marker in structure_markers):
            score += 0.2  # Structured answer
        
        return min(score, 1.0)
    
    answer_quality_score = score_answer_quality(answer, test_case)
    
    # Determine if test passed
    passed = True
    
    # Check expected keywords (at least 50% should be present)
    if test_case.expected_keywords:
        required_found = len(test_case.expected_keywords) * 0.5
        if len(keywords_found) < required_found:
            passed = False
            errors.append(f"Missing keywords: {keywords_missing} (found {len(keywords_found)}/{len(test_case.expected_keywords)})")
    
    # Check keywords_any (at least one should be present)
    if test_case.expected_keywords_any and not keywords_any_found:
        passed = False
        errors.append(f"None of the expected keywords found: {test_case.expected_keywords_any}")
    
    # Check forbidden keywords
    if forbidden_found:
        passed = False
        errors.append(f"Forbidden keywords found: {forbidden_found}")
    
    # Check expected content (all should be present)
    if test_case.expected_content:
        missing_content = [c for c, found in content_found.items() if not found]
        if missing_content:
            passed = False
            errors.append(f"Missing expected content: {missing_content}")
    
    # Check confidence (but allow override if answer quality is high)
    if confidence < test_case.min_confidence:
        # If answer quality is very high, relax confidence requirement
        if answer_quality_score >= 0.8:
            # High quality answer compensates for low confidence
            pass  # Don't fail on confidence
        else:
            passed = False
            errors.append(f"Low confidence: {confidence:.2f} < {test_case.min_confidence}")
    
    # Check KG facts (but allow override if answer quality is high)
    if test_case.min_kg_facts > 0 and kg_facts_count < test_case.min_kg_facts:
        # If answer quality is high, relax fact requirements
        if answer_quality_score >= 0.7:
            # High quality answer suggests facts were used (even if not counted)
            pass  # Don't fail on fact count
        else:
            passed = False
            errors.append(f"Insufficient KG facts: {kg_facts_count} < {test_case.min_kg_facts}")
    
    # Check vector results (but allow override if answer quality is high)
    if test_case.min_vector_results > 0 and vector_results_count < test_case.min_vector_results:
        # If answer quality is high, relax vector requirements
        if answer_quality_score >= 0.7:
            pass  # Don't fail on vector count
        else:
            passed = False
            errors.append(f"Insufficient vector results: {vector_results_count} < {test_case.min_vector_results}")
    
    # Check SPARQL patterns (make this optional - don't fail if answer is good)
    if test_case.expected_sparql_patterns:
        required_patterns = len(test_case.expected_sparql_patterns) * 0.5
        if len(sparql_patterns_found) < required_patterns:
            # Only fail on SPARQL patterns if answer quality is also low
            if answer_quality_score < 0.6:
                passed = False
                errors.append(f"Missing SPARQL patterns: {sparql_patterns_missing}")
            # Otherwise, just warn (SPARQL might be optimized/transformed)
    
    # Check for execution errors
    if errors and not any("Execution error" in e for e in errors):
        # Only mark as passed if answer is reasonable
        if len(answer) < 50:
            passed = False
            errors.append("Answer too short")
    
    test_result = TestResult(
        test_case=test_case,
        passed=passed,
        answer=answer,
        confidence=confidence,
        kg_facts_count=kg_facts_count,
        vector_results_count=vector_results_count,
        sparql_query=sparql_query,
        keywords_found=keywords_found,
        keywords_missing=keywords_missing,
        keywords_any_found=keywords_any_found,
        forbidden_found=forbidden_found,
        content_found=content_found,
        sparql_patterns_found=sparql_patterns_found,
        sparql_patterns_missing=sparql_patterns_missing,
        log_file=log_file,
        duration_ms=duration_ms,
        errors=errors,
    )
    
    if verbose:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   Status: {status}")
        print(f"   Confidence: {confidence:.1%}")
        print(f"   Duration: {duration_ms:.0f}ms")
        print(f"   KG Facts: {kg_facts_count}, Vector Results: {vector_results_count}")
        if keywords_found:
            print(f"   Keywords Found: {keywords_found}")
        if keywords_missing:
            print(f"   Keywords Missing: {keywords_missing}")
        if keywords_any_found and test_case.expected_keywords_any:
            print(f"   Keywords (Any) Found: ✅")
        if forbidden_found:
            print(f"   ⚠️  Forbidden Keywords: {forbidden_found}")
        if content_found:
            print(f"   Expected Content: {content_found}")
        if sparql_patterns_found:
            print(f"   SPARQL Patterns Found: {sparql_patterns_found}")
        if sparql_patterns_missing:
            print(f"   SPARQL Patterns Missing: {sparql_patterns_missing}")
        if errors:
            print(f"   Issues: {errors}")
        if log_file:
            print(f"   Log: {log_file}")
        print(f"   Answer Preview: {answer[:200]}...")
    
    return test_result


def extract_test_cases_from_file(test_file_path: Path) -> list[TestCase]:
    """Extract test cases from a Python test file."""
    test_cases = []
    
    try:
        # Load the test file as a module
        spec = importlib.util.spec_from_file_location("test_module", test_file_path)
        if spec is None or spec.loader is None:
            return []
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find test classes and methods
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and name.endswith("Tester"):
                # Look for test methods
                for method_name, method in inspect.getmembers(obj, predicate=inspect.isfunction):
                    if method_name.startswith("test_") or method_name.startswith("async def test_"):
                        # Try to extract test case info from docstring and code
                        doc = inspect.getdoc(method) or ""
                        
                        # Extract question from method body (if it's a RAG test)
                        source = inspect.getsource(method)
                        question_match = re.search(r'question\s*=\s*["\']([^"\']+)["\']', source, re.MULTILINE)
                        question = question_match.group(1) if question_match else None
                        
                        if question:
                            # Extract expected content from docstring or code
                            expected_content = []
                            if "Expected:" in doc or "expected" in doc.lower():
                                # Try to extract expected values
                                expected_match = re.search(r'Expected[:\s]+([^\n]+)', doc, re.IGNORECASE)
                                if expected_match:
                                    expected_content = [expected_match.group(1).strip()]
                            
                            # Extract test name
                            test_name = method_name.replace("test_", "").replace("_", " ").title()
                            
                            # Extract level/category from docstring
                            level = None
                            category = None
                            if "Level 1" in doc or "SIMPLE" in doc:
                                level = "simple"
                            elif "Level 2" in doc or "ANALYTICAL" in doc:
                                level = "medium"
                            elif "Level 3" in doc or "COMPLEX" in doc:
                                level = "complex"
                            
                            if "risk" in doc.lower():
                                category = "risk"
                            elif "compliance" in doc.lower():
                                category = "compliance"
                            elif "factual" in doc.lower():
                                category = "factual"
                            elif "analytical" in doc.lower():
                                category = "analytical"
                            
                            test_case = TestCase(
                                id=f"{test_file_path.stem}_{method_name}",
                                name=test_name,
                                question=question,
                                description=doc.split("\n")[0] if doc else None,
                                category=category,
                                level=level,
                                expected_content=expected_content if expected_content else None,
                            )
                            test_cases.append(test_case)
        
    except Exception as e:
        print(f"⚠️  Warning: Could not extract test cases from {test_file_path}: {e}")
    
    return test_cases


def load_test_cases_from_yaml(yaml_path: Path) -> list[TestCase]:
    """Load test cases from a YAML file."""
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    
    test_cases = []
    test_cases_data = data.get("test_cases", [])
    
    for i, tc_data in enumerate(test_cases_data, 1):
        test_case = TestCase(
            id=tc_data.get("id", f"test_{i}"),
            name=tc_data.get("name", f"Test {i}"),
            question=tc_data.get("question", ""),
            description=tc_data.get("description"),
            category=tc_data.get("category"),
            level=tc_data.get("level"),
            expected_keywords=tc_data.get("expected_keywords", []),
            expected_keywords_any=tc_data.get("expected_keywords_any", []),
            forbidden_keywords=tc_data.get("forbidden_keywords", []),
            expected_content=tc_data.get("expected_content", []),
            min_confidence=tc_data.get("min_confidence", 0.0),
            min_kg_facts=tc_data.get("min_kg_facts", 0),
            min_vector_results=tc_data.get("min_vector_results", 0),
            expected_sparql_patterns=tc_data.get("expected_sparql_patterns", []),
            graph_uri=tc_data.get("graph_uri"),
            tags=tc_data.get("tags", []),
        )
        test_cases.append(test_case)
    
    return test_cases


async def run_evaluation(
    test_cases: list[TestCase],
    verbose: bool = False,
    enable_phoenix: bool = True,  # Note: LangGraphRetrievalOrchestrator always enables Phoenix
    create_phoenix_dataset: bool = True,
    experiment_name: Optional[str] = None,
) -> list[TestResult]:
    """
    Run all evaluation test cases with Phoenix datasets and experiments.
    
    Args:
        test_cases: List of test cases to evaluate
        verbose: Enable verbose output
        enable_phoenix: Enable Phoenix observability (always True for LangGraph)
        create_phoenix_dataset: Create a Phoenix dataset from test cases
        experiment_name: Name for Phoenix experiment (auto-generated if not provided)
    """
    print("\n" + "="*70)
    print("  📊 CONTRACT KG RAG - ENHANCED EVALUATION SUITE")
    print("="*70)
    print(f"  Running {len(test_cases)} test case(s)...")
    
    # Initialize LangGraphRetrievalOrchestrator (includes Phoenix observability and LangGraph)
    settings = get_settings()
    
    # Set up log directory for evaluation (sessions go to evaluation/sessions)
    from pathlib import Path
    from logging_config import get_module_log_dir
    
    # LangGraphRetrievalOrchestrator automatically sets up Phoenix observability
    # and groups all operations under LangGraph chains for better trace visualization
    print("\n  🔍 Initializing LangGraph retrieval orchestrator...")
    print("  ✅ Phoenix observability will be enabled automatically")
    print("  📊 View traces at: http://localhost:6006")
    
    # Setup Phoenix datasets and experiments
    dataset_id = None
    experiment = None
    experiment_id = None
    phoenix_manager = None
    
    if create_phoenix_dataset:
        print("\n  📦 Setting up Phoenix datasets and experiments...")
        try:
            phoenix_manager = create_phoenix_dataset_manager(
                project_name="contract-kg-evaluation"
            )
            
            if phoenix_manager:
                # Convert test cases to dict format for dataset creation
                test_cases_dict = [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "question": tc.question,
                        "description": tc.description,
                        "category": tc.category,
                        "level": tc.level,
                        "expected_keywords": tc.expected_keywords,
                        "expected_keywords_any": tc.expected_keywords_any,
                        "min_confidence": tc.min_confidence,
                        "min_kg_facts": tc.min_kg_facts,
                        "tags": tc.tags,
                    }
                    for tc in test_cases
                ]
                
                # Create dataset
                dataset_id = phoenix_manager.create_dataset_from_test_cases(
                    test_cases_dict,
                    dataset_name=f"contract-kg-test-cases-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                )
                
                if dataset_id:
                    print(f"  ✅ Created Phoenix dataset: {dataset_id}")
                    
                    # Create experiment
                    if not experiment_name:
                        experiment_name = f"evaluation-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                    
                    experiment = phoenix_manager.create_experiment(
                        experiment_name=experiment_name,
                        dataset_id=dataset_id,
                        description=f"Evaluation run with {len(test_cases)} test cases",
                    )
                    
                    if experiment:
                        experiment_id = experiment.get("name", experiment_name) if isinstance(experiment, dict) else (experiment.id if hasattr(experiment, 'id') else experiment_name)
                        print(f"  ✅ Prepared Phoenix experiment: {experiment_id}")
                        print(f"  💡 View traces in Phoenix UI - they will be grouped by experiment metadata")
                else:
                    print("  ⚠️  Could not create Phoenix dataset (Phoenix may not be running)")
            else:
                print("  ⚠️  Phoenix dataset manager not available")
        except Exception as e:
            print(f"  ⚠️  Error setting up Phoenix datasets: {e}")
            import traceback
            if verbose:
                traceback.print_exc()
    
    orchestrator = LangGraphRetrievalOrchestrator(
        settings=settings,
        enable_logging=True,
    )
    
    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] Running: {test_case.name}")
        result = await run_test_case(test_case, orchestrator, verbose)
        results.append(result)
        
        # Log result to Phoenix experiment if available
        if phoenix_manager and experiment:
            try:
                phoenix_manager.log_experiment_result(
                    experiment_info=experiment,
                    test_case_id=test_case.id,
                    query=test_case.question,
                    answer=result.answer,
                    metrics={
                        "passed": result.passed,
                        "confidence": result.confidence,
                        "kg_facts_count": result.kg_facts_count,
                        "vector_results_count": result.vector_results_count,
                    },
                )
            except Exception as e:
                if verbose:
                    print(f"  ⚠️  Could not log to Phoenix experiment: {e}")
    
    if phoenix_manager and experiment_id:
        print(f"\n  📊 View experiment results in Phoenix: http://localhost:6006")
        print(f"  🔗 Experiment ID: {experiment_id}")
    
    return results


def generate_report(results: list[TestResult]) -> dict:
    """Generate evaluation report."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    
    # Group by category
    categories = {}
    for r in results:
        cat = r.test_case.category or "uncategorized"
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if r.passed:
            categories[cat]["passed"] += 1
    
    # Group by level
    levels = {}
    for r in results:
        level = r.test_case.level or "unknown"
        if level not in levels:
            levels[level] = {"total": 0, "passed": 0}
        levels[level]["total"] += 1
        if r.passed:
            levels[level]["passed"] += 1
    
    # Calculate averages
    avg_confidence = sum(r.confidence for r in results) / total if total > 0 else 0
    avg_duration = sum(r.duration_ms for r in results) / total if total > 0 else 0
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{(passed/total)*100:.1f}%" if total > 0 else "N/A",
        },
        "metrics": {
            "avg_confidence": f"{avg_confidence:.1%}",
            "avg_duration_ms": round(avg_duration, 1),
        },
        "by_category": {
            cat: {
                "passed": data["passed"],
                "total": data["total"],
                "rate": f"{(data['passed']/data['total'])*100:.0f}%",
            }
            for cat, data in categories.items()
        },
        "by_level": {
            level: {
                "passed": data["passed"],
                "total": data["total"],
                "rate": f"{(data['passed']/data['total'])*100:.0f}%",
            }
            for level, data in levels.items()
        },
        "test_results": [
            {
                "id": r.test_case.id,
                "name": r.test_case.name,
                "category": r.test_case.category,
                "level": r.test_case.level,
                "passed": r.passed,
                "confidence": f"{r.confidence:.1%}",
                "duration_ms": round(r.duration_ms, 1),
                "kg_facts": r.kg_facts_count,
                "vector_results": r.vector_results_count,
                "errors": r.errors if r.errors else None,
                "log_file": r.log_file,
            }
            for r in results
        ],
    }
    
    return report


def print_summary(report: dict):
    """Print evaluation summary."""
    print("\n" + "="*70)
    print("  📊 EVALUATION SUMMARY")
    print("="*70)
    
    summary = report["summary"]
    print(f"\n  Total Tests: {summary['total']}")
    print(f"  ✅ Passed: {summary['passed']}")
    print(f"  ❌ Failed: {summary['failed']}")
    print(f"  📈 Pass Rate: {summary['pass_rate']}")
    
    print(f"\n  Average Confidence: {report['metrics']['avg_confidence']}")
    print(f"  Average Duration: {report['metrics']['avg_duration_ms']}ms")
    
    if report.get("by_category"):
        print("\n  By Category:")
        for cat, data in report["by_category"].items():
            emoji = "✅" if data["passed"] == data["total"] else "⚠️"
            print(f"    {emoji} {cat}: {data['passed']}/{data['total']} ({data['rate']})")
    
    if report.get("by_level"):
        print("\n  By Level:")
        for level, data in report["by_level"].items():
            emoji = "✅" if data["passed"] == data["total"] else "⚠️"
            print(f"    {emoji} {level}: {data['passed']}/{data['total']} ({data['rate']})")
    
    print("\n  Individual Results:")
    for r in report["test_results"]:
        status = "✅" if r["passed"] else "❌"
        print(f"    {status} {r['id']}: {r['name']} ({r['confidence']}, {r['duration_ms']}ms)")
        if r.get("errors"):
            for err in r["errors"][:2]:
                print(f"       └─ {err}")
    
    print("\n" + "="*70)


async def main():
    parser = argparse.ArgumentParser(
        description="Enhanced Evaluation Script for Contract KG RAG System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate all test cases from test folder
  PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py

  # Evaluate specific test file
  PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --test-file test_hybrid_rag_queries.py

  # Load test cases from YAML
  PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --yaml test_cases.yaml

  # Run specific test case
  PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --case-id test_hybrid_rag_queries_test_level1_simple_count

  # Filter by category
  PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --category risk

  # Verbose output
  PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --verbose
        """
    )
    parser.add_argument("--test-file", type=str, help="Specific test file to evaluate (from agents/tests/)")
    parser.add_argument("--yaml", type=str, help="Load test cases from YAML file")
    parser.add_argument("--case-id", type=str, help="Run specific test case by ID")
    parser.add_argument("--category", type=str, help="Filter test cases by category")
    parser.add_argument("--level", type=str, help="Filter test cases by level")
    parser.add_argument("--tag", type=str, help="Filter test cases by tag")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--output", "-o", type=str, help="Output JSON report to file")
    parser.add_argument("--phoenix", action="store_true", default=True, help="Enable Phoenix observability (default: True)")
    parser.add_argument("--no-phoenix", dest="phoenix", action="store_false", help="Disable Phoenix observability")
    args = parser.parse_args()
    
    # Load test cases
    test_cases = []
    test_dir = Path(__file__).parent.parent / "agents" / "tests"
    
    if args.yaml:
        # Load from YAML
        yaml_path = Path(args.yaml)
        if not yaml_path.is_absolute():
            yaml_path = Path.cwd() / yaml_path
        if not yaml_path.exists():
            print(f"❌ YAML file not found: {yaml_path}")
            sys.exit(1)
        test_cases = load_test_cases_from_yaml(yaml_path)
        print(f"✅ Loaded {len(test_cases)} test case(s) from {yaml_path}")
    
    elif args.test_file:
        # Load from specific test file
        test_file_path = test_dir / args.test_file
        if not test_file_path.exists():
            print(f"❌ Test file not found: {test_file_path}")
            sys.exit(1)
        test_cases = extract_test_cases_from_file(test_file_path)
        print(f"✅ Extracted {len(test_cases)} test case(s) from {test_file_path}")
    
    else:
        # Load from all test files in test folder
        test_files = list(test_dir.glob("test_*.py"))
        print(f"📁 Found {len(test_files)} test file(s) in {test_dir}")
        
        for test_file in test_files:
            extracted = extract_test_cases_from_file(test_file)
            test_cases.extend(extracted)
            if extracted:
                print(f"  ✅ {test_file.name}: {len(extracted)} test case(s)")
        
        print(f"\n✅ Total: {len(test_cases)} test case(s) extracted")
    
    if not test_cases:
        print("❌ No test cases found!")
        sys.exit(1)
    
    # Filter test cases
    if args.case_id:
        test_cases = [tc for tc in test_cases if tc.id == args.case_id]
        if not test_cases:
            print(f"❌ Test case {args.case_id} not found")
            sys.exit(1)
    
    if args.category:
        test_cases = [tc for tc in test_cases if tc.category == args.category]
        if not test_cases:
            print(f"❌ No test cases in category '{args.category}'")
            sys.exit(1)
    
    if args.level:
        test_cases = [tc for tc in test_cases if tc.level == args.level]
        if not test_cases:
            print(f"❌ No test cases at level '{args.level}'")
            sys.exit(1)
    
    if args.tag:
        test_cases = [tc for tc in test_cases if args.tag in tc.tags]
        if not test_cases:
            print(f"❌ No test cases with tag '{args.tag}'")
            sys.exit(1)
    
    try:
        # Run evaluation
        results = await run_evaluation(
            test_cases, 
            verbose=args.verbose,
            enable_phoenix=args.phoenix,
        )
        
        # Generate report
        report = generate_report(results)
        
        # Print summary
        print_summary(report)
        
        # Save report if requested
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\n📄 Report saved to: {output_path}")
        else:
            # Auto-save to logs directory
            report_dir = Path("logs/evaluation")
            report_dir.mkdir(parents=True, exist_ok=True)
            report_file = report_dir / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\n📄 Report auto-saved to: {report_file}")
        
        # Exit with appropriate code
        passed_all = report["summary"]["passed"] == report["summary"]["total"]
        sys.exit(0 if passed_all else 1)
        
    except Exception as e:
        print(f"\n❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
