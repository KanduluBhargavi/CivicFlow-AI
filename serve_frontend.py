#!/usr/bin/env python3
"""CivicFlow dev server for the frontend folder (replaces VS Code Live Server).
Threaded, so a stuck browser connection can never block other files.
Run from your project root:   python serve_frontend.py
Then open:                    http://127.0.0.1:5500/login.html
Options:  python serve_frontend.py [folder] [port]      (defaults: frontend  5500)"""
import sys, os, functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

folder = sys.argv[1] if len(sys.argv) > 1 else "frontend"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 5500
if not os.path.isdir(folder):
    sys.exit(f"Folder '{folder}' not found. Run this from the folder that contains it.")

class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".svg": "image/svg+xml", ".js": "text/javascript", ".css": "text/css"}
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")      # always show your latest edits
        super().end_headers()
    def log_message(self, *a): pass

ThreadingHTTPServer.daemon_threads = True
srv = ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Handler, directory=folder))
print(f"CivicFlow frontend running:  http://127.0.0.1:{port}/index.html   (Ctrl+C to stop)")
try: srv.serve_forever()
except KeyboardInterrupt: print("\nstopped")
