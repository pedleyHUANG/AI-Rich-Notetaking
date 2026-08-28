#!/usr/bin/env python3
"""
server.py -- local server for the AI Log.

Serves ai_log.html at "/" and exposes the log data as JSON at "/api/log":
  GET  /api/log   -> returns the current store {"tags": {...}, "entries": [...]}
  POST /api/log   -> replaces the store with the JSON body (whole-document write)

Because the browser talks to a real server instead of touching the disk
directly, this works in any browser -- Firefox and Safari included, not
just Chromium. log.py (the command-line tool) reads and writes the same
ai_log_data.json file, so CLI edits and browser edits stay in sync; just
reload the page to see CLI-made changes.

Usage:
    python3 server.py                  # serves on http://localhost:8420
    python3 server.py --port 9000
    python3 server.py --data other.json --html other.html
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_PORT = 8420
DEFAULT_DATA_FILE = 'ai_log_data.json'
DEFAULT_HTML_FILE = 'ai_log.html'

SEED_STORE = {
    "tags": {
        "idea": "#6c8ebf",
        "bug": "#d1584f",
        "decision": "#6fa273",
        "note": "#9b8f6b",
        "PROMPT!": "#ff8a3d"
    },
    "entries": []
}


def make_handler(data_path: Path, html_path: Path):

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

        def do_GET(self):
            if self.path == '/' or self.path == '':
                if not html_path.exists():
                    self._send_html(f'<h1>{html_path} not found</h1>', status=404)
                    return
                self._send_html(html_path.read_text(encoding='utf-8'))
            elif self.path == '/api/log':
                if not data_path.exists():
                    data_path.write_text(json.dumps(SEED_STORE, indent=2), encoding='utf-8')
                try:
                    store = json.loads(data_path.read_text(encoding='utf-8'))
                except json.JSONDecodeError as err:
                    self._send_json({'error': f'data file is not valid JSON: {err}'}, status=500)
                    return
                self._send_json(store)
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

            data_path.write_text(json.dumps(store, indent=2), encoding='utf-8')
            self._send_json({'ok': True})

        def log_message(self, fmt, *args):
            # quieter default logging -- comment this out for verbose request logs
            if self.path.startswith('/api/'):
                print(f'{self.address_string()} {fmt % args}')

    return Handler


def main():
    parser = argparse.ArgumentParser(description='Local server for the AI Log')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--data', default=DEFAULT_DATA_FILE, help='path to the JSON data file')
    parser.add_argument('--html', default=DEFAULT_HTML_FILE, help='path to the ai_log.html file')
    args = parser.parse_args()

    data_path = Path(args.data)
    html_path = Path(args.html)

    if not data_path.exists():
        data_path.write_text(json.dumps(SEED_STORE, indent=2), encoding='utf-8')
        print(f'Created new data file at {data_path}')

    if not html_path.exists():
        print(f'Warning: {html_path} not found in this directory -- "/" will 404 until it exists.')

    handler = make_handler(data_path, html_path)
    server = ThreadingHTTPServer(('localhost', args.port), handler)
    print(f'AI Log running at http://localhost:{args.port}  (Ctrl+C to stop)')
    print(f'Data file: {data_path.resolve()}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')


if __name__ == '__main__':
    main()
