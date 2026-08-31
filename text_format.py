#!/usr/bin/env python3
"""
text_format.py -- display-only text cleanup for log entry content.

These functions are purely cosmetic: they never modify what's stored on
disk (see store_io.py), only what gets shown to a human. Call them at the
point of display (e.g. log.py's `show` command), never when writing data.
"""

import re

_LONE_ASTERISK_LINE = re.compile(r'^[ \t]*\*[ \t]*$')


def strip_stray_asterisk_lines(text: str) -> str:
    """Drop any line that consists solely of a single '*' (optionally
    padded with whitespace), wherever it appears in the text.

    Some pasted sources (e.g. Gemini output) wrap each bullet list in a
    stray '*' line before and after it, like:

        *
        * point one
        * point two
        *

    and may do this more than once in a single entry (e.g. a paragraph,
    then another wrapped list further down). The '* point one' lines are
    normal markdown bullets and are left alone; only the empty '*' lines
    are dropped, regardless of where in the text they occur.
    """
    if not text:
        return text

    lines = [line for line in text.split('\n') if not _LONE_ASTERISK_LINE.match(line)]
    return '\n'.join(lines)


def clean_display_text(text: str) -> str:
    """Apply all display-only cleanup passes to entry content/question text."""
    return strip_stray_asterisk_lines(text)
