from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_SQL_KEYWORDS = frozenset({
    'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'AS', 'ON',
    'CREATE', 'TABLE', 'ALTER', 'ADD', 'DROP', 'COLUMN', 'MODIFY', 'CHANGE',
    'SET', 'NULL', 'PRIMARY', 'KEY', 'FOREIGN', 'REFERENCES',
    'INDEX', 'UNIQUE', 'CONSTRAINT', 'DEFAULT', 'CHECK',
    'INSERT', 'INTO', 'VALUES', 'UPDATE', 'DELETE', 'WITH',
    'ORDER', 'GROUP', 'BY', 'HAVING', 'LIMIT', 'OFFSET',
    'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'CROSS', 'FULL',
    'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'CAST',
    'TRUE', 'FALSE', 'IS', 'LIKE', 'BETWEEN', 'EXISTS',
    'DISTINCT', 'TOP', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
    'OVER', 'PARTITION', 'ROW', 'ROWS', 'RANGE', 'UNBOUNDED',
    'PRECEDING', 'FOLLOWING', 'CURRENT', 'USE', 'DATABASE', 'SCHEMA',
})

_COL_NAME_RE = re.compile(r'^[+-]\s*(\w+)')
_ANNOTATION_RE = re.compile(
    r'[+#-]?\s*(?:--|#)\s*cascade:\s*rename\s+(\w+)\s*->\s*(\w+)',
    re.IGNORECASE,
)
_DIFF_HEADER_RE = re.compile(r'^diff --git', re.MULTILINE)


def _is_column_line(line: str) -> str | None:
    m = _COL_NAME_RE.match(line)
    if m:
        name = m.group(1)
        if name.upper() not in _SQL_KEYWORDS:
            return name
    return None


def _find_annotations(text: str) -> dict[str, str]:
    renames: dict[str, str] = {}
    for line in text.splitlines():
        m = _ANNOTATION_RE.search(line)
        if m:
            renames[m.group(1)] = m.group(2)
    return renames


def _parse_file_section(section: str) -> list[dict[str, Any]]:
    annotations = _find_annotations(section)
    removed: dict[str, str] = {}
    added: dict[str, str] = {}

    for line in section.splitlines():
        col = _is_column_line(line)
        if col is None:
            continue
        if line.startswith('-'):
            removed[col] = line
        elif line.startswith('+'):
            added[col] = line

    changes: list[dict[str, Any]] = []

    for from_name, to_name in annotations.items():
        changes.append({
            "type": "FIELD_RENAMED",
            "from": from_name,
            "to": to_name,
            "detected_by": "annotation",
        })
        removed.pop(from_name, None)
        added.pop(to_name, None)

    if len(removed) == 1 and len(added) == 1:
        from_name = next(iter(removed))
        to_name = next(iter(added))
        changes.append({
            "type": "FIELD_RENAMED",
            "from": from_name,
            "to": to_name,
            "detected_by": "heuristic",
        })
        removed.pop(from_name)

    for col in removed:
        changes.append({
            "type": "FIELD_REMOVED",
            "from": col,
            "to": None,
            "detected_by": "heuristic",
        })

    return changes


def parse_diff(text: str) -> list[dict[str, Any]]:
    sections = _DIFF_HEADER_RE.split(text)
    sections = [s for s in sections if s.strip()]

    all_changes: list[dict[str, Any]] = []
    for section in sections:
        all_changes.extend(_parse_file_section(section))

    return all_changes


def parse_changes_text(text: str) -> list[dict[str, Any]]:
    """Parse pasted JSON changes or a unified SQL/dbt diff."""
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith("{") or stripped.startswith("["):
        data = json.loads(text)
        return data if isinstance(data, list) else data.get("changes", [])
    return parse_diff(text)


def load_changes(path: str | Path) -> list[dict[str, Any]]:
    return parse_changes_text(Path(path).read_text())
