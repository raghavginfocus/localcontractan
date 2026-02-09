#!/usr/bin/env python3
"""
Fix malformed SHACL files by removing line breaks from URIs.
"""
import re
from pathlib import Path


def fix_uri_linebreaks(text: str) -> str:
    """Remove line breaks from URIs in angle brackets."""
    def fix_match(match):
        uri = match.group(0)
        # Remove all newlines and extra spaces within URIs
        uri = uri.replace('\n', '').replace('\r', '')
        uri = re.sub(r'\s+', '', uri)
        return uri
    
    # Fix URIs in angle brackets that span multiple lines
    text = re.sub(r'<[^>]*\n[^>]*>', fix_match, text, flags=re.MULTILINE)
    return text


def fix_shacl_file(file_path: Path) -> bool:
    """Fix a single SHACL file."""
    try:
        # Read original content
        with open(file_path, 'r', encoding='utf-8') as f:
            original = f.read()
        
        # Fix line breaks in URIs
        fixed = fix_uri_linebreaks(original)
        
        # Only write if changes were made
        if fixed != original:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed)
            return True
        return False
    except Exception as e:
        print(f"  ✗ Error fixing {file_path.name}: {e}")
        return False


def main():
    """Fix all SHACL files in the generated directory."""
    shacl_dir = Path("agents/data/generated/shacl")
    
    if not shacl_dir.exists():
        print(f"⚠️  SHACL directory not found: {shacl_dir}")
        return
    
    shacl_files = list(shacl_dir.glob("*.ttl"))
    print(f"\n🔧 Fixing {len(shacl_files)} SHACL files...")
    
    fixed_count = 0
    for shacl_file in shacl_files:
        if fix_shacl_file(shacl_file):
            fixed_count += 1
            print(f"  ✓ Fixed: {shacl_file.name}")
    
    print(f"\n✅ Fixed {fixed_count}/{len(shacl_files)} SHACL files")
    
    if fixed_count > 0:
        print("\n💡 Now run: python scripts/setup/load_shacl_and_rules.py")


if __name__ == "__main__":
    main()


