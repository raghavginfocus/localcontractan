#!/usr/bin/env python3
"""
Concurrent Async Queue Test with Monitoring

This script demonstrates the complete async queue processing system by:
1. Loading test cases from YAML file
2. Submitting all queries simultaneously to the async API
3. Monitoring RabbitMQ queue status
4. Monitoring Redis job tracking
5. Monitoring worker processing
6. Verifying Phoenix observability integration

Usage:
    python scripts/test_async_queue_concurrent.py
    
Or via Make:
    make test-async-concurrent
"""

import asyncio
import httpx
import yaml
import time
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8001"
RABBITMQ_MGMT_URL = "http://localhost:15672"
RABBITMQ_USER = "admin"
RABBITMQ_PASS = "admin123"
PHOENIX_URL = "http://localhost:6006"
TEST_CASES_FILE = "tests/test_cases/test_cases_simple.yaml"

# ANSI Colors
class C:
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[0;33m'
    RED = '\033[0;31m'
    CYAN = '\033[0;36m'
    MAGENTA = '\033[0;35m'
    BOLD = '\033[1m'
    NC = '\033[0m'


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{C.BLUE}{C.BOLD}{'=' * 80}{C.NC}")
    print(f"{C.BLUE}{C.BOLD}{text:^80}{C.NC}")
    print(f"{C.BLUE}{C.BOLD}{'=' * 80}{C.NC}\n")


def print_section(text: str):
    """Print formatted section"""
    print(f"\n{C.CYAN}{C.BOLD}{text}{C.NC}")
    print(f"{C.CYAN}{'-' * len(text)}{C.NC}")


def print_success(text: str):
    print(f"{C.GREEN}✓ {text}{C.NC}")


def print_error(text: str):
    print(f"{C.RED}✗ {text}{C.NC}")


def print_info(text: str):
    print(f"{C.YELLOW}ℹ {text}{C.NC}")


def print_metric(label: str, value: Any, indent: int = 2):
    spaces = " " * indent
    print(f"{spaces}{C.MAGENTA}{label}:{C.NC} {value}")


def load_test_cases() -> List[Dict[str, Any]]:
    """Load test cases from YAML file"""
    yaml_path = Path(TEST_CASES_FILE)
    
    if not yaml_path.exists():
        print_error(f"Test cases file not found: {TEST_CASES_FILE}")
        return []
    
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    
    test_cases = data.get('test_cases', [])
    print_success(f"Loaded {len(test_cases)} test cases from YAML")
    
    return test_cases


async def check_services() -> bool:
    """Check if all required services are running"""
    print_section("Checking Services")
    
    all_ok = True
    
    # Check API
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{API_BASE_URL}/health")
            if resp.status_code == 200:
                print_success("API is healthy")
            else:
                print_error(f"API unhealthy: {resp.status_code}")
                all_ok = False
    except Exception as e:
        print_error(f"API not accessible: {e}")
        all_ok = False
    
    # Check RabbitMQ Management API
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{RABBITMQ_MGMT_URL}/api/overview",
                auth=(RABBITMQ_USER, RABBITMQ_PASS)
            )
            if resp.status_code == 200:
                print_success("RabbitMQ Management API accessible")
            else:
                print_error(f"RabbitMQ unhealthy: {resp.status_code}")
                all_ok = False
    except Exception as e:
        print_error(f"RabbitMQ not accessible: {e}")
        all_ok = False
    
    # Check Phoenix
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(PHOENIX_URL)
            if resp.status_code == 200:
                print_success("Phoenix observability accessible")
            else:
                print_info("Phoenix may not be running (optional)")
    except Exception as e:
        print_info(f"Phoenix not accessible (optional): {e}")
    
    return all_ok


async def get_queue_stats() -> Dict[str, Any]:
    """Get RabbitMQ queue statistics"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{RABBITMQ_MGMT_URL}/api/queues/%2F/contract_queries",
                auth=(RABBITMQ_USER, RABBITMQ_PASS)
            )
            if resp.status_code == 200:
                return resp.json()
            return {}
    except Exception:
        return {}


async def get_api_queue_stats() -> Dict[str, Any]:
    """Get queue stats from API endpoint"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{API_BASE_URL}/api/v1/queue/stats")
            if resp.status_code == 200:
                return resp.json()
            return {}
    except Exception:
        return {}


