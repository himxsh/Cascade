"""cascade init / setup / doctor — consumer repo bootstrap. Stdlib only."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from cascade import __version__
from cascade.config import CascadeConfig, _urn_stem, load_config, resolve_rewrite_mode
from cascade.datahub_live import health_check, search_dataset_urns
from cascade.dotenv_load import load_dotenv

_TEMPLATES = Path(__file__).resolve().parent / "templates"

_SKIP_DIRS = frozenset({
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".tox",
    "dist",
    "build",
    "artifacts",
    ".cascade",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
})

_PLACEHOLDER_MARKERS = ("YOUR_TABLE", "YOUR_DB")
_MAX_SQL_STEMS = 20

# Same graph as demo/fixtures/demo_graph.json — used offline by `cascade setup --demo`.
_DEMO_URNS = {
    "raw_orders": "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)",
    "stg_orders": "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.stg_orders,PROD)",
    "fct_orders": "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.fct_orders,PROD)",
    "features_orders": "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.features_orders,PROD)",
}

_NEXT_STEPS = [
    "Next:",
    "  Commit these files.",
    "  Open a PR that touches SQL, models, or schema.yml — Cascade will comment.",
    "  Stacked PRs need /cascade stack later.",
]

_GH_SECRET_BLOCK = (
    "printf '%s' \"$DATAHUB_GMS_URL\" | gh secret set DATAHUB_GMS_URL\n"
    "printf '%s' \"$DATAHUB_TOKEN\" | gh secret set DATAHUB_TOKEN"
)


def _copy_template(name: str, dest: Path, force: bool) -> str:
    src = _TEMPLATES / name
    if dest.exists() and not force:
        return f"skip {dest} (exists)"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src.read_text())
    return f"wrote {dest}"


def run_init(
    root: Path | None = None,
    *,
    force: bool = False,
    include_hints: bool = True,
) -> list[str]:
    root = (root or Path.cwd()).resolve()
    notes = [
        _copy_template("config.json", root / ".cascade" / "config.json", force),
        _copy_template("env.example", root / ".env.example", force),
        _copy_template(
            "github-cascade.yml",
            root / ".github" / "workflows" / "cascade.yml",
            force,
        ),
    ]
    if include_hints:
        notes.extend(
            [
                "Next: copy .env.example → .env, fill DATAHUB_GMS_URL, map URNs in .cascade/config.json",
                "Add the same DataHub keys as GitHub Actions secrets. Do not commit .env.",
            ]
        )
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        text = gitignore.read_text()
        existing = {ln.strip() for ln in text.splitlines()}
        if ".env" not in existing:
            gitignore.write_text(text.rstrip() + "\n.env\n")
            notes.append("appended .env to .gitignore")
    return notes


def run_doctor(root: Path | None = None) -> tuple[list[str], int]:
    root = (root or Path.cwd()).resolve()
    lines: list[str] = [f"cascade {__version__}"]
    rc = 0

    py = sys.version_info
    if py >= (3, 11):
        lines.append(f"ok   python {py.major}.{py.minor}.{py.micro}")
    else:
        lines.append(f"fail python {py.major}.{py.minor} (need >= 3.11)")
        rc = 1

    cfg_path = root / ".cascade" / "config.json"
    if not cfg_path.is_file():
        lines.append("fail config missing (.cascade/config.json) — run cascade setup")
        rc = 1
        cfg = load_config(None)
    else:
        try:
            cfg = load_config(cfg_path)
            lines.append(f"ok   config {cfg_path}")
        except json.JSONDecodeError as e:
            lines.append(f"fail config JSON: {e}")
            rc = 1
            cfg = CascadeConfig()

    if cfg.default_urn or cfg.mappings or os.environ.get("CASCADE_SOURCE_URN"):
        lines.append("ok   URN mapping present")
    else:
        lines.append("fail no default_urn / mappings / CASCADE_SOURCE_URN")
        rc = 1

    gms = os.environ.get("DATAHUB_GMS_URL", "").strip()
    if not gms:
        lines.append("warn DATAHUB_GMS_URL unset (live source will fail)")
    elif health_check(gms):
        lines.append(f"ok   GMS {gms}")
    else:
        lines.append(f"fail GMS unreachable {gms}")
        rc = 1

    mode = resolve_rewrite_mode(config=cfg)
    lines.append(f"ok   rewrite mode {mode}")
    if mode == "llm":
        key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        model = os.environ.get("LLM_MODEL") or cfg.rewrite_model
        if key:
            lines.append("ok   LLM key set")
        else:
            lines.append("fail CASCADE_MODE=llm but no LLM_API_KEY")
            rc = 1
        if model:
            lines.append(f"ok   LLM_MODEL {model}")
        else:
            lines.append("fail CASCADE_MODE=llm requires LLM_MODEL")
            rc = 1

    return lines, rc


def _is_git_repo(root: Path) -> bool:
    git = root / ".git"
    if git.is_dir() or git.is_file():
        return True
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _scan_sql_signals(root: Path) -> tuple[list[Path], bool]:
    sql_files: list[Path] = []
    has_other = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        if Path(dirpath).name == "models" or rel_dir == "models" or rel_dir.endswith("/models"):
            has_other = True
        for name in filenames:
            path = Path(dirpath) / name
            if name.endswith(".sql"):
                sql_files.append(path)
            elif name in ("schema.yml", "schema.yaml"):
                has_other = True
    sql_files.sort()
    return sql_files, has_other or (root / "models").is_dir()


def _can_prompt(non_interactive: bool, prompt: Callable[[str], str] | None) -> bool:
    if non_interactive:
        return False
    if prompt is not None:
        return True
    return bool(sys.stdin.isatty())


def _is_placeholder_urn(urn: str) -> bool:
    return any(marker in urn for marker in _PLACEHOLDER_MARKERS)


def _apply_config_suggestions(
    config_path: Path,
    *,
    mappings: list[tuple[str, str]],
    default_urn: str | None,
    replace_placeholders: bool,
) -> None:
    if not config_path.is_file():
        return
    data = json.loads(config_path.read_text())
    raw = data.get("mappings") or []
    items: list[dict[str, str]] = []
    if isinstance(raw, dict):
        items = [{"path": str(p), "urn": str(u)} for p, u in raw.items()]
    else:
        for item in raw:
            if isinstance(item, dict) and item.get("path") and item.get("urn"):
                items.append({"path": str(item["path"]), "urn": str(item["urn"])})
    if replace_placeholders or mappings:
        items = [m for m in items if not _is_placeholder_urn(m["urn"])]
    seen_paths = {m["path"] for m in items}
    for path, urn in mappings:
        if path in seen_paths:
            continue
        items.append({"path": path, "urn": urn})
        seen_paths.add(path)
    if default_urn and (
        replace_placeholders or _is_placeholder_urn(str(data.get("default_urn") or ""))
    ):
        data["default_urn"] = default_urn
    data["mappings"] = items
    config_path.write_text(json.dumps(data, indent=2) + "\n")


def _match_stem(stem: str, urns: list[str]) -> list[str]:
    want = stem.lower()
    return [u for u in urns if (_urn_stem(u) or "").lower() == want]


def _suggest_from_files(
    root: Path,
    sql_files: list[Path],
    lookup: Callable[[str], list[str]],
) -> tuple[list[str], list[tuple[str, str]], str | None]:
    notes: list[str] = []
    mappings: list[tuple[str, str]] = []
    unmatched: list[str] = []
    scanned = sql_files[:_MAX_SQL_STEMS]
    if len(sql_files) > _MAX_SQL_STEMS:
        notes.append(f"warn scanned {_MAX_SQL_STEMS} SQL files (skipped {len(sql_files) - _MAX_SQL_STEMS})")
    for path in scanned:
        stem = path.stem
        rel = path.relative_to(root).as_posix()
        if len(stem) < 2:
            unmatched.append(rel)
            continue
        exact = _match_stem(stem, lookup(stem))
        if len(exact) == 1:
            mappings.append((rel, exact[0]))
            notes.append(f"matched {rel}")
        elif len(exact) > 1:
            notes.append(f"ambiguous {rel} ({len(exact)} catalog hits)")
            unmatched.append(rel)
        else:
            unmatched.append(rel)
    if unmatched:
        notes.append("unmapped: " + ", ".join(unmatched))
        notes.append("TODO: set path→URN mappings in .cascade/config.json")
    default_urn = mappings[0][1] if mappings else None
    return notes, mappings, default_urn


def _demo_lookup(stem: str) -> list[str]:
    urn = _DEMO_URNS.get(stem.lower())
    return [urn] if urn else []


def _live_lookup(gms_url: str, token: str | None) -> Callable[[str], list[str]]:
    # ponytail: searchAcrossEntities per SQL stem (count=10), not a full catalog dump
    def lookup(stem: str) -> list[str]:
        return search_dataset_urns(stem, gms_url=gms_url, token=token, count=10)

    return lookup


def _gh_secret_help() -> list[str]:
    return [
        "Set Actions secrets (values stay in your shell):",
        _GH_SECRET_BLOCK,
    ]


def _try_set_gh_secrets(root: Path, url: str, token: str | None) -> list[str]:
    if not shutil.which("gh"):
        return _gh_secret_help()
    try:
        auth = subprocess.run(
            ["gh", "auth", "status"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _gh_secret_help()
    if auth.returncode != 0:
        return _gh_secret_help()

    notes: list[str] = []
    pairs = [("DATAHUB_GMS_URL", url)]
    if token:
        pairs.append(("DATAHUB_TOKEN", token))
    for name, value in pairs:
        try:
            proc = subprocess.run(
                ["gh", "secret", "set", name],
                cwd=root,
                input=value,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            return notes + _gh_secret_help()
        if proc.returncode != 0:
            return notes + _gh_secret_help()
        notes.append(f"set GitHub secret {name}")
    return notes


def run_setup(
    root: Path | None = None,
    *,
    demo: bool = False,
    non_interactive: bool = False,
    skip_secrets: bool = False,
    prompt: Callable[[str], str] | None = None,
) -> tuple[list[str], int]:
    root = (root or Path.cwd()).resolve()
    load_dotenv(root / ".env")
    lines: list[str] = []
    ask = prompt or input

    if not _is_git_repo(root):
        return [f"cascade setup: not a git repository ({root})"], 1

    sql_files, has_other = _scan_sql_signals(root)
    if not sql_files and not has_other:
        lines.append("warn no *.sql, models/, or schema.yml in this repo")
        if not _can_prompt(non_interactive, prompt):
            lines.append(
                "cascade setup: no SQL/dbt files; re-run without --non-interactive to continue"
            )
            return lines, 1
        ans = ask("Write scaffolding anyway? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            lines.append("cascade setup: aborted")
            return lines, 1

    lines.extend(run_init(root, include_hints=False))
    config_path = root / ".cascade" / "config.json"

    if demo:
        lines.append(
            "demo: skipped live DataHub. PR comments about real tables still need GMS."
        )
        notes, mappings, default_urn = _suggest_from_files(root, sql_files, _demo_lookup)
        lines.extend(notes)
        _apply_config_suggestions(
            config_path,
            mappings=mappings,
            default_urn=default_urn or _DEMO_URNS["raw_orders"],
            replace_placeholders=True,
        )
    else:
        url = os.environ.get("DATAHUB_GMS_URL", "").strip()
        token = os.environ.get("DATAHUB_TOKEN", "").strip() or None
        if not url:
            if not _can_prompt(non_interactive, prompt):
                lines.append(
                    "cascade setup: DATAHUB_GMS_URL is unset (export it, or use --demo)"
                )
                return lines, 1
            url = ask("DataHub GMS URL: ").strip()
            if not url:
                lines.append("cascade setup: DATAHUB_GMS_URL is required (or use --demo)")
                return lines, 1
            os.environ["DATAHUB_GMS_URL"] = url
        if not health_check(url):
            lines.append("cascade setup: DataHub unreachable")
            return lines, 1
        lines.append("ok   DataHub reachable")
        notes, mappings, default_urn = _suggest_from_files(
            root, sql_files, _live_lookup(url, token)
        )
        lines.extend(notes)
        _apply_config_suggestions(
            config_path,
            mappings=mappings,
            default_urn=default_urn,
            replace_placeholders=bool(mappings),
        )
        if not skip_secrets:
            lines.extend(_try_set_gh_secrets(root, url, token))

    doc_lines, doc_rc = run_doctor(root)
    lines.extend(doc_lines)
    lines.append("")
    lines.extend(_NEXT_STEPS)
    return lines, doc_rc
