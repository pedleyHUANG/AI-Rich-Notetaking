#!/usr/bin/env python3
"""
server.py -- local server for the AI Log.

Serves ai_log.html at "/", static assets (e.g. the vendored markdown/code/
math renderers under vendor/) by relative path, and exposes the log data
as JSON at "/api/log":
  GET  /api/log   -> returns the current store {"tags": {...}, "entries": [...]}
  POST /api/log   -> replaces the store with the JSON body (whole-document write)

Because the browser talks to a real server instead of touching the disk
directly, this works in any browser -- Firefox and Safari included, not
just Chromium. log.py (the command-line tool) reads and writes the same
on-disk log data (see store_io.py), so CLI edits and browser edits stay in
sync; just reload the page to see CLI-made changes.

The log data itself is stored across one or more shard files plus an
ai_log_meta.json index (see store_io.py) so a single JSON file doesn't
grow without bound; this is invisible to the browser, which always sees
one merged {"tags", "entries"} document.

Usage:
    python3 server.py                  # serves on http://localhost:8420
    python3 server.py --port 9000
    python3 server.py --dir other_dir --html other.html
"""

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import store_io

DEFAULT_PORT = 8420
DEFAULT_DIR = '.'
DEFAULT_HTML_FILE = 'ai_log.html'

mimetypes.add_type('font/woff2', '.woff2')


def make_handler(data_dir: Path, html_path: Path, root_dir: Path):

    class Handler(BaseHTTPRequestHandler):

        def _send_json(self, obj, status=200):
            body = json.dumps(obj).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, text, status=200):
            body = text.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_static(self, path: Path):
            content_type, _ = mimetypes.guess_type(str(path))
            body = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', content_type or 'application/octet-stream')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _static_path(self):
            """Resolve self.path to a file under root_dir, or None if unsafe/missing."""
            rel = self.path.split('?', 1)[0].lstrip('/')
            candidate = (root_dir / rel).resolve()
            try:
                candidate.relative_to(root_dir.resolve())
            except ValueError:
                return None
            if candidate.is_file():
                return candidate
            return None

        def do_GET(self):
            if self.path == '/' or self.path == '':
                if not html_path.exists():
                    self._send_html(f'<h1>{html_path} not found</h1>', status=404)
                    return
                self._send_html(html_path.read_text(encoding='utf-8'))
            elif self.path == '/api/log':
                store = store_io.load_full_store(data_dir)
                self._send_json(store)
            else:
                static_path = self._static_path()
                if static_path is not None:
                    self._send_static(static_path)
                else:
                    self._send_json({'error': 'not found'}, status=404)

        def do_POST(self):
            if self.path != '/api/log':
                self._send_json({'error': 'not found'}, status=404)
                return
            try:
                length = int(self.headers.get('Content-Length', 0))
                raw = self.rfile.read(length)
                store = json.loads(raw)
            except (ValueError, json.JSONDecodeError) as err:
                self._send_json({'error': f'invalid JSON body: {err}'}, status=400)
                return

            if not isinstance(store, dict) or 'tags' not in store or 'entries' not in store:
                self._send_json({'error': 'body must contain "tags" and "entries"'}, status=400)
                return

            store_io.save_full_store(data_dir, store)
            self._send_json({'ok': True})

        def log_message(self, fmt, *args):
            # quieter default logging -- comment this out for verbose request logs
            if self.path.startswith('/api/'):
                print(f'{self.address_string()} {fmt % args}')

        def handle_one_request(self):
            # A client that disconnects mid-response (closed tab, cancelled
            # fetch) raises BrokenPipeError/ConnectionResetError from wfile
            # writes -- that's normal and not worth a scary traceback.
            try:
                super().handle_one_request()
            except (BrokenPipeError, ConnectionResetError):
                pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description='Local server for the AI Log')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--dir', default=DEFAULT_DIR, help='directory holding the log data files')
    parser.add_argument('--html', default=DEFAULT_HTML_FILE, help='path to the ai_log.html file')
    args = parser.parse_args()

    data_dir = Path(args.dir)
    html_path = Path(args.html)
    root_dir = html_path.resolve().parent

    if not html_path.exists():
        print(f'Warning: {html_path} not found in this directory -- "/" will 404 until it exists.')

    handler = make_handler(data_dir, html_path, root_dir)
    server = ThreadingHTTPServer(('localhost', args.port), handler)
    print(f'AI Log running at http://localhost:{args.port}  (Ctrl+C to stop)')
    print(f'Data directory: {data_dir.resolve()}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')


if __name__ == '__main__':
    main()
