#!/usr/bin/env python3
"""
server.py -- local server for the AI Log.

Serves ai_log.html at "/", spec_organization.html at "/spec",
long_conversation.html at "/long", static assets (e.g. the vendored
markdown/code/math renderers under vendor/) by relative path, and exposes
the log data as JSON at "/api/log" and friends:
  GET  /api/log               -> returns the current store {"tags": {...}, "entries": [...]}
  POST /api/log/entry         -> add or update one entry; body is the entry object
  POST /api/log/entry/delete  -> delete one entry; body {"id": "..."}
  POST /api/log/tag           -> add or update one category; body {"name": "...", "color": "..."}
  POST /api/log/tag/delete    -> delete one category; body {"name": "..."}

The Spec Organization page reads and writes markdown files under
markdownAssets/ through a small JSON API of its own:
  GET  /api/markdown/list          -> {"files": ["a.md", "b.md", ...]}
  GET  /api/markdown/file?name=... -> {"content": "..."}
  POST /api/markdown/save          -> body {"name": "...", "content": "..."}

Each of these writes touches only the data it changed (see store_io.py's
upsert_entry/delete_entry/upsert_tag/delete_tag) instead of replacing the
whole document, so a stale or partial client-side copy of the store can't
wipe out entries it doesn't know about.

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
from urllib.parse import urlparse, parse_qs

import store_io

DEFAULT_PORT = 8420
DEFAULT_DIR = '.'
DEFAULT_HTML_FILE = 'ai_log.html'
SPEC_HTML_FILE = 'spec_organization.html'
LONG_HTML_FILE = 'long_conversation.html'
MARKDOWN_ASSETS_DIR = 'markdownAssets'

mimetypes.add_type('font/woff2', '.woff2')


def make_handler(data_dir: Path, html_path: Path, root_dir: Path):

    static_root = (root_dir / 'vendor').resolve()
    spec_html_path = root_dir / SPEC_HTML_FILE
    long_html_path = root_dir / LONG_HTML_FILE
    markdown_root = (root_dir / MARKDOWN_ASSETS_DIR).resolve()

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
            """Resolve self.path to a file under vendor/, or None if unsafe/missing."""
            rel = self.path.split('?', 1)[0].lstrip('/')
            candidate = (root_dir / rel).resolve()
            try:
                candidate.relative_to(static_root)
            except ValueError:
                return None
            if candidate.is_file():
                return candidate
            return None

        def _markdown_path(self, name):
            """Resolve a filename to a .md file under markdownAssets/, or None if unsafe."""
            if not name or not name.endswith('.md'):
                return None
            candidate = (markdown_root / name).resolve()
            try:
                candidate.relative_to(markdown_root)
            except ValueError:
                return None
            return candidate

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == '/' or parsed.path == '':
                if not html_path.exists():
                    self._send_html(f'<h1>{html_path} not found</h1>', status=404)
                    return
                self._send_html(html_path.read_text(encoding='utf-8'))
            elif parsed.path == '/spec':
                if not spec_html_path.exists():
                    self._send_html(f'<h1>{spec_html_path} not found</h1>', status=404)
                    return
                self._send_html(spec_html_path.read_text(encoding='utf-8'))
            elif parsed.path == '/long':
                if not long_html_path.exists():
                    self._send_html(f'<h1>{long_html_path} not found</h1>', status=404)
                    return
                self._send_html(long_html_path.read_text(encoding='utf-8'))
            elif parsed.path == '/api/log':
                store = store_io.load_full_store(data_dir)
                self._send_json(store)
            elif parsed.path == '/api/markdown/list':
                if markdown_root.is_dir():
                    files = sorted(p.name for p in markdown_root.iterdir() if p.suffix == '.md' and p.is_file())
                else:
                    files = []
                self._send_json({'files': files})
            elif parsed.path == '/api/markdown/file':
                name = parse_qs(parsed.query).get('name', [None])[0]
                md_path = self._markdown_path(name)
                if md_path is None or not md_path.is_file():
                    self._send_json({'error': 'not found'}, status=404)
                    return
                self._send_json({'content': md_path.read_text(encoding='utf-8')})
            else:
                static_path = self._static_path()
                if static_path is not None:
                    self._send_static(static_path)
                else:
                    self._send_json({'error': 'not found'}, status=404)

        def _read_json_body(self):
            length = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(length)
            return json.loads(raw)

        def do_POST(self):
            if self.path not in ('/api/log/entry', '/api/log/entry/delete',
                                  '/api/log/tag', '/api/log/tag/delete',
                                  '/api/markdown/save'):
                self._send_json({'error': 'not found'}, status=404)
                return
            try:
                body = self._read_json_body()
            except (ValueError, json.JSONDecodeError) as err:
                self._send_json({'error': f'invalid JSON body: {err}'}, status=400)
                return

            if self.path == '/api/markdown/save':
                if not isinstance(body, dict) or not body.get('name') or 'content' not in body:
                    self._send_json({'error': 'body must contain "name" and "content"'}, status=400)
                    return
                md_path = self._markdown_path(body['name'])
                if md_path is None:
                    self._send_json({'error': f'invalid file name "{body["name"]}"'}, status=400)
                    return
                md_path.write_text(body['content'], encoding='utf-8')
                self._send_json({'ok': True})

            elif self.path == '/api/log/entry':
                if not isinstance(body, dict) or not body.get('id'):
                    self._send_json({'error': 'body must be an entry object with an "id"'}, status=400)
                    return
                store_io.upsert_entry(data_dir, body)
                self._send_json({'ok': True})

            elif self.path == '/api/log/entry/delete':
                if not isinstance(body, dict) or not body.get('id'):
                    self._send_json({'error': 'body must contain "id"'}, status=400)
                    return
                if not store_io.delete_entry(data_dir, body['id']):
                    self._send_json({'error': f'no entry with id "{body["id"]}"'}, status=404)
                    return
                self._send_json({'ok': True})

            elif self.path == '/api/log/tag':
                if not isinstance(body, dict) or not body.get('name') or not body.get('color'):
                    self._send_json({'error': 'body must contain "name" and "color"'}, status=400)
                    return
                store_io.upsert_tag(data_dir, body['name'], body['color'])
                self._send_json({'ok': True})

            else:  # /api/log/tag/delete
                if not isinstance(body, dict) or not body.get('name'):
                    self._send_json({'error': 'body must contain "name"'}, status=400)
                    return
                if not store_io.delete_tag(data_dir, body['name']):
                    self._send_json({'error': f'no category "{body["name"]}"'}, status=404)
                    return
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

    # The Long Conversation page files entries under this category, and log.py
    # rejects categories that aren't registered, so a store predating the
    # feature needs it added once.
    store = store_io.load_full_store(data_dir)
    if store_io.LONG_CONVERSATION_TAG not in store['tags']:
        store_io.upsert_tag(data_dir, store_io.LONG_CONVERSATION_TAG,
                            store_io.SEED_TAGS[store_io.LONG_CONVERSATION_TAG])
        print(f'Added the "{store_io.LONG_CONVERSATION_TAG}" category to this log.')

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
