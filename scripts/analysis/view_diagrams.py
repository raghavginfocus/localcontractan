#!/usr/bin/env python3
"""
Simple HTML viewer for exported diagrams.

Opens a web browser to view all exported diagrams in an organized way.

Usage:
    python scripts/view_diagrams.py
    python scripts/view_diagrams.py --port 8080
"""

import argparse
import http.server
import socketserver
import webbrowser
from pathlib import Path
from urllib.parse import urlparse, unquote


class DiagramHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler to serve diagrams with better HTML."""
    
    def end_headers(self):
        # Add CORS headers for local development
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = unquote(parsed_path.path)
        
        # Serve index.html for root
        if path == '/' or path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            # Generate HTML
            html = self.generate_index_html()
            self.wfile.write(html.encode('utf-8'))
            return
        
        # Serve files normally
        return super().do_GET()
    
    def generate_index_html(self):
        """Generate HTML index page for diagrams."""
        diagrams_dir = Path(self.server.diagrams_dir)
        
        # Find all image files
        png_files = sorted(diagrams_dir.glob('*.png'))
        svg_files = sorted(diagrams_dir.glob('*.svg'))
        all_files = png_files + svg_files
        
        if not all_files:
            return """
<!DOCTYPE html>
<html>
<head>
    <title>No Diagrams Found</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; text-align: center; }
        .error { color: #d32f2f; }
    </style>
</head>
<body>
    <h1 class="error">No Diagrams Found</h1>
    <p>Run the export script first:</p>
    <code>python scripts/export_diagrams.py</code>
</body>
</html>
"""
        
        # Group by source file
        by_source = {}
        for img_file in all_files:
            # Extract source from filename (e.g., "overall_architecture_*" -> "overall_architecture")
            parts = img_file.stem.split('_')
            if len(parts) >= 2:
                source = '_'.join(parts[:2])  # e.g., "overall_architecture"
            else:
                source = "other"
            
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(img_file)
        
        html = """<!DOCTYPE html>
<html>
<head>
    <title>Architecture Diagrams Viewer</title>
    <meta charset="utf-8">
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }
        .section {
            margin: 40px 0;
        }
        .section h2 {
            color: #555;
            margin-top: 30px;
            padding: 10px;
            background: #f0f0f0;
            border-left: 4px solid #4CAF50;
        }
        .diagram-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .diagram {
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 15px;
            background: #fafafa;
            transition: box-shadow 0.3s;
        }
        .diagram:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .diagram h3 {
            margin: 0 0 10px 0;
            color: #333;
            font-size: 16px;
        }
        .diagram img {
            max-width: 100%;
            height: auto;
            border: 1px solid #eee;
            border-radius: 4px;
            background: white;
        }
        .diagram svg {
            max-width: 100%;
            height: auto;
            border: 1px solid #eee;
            border-radius: 4px;
            background: white;
        }
        .info {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
            border-left: 4px solid #2196F3;
        }
        .info code {
            background: #fff;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 14px;
        }
        .stats {
            color: #666;
            font-size: 14px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Architecture Diagrams</h1>
        
        <div class="info">
            <strong>💡 Tip:</strong> Right-click any diagram and select "Save Image As" to download.
            <br>
            <strong>📁 Location:</strong> <code>""" + str(diagrams_dir) + """</code>
        </div>
"""
        
        # Add sections for each source
        for source, files in sorted(by_source.items()):
            source_name = source.replace('_', ' ').title()
            html += f"""
        <div class="section">
            <h2>{source_name} ({len(files)} diagram{'s' if len(files) != 1 else ''})</h2>
            <div class="diagram-grid">
"""
            for img_file in files:
                img_name = img_file.stem.replace('_', ' ').title()
                img_url = img_file.name
                html += f"""
                <div class="diagram">
                    <h3>{img_name}</h3>
                    <img src="{img_url}" alt="{img_name}" loading="lazy">
                    <div class="stats">File: {img_file.name}</div>
                </div>
"""
            html += """
            </div>
        </div>
"""
        
        html += """
    </div>
</body>
</html>
"""
        return html


def main():
    parser = argparse.ArgumentParser(
        description="View exported diagrams in web browser"
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port number (default: 8000)'
    )
    parser.add_argument(
        '--dir',
        type=Path,
        default=Path('docs/02_architecture/diagrams'),
        help='Diagrams directory (default: docs/02_architecture/diagrams)'
    )
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Do not open browser automatically'
    )
    
    args = parser.parse_args()
    
    if not args.dir.exists():
        print(f"❌ Diagrams directory not found: {args.dir}")
        print(f"   Run: python scripts/export_diagrams.py")
        return
    
    # Change to diagrams directory
    import os
    os.chdir(args.dir)
    
    # Create server
    handler = DiagramHandler
    handler.server.diagrams_dir = args.dir
    
    try:
        with socketserver.TCPServer(("", args.port), handler) as httpd:
            url = f"http://localhost:{args.port}"
            print(f"🌐 Starting diagram viewer...")
            print(f"📂 Serving from: {args.dir}")
            print(f"🔗 URL: {url}")
            print()
            print("Press Ctrl+C to stop")
            print()
            
            if not args.no_browser:
                webbrowser.open(url)
            
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {args.port} is already in use")
            print(f"   Try: python scripts/view_diagrams.py --port {args.port + 1}")
        else:
            raise


if __name__ == '__main__':
    main()
