#!/usr/bin/env python3
"""
Log viewer for Contract KG RAG system.

View, analyze, and compare RAG session logs for debugging and evaluation.

Usage:
    uv run python scripts/view_logs.py                    # List recent sessions
    uv run python scripts/view_logs.py --session <id>     # View specific session
    uv run python scripts/view_logs.py --last             # View last session
    uv run python scripts/view_logs.py --compare <id1> <id2>  # Compare two sessions
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def load_session(log_dir: Path, session_id: str) -> dict | None:
    """Load a session log by ID."""
    log_file = log_dir / "sessions" / f"{session_id}.json"
    if log_file.exists():
        with open(log_file) as f:
            return json.load(f)
    return None


def list_sessions(log_dir: Path, limit: int = 20):
    """List recent sessions."""
    sessions_dir = log_dir / "sessions"
    if not sessions_dir.exists():
        print("❌ No sessions found. Run some queries first!")
        return
    
    files = sorted(sessions_dir.glob("*.json"), reverse=True)[:limit]
    
    if not files:
        print("❌ No sessions found.")
        return
    
    print("\n" + "="*70)
    print("  📋 RECENT RAG SESSIONS")
    print("="*70)
    
    for f in files:
        try:
            with open(f) as fp:
                data = json.load(fp)
            
            session_id = data.get("session_id", f.stem)
            question = data.get("question", "")[:50]
            status = data.get("status", "unknown")
            confidence = data.get("final_confidence", 0)
            duration = data.get("total_duration_ms", 0)
            step_count = len(data.get("steps", []))
            
            status_emoji = "✅" if status == "completed" else "❌" if status == "failed" else "⏳"
            
            print(f"\n  {status_emoji} Session: {session_id}")
            print(f"     Question: {question}...")
            print(f"     Confidence: {confidence:.0%} | Steps: {step_count} | Duration: {duration:.0f}ms")
            
        except Exception as e:
            print(f"  ⚠️  Error reading {f.name}: {e}")
    
    print("\n" + "="*70)
    print(f"  Total: {len(files)} sessions")
    print("  Use --session <id> to view details")
    print("="*70 + "\n")


def view_session(log_dir: Path, session_id: str):
    """View detailed session information."""
    data = load_session(log_dir, session_id)
    
    if not data:
        print(f"❌ Session '{session_id}' not found")
        return
    
    print("\n" + "="*70)
    print("  📋 SESSION DETAILS")
    print("="*70)
    
    print(f"\n  Session ID: {data.get('session_id')}")
    print(f"  Started: {data.get('started_at')}")
    print(f"  Status: {data.get('status')}")
    print(f"  Total Duration: {data.get('total_duration_ms', 0):.0f}ms")
    
    print(f"\n  ❓ QUESTION:")
    print(f"  {'-'*66}")
    print(f"  {data.get('question')}")
    
    # Show steps
    steps = data.get("steps", [])
    if steps:
        print(f"\n  📊 PROCESSING STEPS ({len(steps)}):")
        print(f"  {'-'*66}")
        
        for i, step in enumerate(steps, 1):
            status_emoji = "✅" if step.get("status") == "success" else "❌"
            print(f"\n  {status_emoji} Step {i}: {step.get('step_name')}")
            print(f"     Timestamp: {step.get('timestamp')}")
            print(f"     Duration: {step.get('duration_ms', 0):.0f}ms")
            print(f"     Status: {step.get('status')}")
            
            # Show input preview
            input_data = step.get("input_data")
            if input_data:
                print(f"     INPUT:")
                if isinstance(input_data, dict):
                    for k, v in list(input_data.items())[:3]:
                        v_str = str(v)[:80] if v else "None"
                        print(f"       • {k}: {v_str}")
                else:
                    print(f"       {str(input_data)[:100]}")
            
            # Show output preview
            output_data = step.get("output_data")
            if output_data:
                print(f"     OUTPUT:")
                if isinstance(output_data, dict):
                    for k, v in list(output_data.items())[:3]:
                        v_str = str(v)[:80] if v else "None"
                        print(f"       • {k}: {v_str}")
                else:
                    print(f"       {str(output_data)[:100]}")
            
            if step.get("error_message"):
                print(f"     ERROR: {step.get('error_message')}")
    
    # Show final answer
    print(f"\n  💬 FINAL ANSWER:")
    print(f"  {'-'*66}")
    answer = data.get("final_answer", "No answer")
    # Wrap long lines
    for i in range(0, len(answer), 65):
        print(f"  {answer[i:i+65]}")
    
    print(f"\n  📊 METRICS:")
    print(f"  {'-'*66}")
    print(f"  Confidence: {data.get('final_confidence', 0):.0%}")
    
    print("\n" + "="*70 + "\n")


def view_last_session(log_dir: Path):
    """View the most recent session."""
    sessions_dir = log_dir / "sessions"
    if not sessions_dir.exists():
        print("❌ No sessions found")
        return
    
    files = sorted(sessions_dir.glob("*.json"), reverse=True)
    if not files:
        print("❌ No sessions found")
        return
    
    session_id = files[0].stem
    view_session(log_dir, session_id)


def compare_sessions(log_dir: Path, session_id1: str, session_id2: str):
    """Compare two sessions."""
    data1 = load_session(log_dir, session_id1)
    data2 = load_session(log_dir, session_id2)
    
    if not data1:
        print(f"❌ Session '{session_id1}' not found")
        return
    if not data2:
        print(f"❌ Session '{session_id2}' not found")
        return
    
    print("\n" + "="*70)
    print("  📊 SESSION COMPARISON")
    print("="*70)
    
    # Side by side comparison
    print(f"\n  {'Metric':<25} {'Session 1':<20} {'Session 2':<20}")
    print(f"  {'-'*65}")
    
    metrics = [
        ("Session ID", "session_id", "session_id"),
        ("Question (preview)", lambda d: d.get("question", "")[:25] + "...", lambda d: d.get("question", "")[:25] + "..."),
        ("Status", "status", "status"),
        ("Confidence", lambda d: f"{d.get('final_confidence', 0):.0%}", lambda d: f"{d.get('final_confidence', 0):.0%}"),
        ("Duration (ms)", lambda d: f"{d.get('total_duration_ms', 0):.0f}", lambda d: f"{d.get('total_duration_ms', 0):.0f}"),
        ("Steps", lambda d: len(d.get("steps", [])), lambda d: len(d.get("steps", []))),
        ("Answer length", lambda d: len(d.get("final_answer", "")), lambda d: len(d.get("final_answer", ""))),
    ]
    
    for name, getter1, getter2 in metrics:
        if callable(getter1):
            val1 = getter1(data1)
            val2 = getter2(data2)
        else:
            val1 = data1.get(getter1, "N/A")
            val2 = data2.get(getter2, "N/A")
        
        print(f"  {name:<25} {str(val1):<20} {str(val2):<20}")
    
    print("\n" + "="*70 + "\n")


def export_session(log_dir: Path, session_id: str, output_file: str):
    """Export session as formatted text."""
    data = load_session(log_dir, session_id)
    
    if not data:
        print(f"❌ Session '{session_id}' not found")
        return
    
    output_path = Path(output_file)
    
    with open(output_path, "w") as f:
        f.write("="*70 + "\n")
        f.write("CONTRACT KG RAG - SESSION LOG\n")
        f.write("="*70 + "\n\n")
        
        f.write(f"Session ID: {data.get('session_id')}\n")
        f.write(f"Timestamp: {data.get('started_at')}\n")
        f.write(f"Status: {data.get('status')}\n\n")
        
        f.write("QUESTION:\n")
        f.write("-"*70 + "\n")
        f.write(data.get("question", "") + "\n\n")
        
        f.write("PROCESSING STEPS:\n")
        f.write("-"*70 + "\n")
        for i, step in enumerate(data.get("steps", []), 1):
            f.write(f"\nStep {i}: {step.get('step_name')}\n")
            f.write(f"  Status: {step.get('status')}\n")
            f.write(f"  Duration: {step.get('duration_ms', 0):.0f}ms\n")
            f.write(f"  Input: {json.dumps(step.get('input_data'), indent=4)[:500]}\n")
            f.write(f"  Output: {json.dumps(step.get('output_data'), indent=4)[:500]}\n")
        
        f.write("\n\nFINAL ANSWER:\n")
        f.write("-"*70 + "\n")
        f.write(data.get("final_answer", "") + "\n\n")
        
        f.write(f"Confidence: {data.get('final_confidence', 0):.0%}\n")
        f.write(f"Total Duration: {data.get('total_duration_ms', 0):.0f}ms\n")
    
    print(f"✅ Session exported to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="View RAG session logs")
    parser.add_argument("--session", "-s", type=str, help="View specific session by ID")
    parser.add_argument("--last", "-l", action="store_true", help="View last session")
    parser.add_argument("--compare", "-c", nargs=2, metavar=("ID1", "ID2"), help="Compare two sessions")
    parser.add_argument("--export", "-e", type=str, help="Export session to text file")
    parser.add_argument("--limit", type=int, default=20, help="Number of sessions to list")
    parser.add_argument("--log-dir", type=str, default="logs", help="Log directory path")
    args = parser.parse_args()
    
    log_dir = Path(args.log_dir)
    
    if args.last:
        view_last_session(log_dir)
    elif args.session:
        if args.export:
            export_session(log_dir, args.session, args.export)
        else:
            view_session(log_dir, args.session)
    elif args.compare:
        compare_sessions(log_dir, args.compare[0], args.compare[1])
    else:
        list_sessions(log_dir, args.limit)


if __name__ == "__main__":
    main()