async def submit_query(
    test_case: Dict[str, Any],
    priority: int = 5
) -> Dict[str, Any]:
    """Submit a single query to the async API"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/v1/query/async",
                json={
                    "query": test_case['question'],
                    "priority": priority
                }
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "job_id": data.get("job_id"),
                    "test_case_id": test_case['id'],
                    "question": test_case['question']
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}",
                    "test_case_id": test_case['id']
                }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "test_case_id": test_case['id']
        }


async def submit_all_queries(
    test_cases: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Submit all queries concurrently"""
    print_section("Submitting All Queries Concurrently")
    
    # Create tasks for all submissions
    tasks = [
        submit_query(tc, priority=5)
        for tc in test_cases
    ]
    
    # Execute all submissions concurrently
    start_time = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time
    
    # Count successes
    successful = sum(1 for r in results if r.get("success"))
    
    print_success(
        f"Submitted {successful}/{len(test_cases)} queries "
        f"in {elapsed:.2f}s"
    )
    
    return results


async def monitor_queue_and_jobs(
    job_ids: List[str],
    duration: int = 60
):
    """Monitor queue status and job progress"""
    print_section("Monitoring Queue and Job Processing")
    
    start_time = time.time()
    last_queue_size = None
    completed_jobs = set()
    
    print_info(f"Monitoring for {duration} seconds...")
    print_info("Press Ctrl+C to stop monitoring early\n")
    
    while time.time() - start_time < duration:
        try:
            # Get queue stats
            queue_stats = await get_queue_stats()
            api_stats = await get_api_queue_stats()
            
            # Display queue info
            messages_ready = queue_stats.get('messages_ready', 0)
            messages_unacked = queue_stats.get('messages_unacknowledged', 0)
            
            if messages_ready != last_queue_size:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"\n[{timestamp}] Queue Status:")
                print_metric("Messages in queue", messages_ready)
                print_metric("Messages processing", messages_unacked)
                
                if api_stats:
                    print_metric(
                        "Jobs pending",
                        api_stats.get('jobs_pending', 0)
                    )
                    print_metric(
                        "Jobs processing",
                        api_stats.get('jobs_processing', 0)
                    )
                    print_metric(
                        "Jobs completed",
                        api_stats.get('jobs_completed', 0)
                    )
                
                last_queue_size = messages_ready
            
            # Check job statuses
            for job_id in job_ids:
                if job_id in completed_jobs:
                    continue
                
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(
                            f"{API_BASE_URL}/api/v1/jobs/{job_id}/status"
                        )
                        if resp.status_code == 200:
                            job_data = resp.json()
                            status = job_data.get('status')
                            
                            if status in ['completed', 'failed']:
                                completed_jobs.add(job_id)
                                timestamp = datetime.now().strftime(
                                    "%H:%M:%S"
                                )
                                if status == 'completed':
                                    print(
                                        f"[{timestamp}] {C.GREEN}✓{C.NC} "
                                        f"Job {job_id[:8]}... completed"
                                    )
                                else:
                                    print(
                                        f"[{timestamp}] {C.RED}✗{C.NC} "
                                        f"Job {job_id[:8]}... failed"
                                    )
                except Exception:
                    pass
            
            # Check if all jobs completed
            if len(completed_jobs) == len(job_ids):
                print_success(
                    f"\nAll {len(job_ids)} jobs completed!"
                )
                break
            
            await asyncio.sleep(2)
            
        except KeyboardInterrupt:
            print_info("\nMonitoring stopped by user")
            break
    
    return completed_jobs


