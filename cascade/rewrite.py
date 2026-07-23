from __future__ import annotations

import re


def rename_column(sql: str, from_name: str, to_name: str) -> str:
    return re.sub(rf'\b{re.escape(from_name)}\b', to_name, sql)
