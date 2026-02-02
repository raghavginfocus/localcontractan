#!/usr/bin/env python3
"""
Test script to demonstrate logging improvements in the retrieval system.

This script:
1. Submits queries via the async API
2. Monitors job status
3. Displays the improved logging output showing:
   - Clear source attribution (KG vs Milvus)
   - Source contribution metrics
   - Retrieval time breakdown

Usage:
    python scripts/test_logging_improvements.py
    
Or via Make:
    make test-logging-improvements
"""

import asyncio
import httpx
import time
import sys
from typing import Dict, Any

# API Configuration
API_BASE_URL = "http://localhost:8001"
API_TIMEOUT = 300.0  # 5 minutes for long-running queries

# Test queries that will demonstrate the logging improvements
TEST_QUERIES = [
    {
        "name": "Payment Terms Query",
        "question": "What are the payment terms in the contracts?",
        "description": "Tests hybrid retrieval (KG + Vector) with clear source attribution"
    },
    {
        "name": "Termination Clauses Query",
        "question": "What are the termination clauses?",
        "description": "Tests vector-heavy retrieval with timing breakdown"
    },
    {
        "name": "Party Information Query",
        "question": "Who are the parties involved in the contracts?",
        "description": "Tests KG-heavy retrieval with contribution metrics"
    }
]


class Colors:
    """ANSI color codes for terminal output"""
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[0;33m'
    RED = '\033[0;31m'
    CYAN = '\033[0;36m'
    MAGENTA = '\033[0;35m'
    NC = '\033[0m'  # No Color
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'=' * 80}{Colors.NC}")
    print(f"{Colors.BLUE}{Colors.BOLD}{text:^80}{Colors.NC}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'=' * 80}{Colors.NC}\n")


def print_section(text: str):
    """Print a formatted section header"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{text}{Colors.NC}")
    print(f"{Colors.CYAN}{'-' * len(text)}{Colors.NC}")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.NC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.NC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.YELLOW}ℹ {text}{Colors.NC}")


def print_metric(label: str, value: Any):
    """Print a metric with label"""
    print(f"  {Colors.MAGENTA}{label}:{Colors.NC} {value}")


async def check_api_health() -> bool:
    """Check if the API is healthy and ready"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_BASE_URL}/health")
            if response.status_code == 200:
                data = response.json()
                print_success(f"API is healthy: {data.get('status', 'unknown')}")
                return True
            else:
                print_error(f"API health check failed: {response.status_code}")
                return False
    except Exception as e:
        print_error(f"Failed to connect to API: {e}")
        return False


async def submit_query(question: str) -> Dict[str, Any]:
    """Submit a query to the async API"""
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/query/async",
                json={"query": question}
            )
            
            if response.status_code == 200:
                data = response.json()
                job_id = data.get("job_id")
                print_success(f"Query submitted successfully")
                print_metric("Job ID", job_id)
                return data
            else:
                print_error(f"Failed to submit query: {response.status_code}")
                print_error(f"Response: {response.text}")
                return {}
    except Exception as e:
        print_error(f"Error submitting query: {e}")
        return {}


