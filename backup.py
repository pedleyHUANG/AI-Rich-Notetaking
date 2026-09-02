#!/usr/bin/env python3
"""
backup.py -- manual, one-off backup of the AI Log's JSON data files.

MANUAL TOOL ONLY. This module performs no action on import: backup_logs()
is only ever invoked from the `if __name__ == '__main__'` guard below, and
nothing in server.py, log.py, store_io.py, or any hook/automation calls it.
Run it yourself, on purpose, with:

    python backup.py

What gets moved
----------------
The log data lives in a small family of JSON files at the repo root
(see store_io.py), all of which carry the user's own free-text notes and
AI-conversation content -- not structured PII like names/emails/IPs, but
personal journaling content that deserves care:

  ai_log_meta.json            index: {"tags": {...}, "shards": [...], ...}
  ai_log_data_NNNN.json       shard file: {"entries": [...]}
  ai_log_data.json            legacy combined file (pre-sharding)
  ai_log_data.legacy.json     legacy file, kept after auto-migration

Each entry inside a shard/legacy file carries these user-data fields:
  id          synthetic id, not personally identifying
  timestamp   local wall-clock time the entry was written
  title       free text, user-chosen
  question    free text -- the prompt/question the entry is about
  categories  list of tag names the user picked
  content     free text -- the bulk of the personal notes/AI-chat content

Where it goes, and why that's a Claude-Code-safe spot
-------------------------------------------------------
Claude Code's file tools (Read/Edit/Glob/Grep) operate on the working
directory tree of the project it was opened in -- here, this repo,
AiLogServer/. They don't reach outside that root during ordinary work.
BACKUP_ROOT below is a *sibling* of this repo (.. /AiLogServer_backups),
outside the git working tree and outside that project root, so files
moved there sit outside Claude Code's normal read/edit/glob scope.
This is an organizational boundary for keeping notes out of casual
Claude Code visibility, not an access-control or encryption mechanism --
anyone/anything with filesystem access to the machine can still reach it.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent
BACKUP_ROOT = SOURCE_DIR.parent / 'AiLogServer_backups'

LEGACY_FILENAMES = {'ai_log_meta.json', 'ai_log_data.json', 'ai_log_data.legacy.json'}
SHARD_PATTERN = re.compile(r'^ai_log_data_\d{4}\.json$')


def find_log_files(directory: Path) -> list:
    """Return every JSON log/data file in `directory` matching the known
    AI Log filename patterns (see module docstring)."""
    found = []
    for path in sorted(directory.glob('*.json')):
        if path.name in LEGACY_FILENAMES or SHARD_PATTERN.match(path.name):
            found.append(path)
    return found


def backup_logs() -> Path:
    """Move all AI Log JSON files out of the repo into a new timestamped
    folder under BACKUP_ROOT. Returns the backup folder's path."""
    log_files = find_log_files(SOURCE_DIR)
    if not log_files:
        print('No AI Log JSON files found -- nothing to back up.')
        return BACKUP_ROOT

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_ROOT / f'backup_{timestamp}'
    backup_path.mkdir(parents=True)

    for path in log_files:
        shutil.move(str(path), str(backup_path / path.name))
        print(f'Moved {path.name} -> {backup_path}')

    print(f'Backed up {len(log_files)} file(s) to {backup_path}')
    return backup_path


if __name__ == '__main__':
    backup_logs()
