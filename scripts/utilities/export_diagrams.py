#!/usr/bin/env python3
"""
Export Mermaid diagrams from architecture markdown files to images.

This script extracts all Mermaid diagrams from the architecture documentation
and exports them as PNG or SVG images for presentations.

Usage:
    python scripts/export_diagrams.py
    python scripts/export_diagrams.py --format svg
    python scripts/export_diagrams.py --output diagrams/
"""

import re
import argparse
import base64
import json
from pathlib import Path
from typing import List, Tuple
import urllib.request
import urllib.parse

try:
    from PIL import Image
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("⚠️  PIL not available. Install with: pip install Pillow")


def extract_mermaid_diagrams(markdown_file: Path) -> List[Tuple[str, str]]:
    """
    Extract Mermaid diagram code blocks from markdown file.
    
    Returns:
        List of tuples: (diagram_name, diagram_code)
    """
    content = markdown_file.read_text(encoding='utf-8')
    
    # Pattern to match mermaid code blocks
    pattern = r'```mermaid\n(.*?)```'
    
    diagrams = []
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for i, match in enumerate(matches, 1):
        diagram_code = match.group(1).strip()
        
        # Try to extract a meaningful name from the diagram
        # Look for graph title or first node
        name_match = re.search(r'(?:graph|flowchart|sequenceDiagram|classDiagram)\s+(\w+)', diagram_code)
        if name_match:
            diagram_name = name_match.group(1)
        else:
            # Use section heading before the diagram
            before_diagram = content[:match.start()]
            heading_match = re.search(r'^#+\s+(.+)$', before_diagram, re.MULTILINE)
            if heading_match:
                diagram_name = re.sub(r'[^\w\s-]', '', heading_match.group(1)).strip().replace(' ', '_')
            else:
                diagram_name = f"diagram_{i}"
        
        diagrams.append((diagram_name, diagram_code))
    
    return diagrams


def export_via_mermaid_ink(diagram_code: str, format: str = 'png', theme: str = 'default') -> bytes:
    """
    Export diagram using mermaid.ink API (online service).
    
    Args:
        diagram_code: Mermaid diagram code
        format: 'png' or 'svg'
        theme: 'default', 'dark', 'forest', 'neutral'
    
    Returns:
        Image bytes
    """
    # Encode diagram to base64
    diagram_bytes = diagram_code.encode('utf-8')
    diagram_b64 = base64.urlsafe_b64encode(diagram_bytes).decode('utf-8')
    
    # Build URL
    url = f"https://mermaid.ink/img/{diagram_b64}?theme={theme}&type={format}"
    
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read()
    except Exception as e:
        raise Exception(f"Failed to export via mermaid.ink: {e}")


def export_via_mermaid_cli(diagram_code: str, output_file: Path, format: str = 'png') -> None:
    """
    Export diagram using mermaid-cli (requires: npm install -g @mermaid-js/mermaid-cli).
    
    Args:
        diagram_code: Mermaid diagram code
        output_file: Output file path
        format: 'png' or 'svg'
    """
    import subprocess
    import tempfile
    
    # Write diagram to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as tmp:
        tmp.write(diagram_code)
        tmp_path = tmp.name
    
    try:
        # Run mmdc (mermaid-cli)
        cmd = ['mmdc', '-i', tmp_path, '-o', str(output_file), '-f', format]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"mmdc failed: {result.stderr}")
    finally:
        # Clean up temp file
        Path(tmp_path).unlink()


def export_diagrams_from_file(
    markdown_file: Path,
    output_dir: Path,
    format: str = 'png',
    method: str = 'mermaid.ink'
) -> List[Path]:
    """
    Export all diagrams from a markdown file.
    
    Returns:
        List of exported file paths
    """
    diagrams = extract_mermaid_diagrams(markdown_file)
    
    if not diagrams:
        print(f"  ⚠️  No diagrams found in {markdown_file.name}")
        return []
    
    exported_files = []
    file_stem = markdown_file.stem
    
    for i, (diagram_name, diagram_code) in enumerate(diagrams, 1):
        # Create output filename
        safe_name = re.sub(r'[^\w\s-]', '', diagram_name).strip().replace(' ', '_')
        output_file = output_dir / f"{file_stem}_{safe_name}_{i}.{format}"
        
        print(f"  📊 Exporting: {output_file.name}...", end=' ')
        
        try:
            if method == 'mermaid.ink':
                # Use online service
                image_data = export_via_mermaid_ink(diagram_code, format=format)
                output_file.write_bytes(image_data)
            elif method == 'mermaid-cli':
                # Use local CLI (if available)
                export_via_mermaid_cli(diagram_code, output_file, format=format)
            else:
                raise ValueError(f"Unknown method: {method}")
            
            print("✅")
            exported_files.append(output_file)
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    return exported_files


