"""Simple threaded HTTP server for v2 local QA.

Usage:  python serve.py [port]
"""
import os, sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

port = int(sys.argv[1]) if len(sys.argv) > 1 else 7891
os.chdir(os.path.dirname(os.path.abspath(__file__)))
print(f"Serving {os.getcwd()} at http://127.0.0.1:{port}")
ThreadingHTTPServer(("127.0.0.1", port), SimpleHTTPRequestHandler).serve_forever()
