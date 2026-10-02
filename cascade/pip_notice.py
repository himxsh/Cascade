"""Next-steps text shown while pip builds/installs cascade-bot.

Printed from the in-tree PEP 517 backend (stderr + controlling TTY).
Do not write to stdout — that can break the build-hook protocol.
"""

from __future__ import annotations

import sys

NOTICE = """\
Next: run `cascade setup` in your SQL/dbt repo, then open a PR that touches SQL or models.
Cascade will comment. Live lineage needs DataHub; `cascade setup --demo` is offline.
"""


def emit_install_notice() -> None:
    sys.stderr.write(NOTICE)
    sys.stderr.flush()
    try:
        with open("/dev/tty", "w", encoding="utf-8") as tty:
            tty.write(NOTICE)
            tty.flush()
    except OSError:
        pass