async def display_final_results(job_results: List[Dict[str, Any]]):
    """Display final results summary"""
    print_section("Final Results Summary")
    
    successful_submissions = [r for r in job_results if r.get("success")]
    failed_submissions = [r for r in job_results if not r.get("success")]
    
    print_metric("Total queries", len(job_results), indent=0)
    print_metric(
        "Successfully submitted",
        len(successful_submissions),
        indent=0
    )
    print_metric("Failed submissions", len(failed_submissions), indent=0)
    
    if failed_submissions:
        print("\nFailed Submissions:")
        for fail in failed_submissions:
            print_error(
                f"  {fail['test_case_id']}: {fail.get('error', 'Unknown')}"
            )
    
    # Get final stats
    api_stats = await get_api_queue_stats()
    if api_stats:
        print("\nFinal Queue Statistics:")
        print_metric("Jobs completed", api_stats.get('jobs_completed', 0))
        print_metric("Jobs failed", api_stats.get('jobs_failed', 0))
        print_metric("Jobs pending", api_stats.get('jobs_pending', 0))


async def main():
    """Main test function"""
    print_header("Async Queue Concurrent Processing Test")
    
    print(f"{C.BOLD}This test demonstrates:{C.NC}")
    print("1. Loading test cases from YAML")
    print("2. Submitting all queries simultaneously")
    print("3. Monitoring RabbitMQ queue")
    print("4. Monitoring Redis job tracking")
    print("5. Monitoring worker processing")
    print("6. Phoenix observability integration")
    
    # Check services
    if not await check_services():
        print_error("\nSome services are not available")
        print_info("Start services with: make services-up && make api-up")
        sys.exit(1)
    
    # Load test cases
    print_section("Loading Test Cases")
    test_cases = load_test_cases()
    
    if not test_cases:
        print_error("No test cases loaded")
        sys.exit(1)
    
    print(f"\nTest Cases to Execute:")
    for i, tc in enumerate(test_cases, 1):
        print(f"  {i}. {tc['id']}: {tc['question'][:60]}...")
    
    # Submit all queries concurrently
    job_results = await submit_all_queries(test_cases)
    
    # Extract job IDs
    job_ids = [
        r['job_id'] for r in job_results
        if r.get('success') and r.get('job_id')
    ]
    
    if not job_ids:
        print_error("No jobs were successfully submitted")
        sys.exit(1)
    
    print(f"\n{C.BOLD}Submitted Job IDs:{C.NC}")
    for job_id in job_ids:
        print(f"  • {job_id}")
    
    # Monitor processing
    await monitor_queue_and_jobs(job_ids, duration=300)
    
    # Display final results
    await display_final_results(job_results)
    
    # Final instructions
    print_header("Monitoring Instructions")
    
    print(f"{C.BOLD}View Worker Logs:{C.NC}")
    print(f"  {C.CYAN}make api-logs{C.NC}")
    print(f"  {C.CYAN}docker logs -f contract-jena-agents-api-1{C.NC}")
    
    print(f"\n{C.BOLD}View RabbitMQ Management UI:{C.NC}")
    print(f"  {C.CYAN}http://localhost:15672{C.NC}")
    print("  Username: admin, Password: admin123")
    
    print(f"\n{C.BOLD}View Phoenix Observability:{C.NC}")
    print(f"  {C.CYAN}http://localhost:6006{C.NC}")
    print(f"  All traces should be visible with full context")
    
    print(f"\n{C.BOLD}Check Redis Job Data:{C.NC}")
    print(f"  {C.CYAN}docker exec -it contract-jena-redis-1 "
          f"redis-cli{C.NC}")
    print(f"  Then run: {C.CYAN}SELECT 2{C.NC} (job tracking DB)")
    print(f"  Then run: {C.CYAN}KEYS job:*{C.NC}")
    
    print(f"\n{C.BOLD}Logging Improvements Visible in Worker Logs:{C.NC}")
    print("  • 'Found X relevant clauses from Milvus vector store'")
    print("  • 'Source contribution: KG facts: X, Vector results: Y'")
    print("  • 'KG: Xms (Y%)' and 'Vector: Xms (Y%)'")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Test interrupted by user{C.NC}")
        sys.exit(0)
    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