def convert_svg_to_png(svg_file: Path, output_file: Path = None) -> Path:
    """
    Convert SVG file to PNG using PIL or cairosvg.
    
    Args:
        svg_file: Input SVG file
        output_file: Output PNG file (auto-generated if None)
    
    Returns:
        Output PNG file path
    """
    if output_file is None:
        output_file = svg_file.with_suffix('.png')
    
    try:
        # Try using cairosvg (better quality)
        import cairosvg
        cairosvg.svg2png(url=str(svg_file), write_to=str(output_file))
        return output_file
    except ImportError:
        try:
            # Fallback to PIL (requires rsvg or similar)
            from PIL import Image
            import cairosvg
            
            # Read SVG and convert
            with open(svg_file, 'rb') as f:
                svg_data = f.read()
            
            png_data = cairosvg.svg2png(bytestring=svg_data)
            output_file.write_bytes(png_data)
            return output_file
        except Exception as e:
            # Last resort: use wand (ImageMagick)
            try:
                from wand.image import Image as WandImage
                with WandImage(filename=str(svg_file)) as img:
                    img.format = 'png'
                    img.save(filename=str(output_file))
                return output_file
            except ImportError:
                raise Exception(
                    f"Could not convert SVG. Install one of: cairosvg, wand (ImageMagick). "
                    f"Error: {e}"
                )


def convert_all_svgs_to_png(svg_dir: Path, output_dir: Path = None) -> List[Path]:
    """
    Convert all SVG files in directory to PNG.
    
    Returns:
        List of converted PNG file paths
    """
    if output_dir is None:
        output_dir = svg_dir
    
    svg_files = list(svg_dir.glob('*.svg'))
    converted = []
    
    print(f"🔄 Converting {len(svg_files)} SVG file(s) to PNG...")
    print()
    
    for svg_file in svg_files:
        png_file = output_dir / svg_file.with_suffix('.png').name
        print(f"  📊 Converting: {svg_file.name} → {png_file.name}...", end=' ')
        
        try:
            convert_svg_to_png(svg_file, png_file)
            print("✅")
            converted.append(png_file)
        except Exception as e:
            print(f"❌ Error: {e}")
            print(f"     💡 Install cairosvg: pip install cairosvg")
    
    return converted


def main():
    parser = argparse.ArgumentParser(
        description="Export Mermaid diagrams from architecture docs to images"
    )
    parser.add_argument(
        '--format',
        choices=['png', 'svg'],
        default='png',
        help='Output format (default: png - more compatible)'
    )
    parser.add_argument(
        '--convert-svgs',
        action='store_true',
        help='Convert existing SVG files to PNG'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('docs/02_architecture/diagrams'),
        help='Output directory (default: docs/02_architecture/diagrams)'
    )
    parser.add_argument(
        '--method',
        choices=['mermaid.ink', 'mermaid-cli'],
        default='mermaid.ink',
        help='Export method (default: mermaid.ink - online service)'
    )
    parser.add_argument(
        '--files',
        nargs='+',
        help='Specific markdown files to process (default: all architecture docs)'
    )
    
    args = parser.parse_args()
    
    # Handle SVG to PNG conversion
    if args.convert_svgs:
        svg_dir = args.output if args.output.exists() else Path('docs/02_architecture/diagrams')
        if not svg_dir.exists():
            print(f"❌ Directory not found: {svg_dir}")
            return
        
        converted = convert_all_svgs_to_png(svg_dir)
        print()
        print("=" * 60)
        print(f"✅ Converted {len(converted)} SVG file(s) to PNG")
        return
    
    # Find architecture markdown files
    arch_dir = Path('docs/02_architecture')
    
    if args.files:
        markdown_files = [Path(f) for f in args.files]
    else:
        markdown_files = list(arch_dir.glob('*_architecture.md'))
    
    if not markdown_files:
        print("❌ No architecture markdown files found!")
        return
    
    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Output directory: {args.output}")
    print(f"🎨 Format: {args.format}")
    print(f"🔧 Method: {args.method}")
    print()
    
    all_exported = []
    
    for md_file in markdown_files:
        if not md_file.exists():
            print(f"⚠️  File not found: {md_file}")
            continue
        
        print(f"📄 Processing: {md_file.name}")
        exported = export_diagrams_from_file(
            md_file,
            args.output,
            format=args.format,
            method=args.method
        )
        all_exported.extend(exported)
        print()
    
    print("=" * 60)
    print(f"✅ Exported {len(all_exported)} diagram(s) to {args.output}")
    print()
    print("📋 Exported files:")
    for f in all_exported:
        print(f"   • {f.name}")
    
    # Create index HTML for easy viewing
    if all_exported:
        index_file = args.output / 'index.html'
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Architecture Diagrams</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .diagram {{ margin: 20px 0; padding: 20px; border: 1px solid #ddd; }}
        .diagram img {{ max-width: 100%; height: auto; }}
        .diagram h2 {{ margin-top: 0; }}
    </style>
</head>
<body>
    <h1>Architecture Diagrams</h1>
    <p>Generated from architecture documentation</p>
"""
        for f in all_exported:
            html_content += f"""
    <div class="diagram">
        <h2>{f.stem}</h2>
        <img src="{f.name}" alt="{f.stem}">
    </div>
"""
        html_content += """
</body>
</html>
"""
        index_file.write_text(html_content)
        print(f"\n🌐 View all diagrams: {index_file}")


if __name__ == '__main__':
    main()
