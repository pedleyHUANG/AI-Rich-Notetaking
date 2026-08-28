#!/usr/bin/env python3
"""
store_io.py -- shared storage layer for the AI Log, used by both server.py
and log.py.

On disk the log is stored as:
  ai_log_meta.json        {"tags": {...}, "shards": ["ai_log_data_0001.json", ...], "shard_size": 500}
  ai_log_data_0001.json   {"entries": [...]}
  ai_log_data_0002.json   {"entries": [...]}
  ...

Sharding is entirely transparent to callers: load_full_store() returns the
same {"tags": {...}, "entries": [...]} shape the browser/CLI have always
worked with, and save_full_store() takes that same shape and figures out
which shard each entry belongs in.

If no meta file exists yet but a legacy combined ai_log_data.json
({"tags": ..., "entries": ...} in one file) does, it is migrated
automatically: its entries become the first shard, a meta file is written,
and the legacy file is renamed to ai_log_data.legacy.json (kept, not
deleted).
"""

import json
from pathlib import Path

META_FILENAME = 'ai_log_meta.json'
LEGACY_FILENAME = 'ai_log_data.json'
SHARD_PREFIX = 'ai_log_data_'
SHARD_SUFFIX = '.json'
DEFAULT_SHARD_SIZE = 500

SEED_TAGS = {
    "idea": "#6c8ebf",
    "bug": "#d1584f",
    "decision": "#6fa273",
    "note": "#9b8f6b",
    "PROMPT!": "#ff8a3d"
}


def _shard_name(index: int) -> str:
    return f'{SHARD_PREFIX}{index:04d}{SHARD_SUFFIX}'


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def _write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2), encoding='utf-8')


def _migrate_legacy(directory: Path) -> dict:
    legacy_path = directory / LEGACY_FILENAME
    legacy = json.loads(legacy_path.read_text(encoding='utf-8'))
    tags = legacy.get('tags', {})
    entries = legacy.get('entries', [])

    shard_name = _shard_name(1)
    _write_json(directory / shard_name, {'entries': entries})

    meta = {'tags': tags, 'shards': [shard_name], 'shard_size': DEFAULT_SHARD_SIZE}
    _write_json(directory / META_FILENAME, meta)

    legacy_path.rename(directory / 'ai_log_data.legacy.json')
    return meta


def _load_meta(directory: Path) -> dict:
    meta_path = directory / META_FILENAME
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding='utf-8'))

    if (directory / LEGACY_FILENAME).exists():
        return _migrate_legacy(directory)

    shard_name = _shard_name(1)
    _write_json(directory / shard_name, {'entries': []})
    meta = {'tags': dict(SEED_TAGS), 'shards': [shard_name], 'shard_size': DEFAULT_SHARD_SIZE}
    _write_json(directory / META_FILENAME, meta)
    return meta


def load_full_store(directory: Path) -> dict:
    meta = _load_meta(directory)
    entries = []
    for shard_name in meta['shards']:
        shard = _read_json(directory / shard_name, {'entries': []})
        entries.extend(shard.get('entries', []))
    return {'tags': meta.get('tags', {}), 'entries': entries}


def save_full_store(directory: Path, store: dict) -> None:
    meta = _load_meta(directory)
    shard_size = meta.get('shard_size', DEFAULT_SHARD_SIZE)
    shard_names = list(meta['shards'])

    id_to_shard = {}
    old_shard_entries = {}
    for shard_name in shard_names:
        shard = _read_json(directory / shard_name, {'entries': []})
        old_shard_entries[shard_name] = shard.get('entries', [])
        for entry in old_shard_entries[shard_name]:
            id_to_shard[entry['id']] = shard_name

    new_shard_entries = {name: [] for name in shard_names}
    trailing_new_entries = []

    for entry in store.get('entries', []):
        home_shard = id_to_shard.get(entry['id'])
        if home_shard is not None:
            new_shard_entries[home_shard].append(entry)
        else:
            trailing_new_entries.append(entry)

    last_shard = shard_names[-1]
    for entry in trailing_new_entries:
        if len(new_shard_entries[last_shard]) >= shard_size:
            last_shard = _shard_name(len(shard_names) + 1)
            shard_names.append(last_shard)
            new_shard_entries[last_shard] = []
        new_shard_entries[last_shard].append(entry)

    for shard_name in shard_names:
        _write_json(directory / shard_name, {'entries': new_shard_entries[shard_name]})

    meta['tags'] = store.get('tags', {})
    meta['shards'] = shard_names
    _write_json(directory / META_FILENAME, meta)