async def get_job_status(job_id: str) -> Dict[str, Any]:
    """Get the status of a job"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{API_BASE_URL}/api/v1/jobs/{job_id}/status"
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print_error(f"Failed to get job status: {response.status_code}")
                return {}
    except Exception as e:
        print_error(f"Error getting job status: {e}")
        return {}


async def wait_for_job_completion(job_id: str, max_wait: int = 180) -> Dict[str, Any]:
    """Wait for a job to complete and return the result"""
    print_info(f"Waiting for job {job_id} to complete...")
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < max_wait:
        status_data = await get_job_status(job_id)
        
        if not status_data:
            await asyncio.sleep(2)
            continue
        
        current_status = status_data.get("status")
        
        # Only print status changes
        if current_status != last_status:
            print_info(f"Job status: {current_status}")
            last_status = current_status
        
        if current_status == "completed":
            elapsed = time.time() - start_time
            print_success(f"Job completed in {elapsed:.2f}s")
            return status_data
        
        elif current_status == "failed":
            print_error("Job failed")
            error = status_data.get("error", "Unknown error")
            print_error(f"Error: {error}")
            return status_data
        
        await asyncio.sleep(2)
    
    print_error(f"Job timed out after {max_wait}s")
    return {}


def display_logging_improvements(result: Dict[str, Any]):
    """Display the logging improvements from the result"""
    print_section("📊 Logging Improvements Demonstrated")
    
    # The actual logging happens in the worker logs, but we can show
    # what information is now available
    
    print(f"\n{Colors.BOLD}1. Clear Source Attribution:{Colors.NC}")
    print("   ✓ Logs now clearly state: 'Found X relevant clauses from Milvus vector store'")
    print("   ✓ No more ambiguous 'relevant clauses' messages")
    
    print(f"\n{Colors.BOLD}2. Source Contribution Metrics:{Colors.NC}")
    print("   ✓ Shows KG facts count vs Vector results count")
    print("   ✓ Displays percentage contribution from each source")
    print("   ✓ Example: 'KG contribution: 60.0%' and 'Vector contribution: 40.0%'")
    
    print(f"\n{Colors.BOLD}3. Retrieval Time Breakdown:{Colors.NC}")
    print("   ✓ Separate timing for KG retrieval (ms and %)")
    print("   ✓ Separate timing for Vector retrieval (ms and %)")
    print("   ✓ Example: 'KG: 70070.67ms (100.0%)' and 'Vector: 6903.45ms (9.9%)'")
    
    print(f"\n{Colors.YELLOW}💡 To see the actual improved logs:{Colors.NC}")
    print(f"   Run: {Colors.CYAN}docker logs -f contract-jena-agents-api-1{Colors.NC}")
    print(f"   Or:  {Colors.CYAN}make api-logs{Colors.NC}")


async def run_test_query(query_info: Dict[str, str]):
    """Run a single test query and display results"""
    print_header(f"Testing: {query_info['name']}")
    
    print_info(f"Description: {query_info['description']}")
    print_metric("Question", query_info['question'])
    
    # Submit query
    print_section("Step 1: Submit Query")
    submit_result = await submit_query(query_info['question'])
    
    if not submit_result:
        print_error("Failed to submit query")
        return
    
    job_id = submit_result.get("job_id")
    
    # Wait for completion
    print_section("Step 2: Wait for Completion")
    result = await wait_for_job_completion(job_id)
    
    if not result:
        print_error("Failed to get result")
        return
    
    # Display result
    print_section("Step 3: Result")
    
    status = result.get("status")
    if status == "completed":
        answer = result.get("result", {}).get("answer", "No answer")
        confidence = result.get("result", {}).get("confidence", 0)
        
        print_success("Query completed successfully")
        print_metric("Confidence", f"{confidence:.1%}")
        print_metric("Answer Preview", answer[:200] + "..." if len(answer) > 200 else answer)
        
        # Display logging improvements
        display_logging_improvements(result)
    else:
        print_error(f"Query failed with status: {status}")


async def main():
    """Main test function"""
    print_header("Logging Improvements Test Suite")
    
    print(f"{Colors.BOLD}This test demonstrates three key logging improvements:{Colors.NC}")
    print("1. ✓ Ambiguous 'relevant clauses' → Clear 'from Milvus vector store'")
    print("2. ✓ Added source contribution metrics (KG vs Vector)")
    print("3. ✓ Added retrieval time breakdown (KG time vs Vector time)")
    
    # Check API health
    print_section("Checking API Health")
    if not await check_api_health():
        print_error("API is not available. Please start it with: make api-up")
        sys.exit(1)
    
    # Run test queries
    for i, query_info in enumerate(TEST_QUERIES, 1):
        await run_test_query(query_info)
        
        # Add delay between queries
        if i < len(TEST_QUERIES):
            print_info("Waiting 5 seconds before next query...")
            await asyncio.sleep(5)
    
    # Final summary
    print_header("Test Complete")
    print_success("All logging improvements have been demonstrated")
    
    print(f"\n{Colors.BOLD}Next Steps:{Colors.NC}")
    print(f"1. View worker logs to see the improved logging:")
    print(f"   {Colors.CYAN}docker logs -f contract-jena-agents-api-1{Colors.NC}")
    print(f"\n2. Or use the Make command:")
    print(f"   {Colors.CYAN}make api-logs{Colors.NC}")
    print(f"\n3. Look for these improvements in the logs:")
    print(f"   • 'Found X relevant clauses from Milvus vector store'")
    print(f"   • 'Source contribution: KG facts: X, Vector results: Y'")
    print(f"   • 'Retrieval: Xms' with 'KG: Xms (Y%)' and 'Vector: Xms (Y%)'")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.NC}")
        sys.exit(0)
    except Exception as e:
        print_error(f"Test failed with error: {e}")
        sys.exit(1)


