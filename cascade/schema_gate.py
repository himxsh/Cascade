from __future__ import annotations

import re
from typing import AbstractSet

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
})

_IDENTIFIER_RE = re.compile(r'[a-zA-Z_]\w*')
_QUALIFIED_RE = re.compile(r'([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)')


# ponytail: naive word-token scan, no SQL parser. Single-char aliases and
#   qualified refs (t.col pass through). Upgrades: sqlparse-based AST visitor.
def validate_sql(sql: str, allowed_columns: AbstractSet[str]) -> None:
    identifiers = set(_IDENTIFIER_RE.findall(sql))
    qualified: set[str] = set()
    for m in _QUALIFIED_RE.finditer(sql):
        qualified.add(m.group(1))
        qualified.add(m.group(2))
    allowed_lower = {c.lower() for c in allowed_columns}
    unknown: list[str] = sorted(
        i for i in identifiers
        if len(i) > 1
        and i not in qualified
        and i.lower() not in allowed_lower
        and i.upper() not in _SQL_KEYWORDS
    )
    if unknown:
        raise ValueError(
            f"Schema gate rejected unknown identifiers: {unknown}. "
            f"Allowed: {sorted(allowed_columns)}"
        )
