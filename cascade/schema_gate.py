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
_QUALIFIED_CHAIN_RE = re.compile(r'[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+')
_AS_ALIAS_RE = re.compile(r'\bAS\s+([a-zA-Z_]\w*)', re.IGNORECASE)
_LINE_COMMENT_RE = re.compile(r'--.*?$', re.MULTILINE)
_BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/', re.DOTALL)


def _strip_sql_comments(sql: str) -> str:
    sql = _BLOCK_COMMENT_RE.sub(' ', sql)
    return _LINE_COMMENT_RE.sub(' ', sql)


# ponytail: naive word-token scan, no SQL parser. Comments stripped; dotted
#   table refs + AS aliases pass. Upgrade: sqlparse AST.
def validate_sql(sql: str, allowed_columns: AbstractSet[str]) -> None:
    sql = _strip_sql_comments(sql)
    identifiers = set(_IDENTIFIER_RE.findall(sql))
    skip: set[str] = set()
    for m in _QUALIFIED_CHAIN_RE.finditer(sql):
        for part in m.group(0).split('.'):
            skip.add(part)
    for m in _AS_ALIAS_RE.finditer(sql):
        skip.add(m.group(1))
    allowed_lower = {c.lower() for c in allowed_columns}
    unknown: list[str] = sorted(
        i for i in identifiers
        if len(i) > 1
        and i not in skip
        and i.lower() not in allowed_lower
        and i.upper() not in _SQL_KEYWORDS
    )
    if unknown:
        raise ValueError(
            f"Schema gate rejected unknown identifiers: {unknown}. "
            f"Allowed: {sorted(allowed_columns)}"
        )
