#!/usr/bin/env python3
"""
log.py -- command-line editor for the AI Log's data (see store_io.py).

This edits the same on-disk data that server.py serves to the browser, so
CLI changes and browser changes stay in sync -- just reload the page
(or restart the server) to see edits made from either side.

Entry schema:
    {
      "id": "...",
      "timestamp": "2026-08-07T14:32:00",   # set automatically on `add`
      "title": "...",       # optional
      "question": "...",    # optional; conventionally left blank for PROMPT! entries
      "categories": [...],  # 0-6 category names
      "content": "..."      # optional
    }

Commands:
    log.py add    [--title T] [--question Q] [--category C ...] [--content TXT]
    log.py edit   <id> [--title T] [--question Q] [--category C ...] [--content TXT] [--add-note TXT]
    log.py delete <id>
    log.py tag    <name> <#hexcolor>
    log.py rmtag  <name>
    log.py list   [--category C] [--prompt-only]

All fields on `add` are optional -- you can log a bare placeholder and
fill in the rest later with `edit`. If --content is omitted on `add`
and something is piped into stdin, that's used as the content.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import store_io

DEFAULT_DIR = '.'
MAX_CATEGORIES = 6


def load_store(directory: Path):
    return store_io.load_full_store(directory)


def save_store(directory: Path, store):
    store_io.save_full_store(directory, store)


def clean_categories(store, categories):
    if not categories:
        return []
    unknown = [c for c in categories if c not in store['tags']]
    if unknown:
        available = ', '.join(store['tags'].keys())
        sys.exit(f'Unknown categor{"y" if len(unknown)==1 else "ies"}: {", ".join(unknown)}\n'
                  f'Existing categories: {available}\n'
                  f'Add one first with: log.py tag <name> "#RRGGBB"')
    if len(categories) > MAX_CATEGORIES:
        print(f'Note: only the first {MAX_CATEGORIES} categories are kept.', file=sys.stderr)
    return categories[:MAX_CATEGORIES]


def read_content_arg(content):
    if content is not None:
        return content
    if not sys.stdin.isatty():
        return sys.stdin.read().rstrip('\n')
    return ''


def cmd_add(args):
    directory = Path(args.dir)
    store = load_store(directory)

    categories = clean_categories(store, args.category or [])
    content = read_content_arg(args.content)

    entry = {
        'id': 'e-' + str(int(datetime.now().timestamp() * 1000)),
        'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'title': args.title or '',
        'question': '' if 'PROMPT!' in categories else (args.question or ''),
        'categories': categories,
        'content': content,
    }
    store['entries'].append(entry)
    save_store(directory, store)
    label = entry['title'] or '(untitled)'
    print(f'Added entry "{label}" [{", ".join(categories) or "no category"}] id={entry["id"]}')


def cmd_edit(args):
    directory = Path(args.dir)
    store = load_store(directory)

    entry = next((e for e in store['entries'] if e['id'] == args.id), None)
    if entry is None:
        sys.exit(f'No entry with id "{args.id}". Use `log.py list` to see ids.')

    if args.title is not None:
        entry['title'] = args.title
    if args.category is not None:
        entry['categories'] = clean_categories(store, args.category)
    if args.question is not None:
        entry['question'] = '' if 'PROMPT!' in entry.get('categories', []) else args.question
    if args.content is not None:
        entry['content'] = args.content
    if args.add_note is not None:
        stamp = datetime.now().strftime('%H:%M:%S')
        entry['content'] = (entry['content'] + '\n\n' if entry.get('content') else '') + f'[{stamp}] {args.add_note}'

    save_store(directory, store)
    print(f'Updated entry {args.id}')


def cmd_delete(args):
    directory = Path(args.dir)
    store = load_store(directory)

    before = len(store['entries'])
    store['entries'] = [e for e in store['entries'] if e['id'] != args.id]
    if len(store['entries']) == before:
        sys.exit(f'No entry with id "{args.id}". Use `log.py list` to see ids.')

    save_store(directory, store)
    print(f'Deleted entry {args.id}')


def cmd_tag(args):
    directory = Path(args.dir)
    store = load_store(directory)

    color = args.color
    if not color.startswith('#'):
        color = '#' + color
    store['tags'][args.name] = color
    save_store(directory, store)
    print(f'Category "{args.name}" set to {color}')


def cmd_rmtag(args):
    directory = Path(args.dir)
    store = load_store(directory)

    if args.name not in store['tags']:
        sys.exit(f'No such category "{args.name}".')

    del store['tags'][args.name]
    for entry in store['entries']:
        entry['categories'] = [c for c in entry.get('categories', []) if c != args.name]

    save_store(directory, store)
    print(f'Removed category "{args.name}" (and stripped it from all entries)')


def cmd_list(args):
    directory = Path(args.dir)
    store = load_store(directory)

    entries = store['entries']
    if args.prompt_only:
        entries = [e for e in entries if 'PROMPT!' in e.get('categories', [])]
    elif args.category:
        entries = [e for e in entries if args.category in e.get('categories', [])]
    entries = sorted(entries, key=lambda e: e['timestamp'], reverse=True)

    if not entries:
        print('No matching entries.')
        return

    for e in entries:
        cats = ','.join(e.get('categories', [])) or '-'
        title = e['title'] or '(untitled)'
        print(f'{e["timestamp"]}  [{cats}]  {title}  id={e["id"]}')


def build_parser():
    parser = argparse.ArgumentParser(description="Command-line editor for the AI Log's data")
    parser.add_argument('--dir', default=DEFAULT_DIR, help=f'directory holding the log data files (default: {DEFAULT_DIR})')
    sub = parser.add_subparsers(dest='command', required=True)

    p_add = sub.add_parser('add', help='add a new log entry (all fields optional)')
    p_add.add_argument('--title', default=None)
    p_add.add_argument('--question', default=None)
    p_add.add_argument('--category', action='append', help='repeat for multiple, up to 6')
    p_add.add_argument('--content', default=None, help='if omitted, reads piped stdin, else blank')
    p_add.set_defaults(func=cmd_add)

    p_edit = sub.add_parser('edit', help='edit an existing entry, or append a timestamped note to it')
    p_edit.add_argument('id')
    p_edit.add_argument('--title', default=None)
    p_edit.add_argument('--question', default=None)
    p_edit.add_argument('--category', action='append', help='repeat for multiple, up to 6 (replaces the full list)')
    p_edit.add_argument('--content', default=None, help='replaces the content outright')
    p_edit.add_argument('--add-note', default=None, help='appends a timestamped line instead of replacing content')
    p_edit.set_defaults(func=cmd_edit)

    p_delete = sub.add_parser('delete', help='delete an entry')
    p_delete.add_argument('id')
    p_delete.set_defaults(func=cmd_delete)

    p_tag = sub.add_parser('tag', help='add or update a category color')
    p_tag.add_argument('name')
    p_tag.add_argument('color', help='hex color, e.g. #ff8a3d or ff8a3d')
    p_tag.set_defaults(func=cmd_tag)

    p_rmtag = sub.add_parser('rmtag', help='delete a category and strip it from all entries')
    p_rmtag.add_argument('name')
    p_rmtag.set_defaults(func=cmd_rmtag)

    p_list = sub.add_parser('list', help='list entries in the terminal')
    p_list.add_argument('--category', default=None)
    p_list.add_argument('--prompt-only', action='store_true')
    p_list.set_defaults(func=cmd_list)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
