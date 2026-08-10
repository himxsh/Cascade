from __future__ import annotations

import re
from typing import AbstractSet, Any

_SQL_KEYWORDS: frozenset[str] = frozenset({
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
    'DESC', 'ASC', 'INT', 'VARCHAR', 'DECIMAL', 'FLOAT', 'BOOLEAN',
    'TIMESTAMP', 'DATE', 'NUMBER', 'STRING', 'BIGINT', 'SMALLINT',
    'TINYINT', 'DOUBLE', 'PRECISION', 'NOT', 'NULL',
    'JOIN', 'GROUP', 'BY', 'COUNT', 'SUM',
})

_IDENTIFIER_RE = re.compile(r'[a-zA-Z_]\w*')
_QUALIFIED_CHAIN_RE = re.compile(r'[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+')
_AS_ALIAS_RE = re.compile(r'\bAS\s+([a-zA-Z_]\w*)', re.IGNORECASE)
# alias.col AS name  OR  col AS name
_AS_SOURCE_RE = re.compile(
    r'([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)?)\s+AS\s+([a-zA-Z_]\w*)',
    re.IGNORECASE,
)
_FROM_JOIN_TABLE_RE = re.compile(
    r'\b(?:FROM|JOIN)\s+([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)',
    re.IGNORECASE,
)
_LINE_COMMENT_RE = re.compile(r'--.*?$', re.MULTILINE)
_BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/', re.DOTALL)


def _strip_sql_comments(sql: str) -> str:
    sql = _BLOCK_COMMENT_RE.sub(' ', sql)
    return _LINE_COMMENT_RE.sub(' ', sql)


def _renames(changes: list[dict[str, Any]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for c in changes:
        if c.get("type") != "FIELD_RENAMED":
            continue
        old, new = c.get("from"), c.get("to")
        if old and new:
            out.append((str(old), str(new)))
    return out


# ponytail: naive word-token scan, no SQL parser. 2-part chains validate the
#   column; 3+ part / FROM-JOIN names treated as table refs. Upgrade: sqlparse.
def validate_sql(sql: str, allowed_columns: AbstractSet[str]) -> None:
    sql = _strip_sql_comments(sql)
    identifiers = set(_IDENTIFIER_RE.findall(sql))
    skip: set[str] = set()
    must_allow: set[str] = set()
    for m in _FROM_JOIN_TABLE_RE.finditer(sql):
        skip.update(m.group(1).split('.'))
    for m in _QUALIFIED_CHAIN_RE.finditer(sql):
        parts = m.group(0).split('.')
        if len(parts) >= 3:
            # db.schema.table (or longer) — not a column ref
            skip.update(parts)
        else:
            # alias.column — validate column, skip alias
            skip.add(parts[0])
            must_allow.add(parts[1])
    for m in _AS_ALIAS_RE.finditer(sql):
        skip.add(m.group(1))
    allowed_lower = {c.lower() for c in allowed_columns}
    unknown: list[str] = sorted(
        {
            i for i in identifiers
            if len(i) > 1
            and i not in skip
            and i.lower() not in allowed_lower
            and i.upper() not in _SQL_KEYWORDS
        }
        | {
            i for i in must_allow
            if i not in skip
            and i.lower() not in allowed_lower
            and i.upper() not in _SQL_KEYWORDS
        }
    )
    if unknown:
        raise ValueError(
            f"Schema gate rejected unknown identifiers: {unknown}. "
            f"Allowed: {sorted(allowed_columns)}"
        )


def validate_rename_semantics(sql: str, changes: list[dict[str, Any]]) -> None:
    """Reject wrong-direction aliases and rename-target misuse."""
    stripped = _strip_sql_comments(sql)
    lower = stripped.lower()
    renames = _renames(changes)
    if not renames:
        return

    for old, new in renames:
        # Upstream is already `new`; never `old AS new`.
        if re.search(rf'\b{re.escape(old)}\s+as\s+{re.escape(new)}\b', lower):
            raise ValueError(
                f"Schema gate rejected wrong rename direction: "
                f"{old} AS {new} (use {new} or {new} AS {old})"
            )

    to_names = {new.lower(): (old, new) for old, new in renames}
    for m in _AS_SOURCE_RE.finditer(stripped):
        source, alias = m.group(1), m.group(2)
        hit = to_names.get(alias.lower())
        if not hit:
            continue
        old, new = hit
        src_l = source.lower()
        if re.search(rf'\b{re.escape(old)}\b', src_l) or re.search(
            rf'\b{re.escape(new)}\b', src_l
        ):
            continue
        raise ValueError(
            f"Schema gate rejected unrelated alias to rename target: "
            f"{source} AS {alias} (rename is {old} → {new})"
        )
