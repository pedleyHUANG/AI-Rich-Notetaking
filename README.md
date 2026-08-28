# AI Log

A local, self-hosted notetaking log for tracking AI prompts, ideas, bugs, and
decisions — browsable in any browser and editable from the command line, both
reading and writing the same on-disk data.

![AI Log screenshot](docs/images/screenshot-main.png)
<!-- placeholder — see "Adding images" below -->

## Contents

- [Features](#features)
- [Dependencies](#dependencies)
- [Usage](#usage)
  - [Starting the server](#starting-the-server)
  - [Web UI](#web-ui)
  - [Command-line tool (`log.py`)](#command-line-tool-logpy)
- [Data storage](#data-storage)
- [File reference](#file-reference)
- [Adding images to this document](#adding-images-to-this-document)

## Features

- **Web UI** (`ai_log.html`) — add, edit, delete, search, and filter log
  entries; categories are colored tags with a dropdown selector so the list
  scales as you add more of them.
- **Markdown, code, and math rendering** — entry content supports Markdown,
  fenced code blocks (syntax-highlighted), and LaTeX-style math (`$...$`,
  `$$...$$`).
- **Expand modal** — a larger Preview/Edit view for reading or writing longer
  entries than the inline card comfortably fits.
- **Backdating** — log an entry as having happened in the past, down to the
  hour, instead of always using "now".
- **Command-line tool** (`log.py`) — add, edit, delete entries and manage
  categories from a terminal or a script, without opening a browser.
- **Sharded storage** — log data is split across multiple JSON files behind
  the scenes once it grows large, so no single file balloons forever; this is
  invisible to both the UI and the CLI.

## Dependencies

**Backend**: Python 3 standard library only (`http.server`, `json`,
`pathlib`, `argparse`) — no `pip install` required.

**Frontend**: vendored (checked into `vendor/`, no CDN/network access
needed at runtime):

| Library | Purpose |
|---|---|
| [marked](https://github.com/markedjs/marked) | Markdown → HTML |
| [highlight.js](https://github.com/highlightjs/highlight.js) | Code block syntax highlighting |
| [KaTeX](https://github.com/KaTeX/KaTeX) | LaTeX-style math rendering |
| [DOMPurify](https://github.com/cure53/DOMPurify) | Sanitizing rendered Markdown before it's inserted into the page |

## Usage

### Starting the server

```bash
python3 server.py                  # serves at http://localhost:8420
python3 server.py --port 9000      # use a different port
python3 server.py --dir other_dir  # store log data somewhere else
```

Open the printed URL in any browser (Chrome, Firefox, Safari all work,
since the page talks to a real local server rather than reading files
directly off disk).

If you get an "address already in use" error, something is already bound to
that port — find it with `lsof -i:8420` and either stop that process
(`kill <PID>`) or start this one on a different `--port`.

### Web UI

- **Add entry** (right panel) — title, question, categories, and content are
  all optional. Check "Log this in the past" to backdate an entry to a
  specific date and hour instead of using the current time.
- **Search / filter** (top of the center pane) — search box matches entry
  titles; the tag dropdown filters to entries carrying any of the selected
  categories. Both apply to the center list and the sidebar together.
- **Edit / Delete / Expand** (on each entry card) — Edit opens an inline
  form; Expand opens a larger Preview/Edit modal, useful for longer content;
  Delete removes the entry after confirmation.
- **Manage categories** (right panel) — add a category with a name and
  color, or delete one with the "×" on its chip (this also strips that
  category from every entry that had it).

### Command-line tool (`log.py`)

```bash
python3 log.py add    [--title T] [--question Q] [--category C ...] [--content TXT]
python3 log.py edit   <id> [--title T] [--question Q] [--category C ...] [--content TXT] [--add-note TXT]
python3 log.py delete <id>
python3 log.py tag    <name> <#hexcolor>
python3 log.py rmtag  <name>
python3 log.py list   [--category C] [--prompt-only]
```

All fields on `add` are optional — log a bare placeholder and fill in the
rest later with `edit`. If `--content` is omitted and something is piped
into stdin, that's used as the content:

```bash
echo "Remember to check the migration script" | python3 log.py add --title "Reminder" --category note
```

Pass `--dir <path>` before the subcommand to point at a log data directory
other than the current one.

CLI edits and browser edits stay in sync automatically — reload the page
(or re-run `list`) to see changes made from the other side.

## Data storage

Log data lives in the working directory as:

- `ai_log_meta.json` — category names/colors and the list of shard files
- `ai_log_data_0001.json`, `ai_log_data_0002.json`, ... — the actual entries,
  split across files once a shard passes 500 entries

You normally never touch these directly — `server.py` and `log.py` both
read/write through `store_io.py`, which presents them as a single merged
`{tags, entries}` document to both the browser and the CLI.

## File reference

| File | Role |
|---|---|
| `server.py` | HTTP server: serves the UI and the `/api/log` JSON endpoint |
| `log.py` | Command-line editor for the log data |
| `store_io.py` | Shared storage layer (sharding, migration) used by both of the above |
| `ai_log.html` | The web UI (single-file HTML/CSS/JS) |
| `vendor/` | Vendored frontend libraries (see [Dependencies](#dependencies)) |

## Adding images to this document

The screenshot placeholder at the top of this file points at
`docs/images/screenshot-main.png`, which doesn't exist yet — GitHub will
show a broken-image icon until you add it. To add a real screenshot:

1. Create the folder if it doesn't exist: `mkdir -p docs/images`
2. Save your image there, e.g. `docs/images/screenshot-main.png`
3. Reference it from Markdown with `![alt text](docs/images/your-file.png)`
   — the path is relative to this file's location in the repo.
4. Commit the image file along with your changes (`git add docs/images/...`)
   so it's actually part of the repository, not just present locally.

You can add as many images as you like this way — e.g. one per feature
(`docs/images/search-and-filter.png`, `docs/images/expand-modal.png`) placed
next to the section of this README that describes it.
