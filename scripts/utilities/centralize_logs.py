#!/usr/bin/env python3
"""
Script to centralize all logs and clean up old log directories.

This script:
1. Creates centralized logs/ directory structure
2. Moves any existing logs from old locations
3. Deletes old log directories
"""

import shutil
from pathlib import Path

# Central logs directory
LOGS_ROOT = Path("logs")

# Old log directories to clean up
OLD_LOG_DIRS = [
    Path("agents/logs"),
    Path("agents/data/logs"),
    Path("agents/data/generated/logs"),
]

# Subdirectories to create
SUB_DIRS = [
    "ingestion",
    "retrieval",
    "shacl",
    "evaluation",
    "benchmark",
    "sparql",
    "sessions",
    "ontology",
    "rules",
]


def create_log_structure():
    """Create centralized log directory structure."""
    print("Creating centralized log directory structure...")
    
    # Create root logs directory
    LOGS_ROOT.mkdir(exist_ok=True)
    print(f"  ✓ Created {LOGS_ROOT}")
    
    # Create subdirectories
    for sub_dir in SUB_DIRS:
        log_dir = LOGS_ROOT / sub_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Created {log_dir}")


def move_existing_logs():
    """Move logs from old locations to centralized location."""
    print("\nMoving existing logs...")
    
    moved_count = 0
    
    for old_dir in OLD_LOG_DIRS:
        if not old_dir.exists():
            continue
        
        print(f"\n  Processing {old_dir}...")
        
        # Determine target directory based on old location
        if "ingestion" in str(old_dir) or "generated" in str(old_dir):
            target = LOGS_ROOT / "ingestion"
        elif "retrieval" in str(old_dir) or "rag" in str(old_dir):
            target = LOGS_ROOT / "retrieval"
        else:
            target = LOGS_ROOT / "ingestion"  # Default
        
        # Move files
        for file_path in old_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(old_dir)
                target_file = target / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Avoid overwriting existing files
                if target_file.exists():
                    # Add timestamp to filename
                    stem = target_file.stem
                    suffix = target_file.suffix
                    counter = 1
                    while target_file.exists():
                        target_file = target_file.parent / f"{stem}_{counter}{suffix}"
                        counter += 1
                
                shutil.move(str(file_path), str(target_file))
                moved_count += 1
                print(f"    Moved {file_path.name} → {target_file}")
        
        print(f"  ✓ Moved {moved_count} files from {old_dir}")
    
    if moved_count == 0:
        print("  No logs found to move")


def cleanup_old_dirs():
    """Delete old log directories."""
    print("\nCleaning up old log directories...")
    
    for old_dir in OLD_LOG_DIRS:
        if old_dir.exists():
            try:
                # Only delete if empty or only contains empty subdirectories
                if old_dir.is_dir():
                    # Check if directory is effectively empty
                    has_files = any(old_dir.rglob("*"))
                    if not has_files:
                        old_dir.rmdir()
                        print(f"  ✓ Removed empty directory: {old_dir}")
                    else:
                        # Try to remove if it only has empty subdirs
                        try:
                            shutil.rmtree(old_dir)
                            print(f"  ✓ Removed directory: {old_dir}")
                        except Exception as e:
                            print(f"  ⚠ Could not remove {old_dir}: {e}")
            except Exception as e:
                print(f"  ⚠ Could not remove {old_dir}: {e}")


def main():
    """Main execution."""
    print("=" * 60)
    print("Centralizing Logs")
    print("=" * 60)
    
    create_log_structure()
    move_existing_logs()
    cleanup_old_dirs()
    
    print("\n" + "=" * 60)
    print("✓ Log centralization complete!")
    print("=" * 60)
    print(f"\nCentralized logs location: {LOGS_ROOT.absolute()}")
    print("\nSubdirectories:")
    for sub_dir in SUB_DIRS:
        print(f"  - logs/{sub_dir}/")


if __name__ == "__main__":
    main()
