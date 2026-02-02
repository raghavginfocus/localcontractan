#!/usr/bin/env python3
"""
Monitor ingestion processes - Shows threads, processes, and resource usage.

Usage:
    python scripts/monitor_ingestion.py
    python scripts/monitor_ingestion.py --watch  # Continuous monitoring
"""

import sys
import time
import threading
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

import psutil
import os


def get_current_process_info():
    """Get information about the current Python process."""
    process = psutil.Process(os.getpid())
    
    return {
        "pid": process.pid,
        "name": process.name(),
        "status": process.status(),
        "threads": process.num_threads(),
        "cpu_percent": process.cpu_percent(interval=0.1),
        "memory_mb": process.memory_info().rss / 1024 / 1024,
        "memory_percent": process.memory_percent(),
        "open_files": len(process.open_files()),
        "connections": len(process.connections()),
    }


def get_thread_info():
    """Get information about all threads in the current process."""
    threads = threading.enumerate()
    
    thread_details = []
    for thread in threads:
        thread_details.append({
            "name": thread.name,
            "daemon": thread.daemon,
            "alive": thread.is_alive(),
            "ident": thread.ident,
        })
    
    return {
        "total": len(threads),
        "active": sum(1 for t in threads if t.is_alive()),
        "daemon": sum(1 for t in threads if t.daemon),
        "details": thread_details,
    }


def get_async_tasks_info():
    """Try to get information about asyncio tasks (if in async context)."""
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
            return {
                "total_tasks": len(tasks),
                "pending": sum(1 for t in tasks if not t.done()),
                "task_names": [t.get_name() for t in tasks[:10]],  # First 10
            }
    except (RuntimeError, AttributeError):
        pass
    
    return None


def get_python_processes():
    """Get all Python processes related to ingestion."""
    python_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info']):
        try:
            if 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'ingestion' in cmdline.lower() or 'run_ingestion' in cmdline.lower():
                    python_processes.append({
                        "pid": proc.info['pid'],
                        "name": proc.info['name'],
                        "cmdline": cmdline[:100],  # Truncate
                        "cpu_percent": proc.cpu_percent(interval=0.1),
                        "memory_mb": proc.info['memory_info'].rss / 1024 / 1024,
                        "threads": proc.num_threads(),
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return python_processes


def print_monitoring_info():
    """Print current monitoring information."""
    print("\n" + "="*70)
    print("📊 Ingestion Process Monitoring")
    print("="*70)
    
    # Current process info
    proc_info = get_current_process_info()
    print(f"\n🖥️  Current Process:")
    print(f"   PID: {proc_info['pid']}")
    print(f"   Name: {proc_info['name']}")
    print(f"   Status: {proc_info['status']}")
    print(f"   CPU: {proc_info['cpu_percent']:.1f}%")
    print(f"   Memory: {proc_info['memory_mb']:.1f} MB ({proc_info['memory_percent']:.1f}%)")
    print(f"   Open Files: {proc_info['open_files']}")
    print(f"   Connections: {proc_info['connections']}")
    
    # Thread info
    thread_info = get_thread_info()
    print(f"\n🧵 Threads:")
    print(f"   Total: {thread_info['total']}")
    print(f"   Active: {thread_info['active']}")
    print(f"   Daemon: {thread_info['daemon']}")
    
    if thread_info['details']:
        print(f"\n   Thread Details:")
        for thread in thread_info['details'][:10]:  # Show first 10
            status = "✓" if thread['alive'] else "✗"
            daemon = "D" if thread['daemon'] else " "
            print(f"     {status} [{daemon}] {thread['name']} (ID: {thread['ident']})")
        if len(thread_info['details']) > 10:
            print(f"     ... and {len(thread_info['details']) - 10} more threads")
    
    # Async tasks info
    async_info = get_async_tasks_info()
    if async_info:
        print(f"\n⚡ Async Tasks:")
        print(f"   Total: {async_info['total_tasks']}")
        print(f"   Pending: {async_info['pending']}")
        if async_info['task_names']:
            print(f"   Task Names:")
            for name in async_info['task_names'][:10]:
                print(f"     • {name}")
    
    # Related Python processes
    python_procs = get_python_processes()
    if python_procs:
        print(f"\n🐍 Related Python Processes:")
        for proc in python_procs:
            print(f"   PID {proc['pid']}: {proc['name']}")
            print(f"     Threads: {proc['threads']}")
            print(f"     CPU: {proc['cpu_percent']:.1f}%")
            print(f"     Memory: {proc['memory_mb']:.1f} MB")
            print(f"     Cmd: {proc['cmdline'][:80]}")
    
    print("\n" + "="*70)


def main():
    """Main monitoring function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor ingestion processes")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuous monitoring (updates every 2 seconds)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Update interval in seconds (default: 2.0)"
    )
    args = parser.parse_args()
    
    try:
        if args.watch:
            print("🔄 Continuous monitoring mode (Ctrl+C to stop)")
            while True:
                # Clear screen (works on most terminals)
                print("\033[2J\033[H", end="")
                print_monitoring_info()
                print(f"\n⏱️  Next update in {args.interval}s... (Ctrl+C to stop)")
                time.sleep(args.interval)
        else:
            print_monitoring_info()
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped")


if __name__ == "__main__":
    main()
