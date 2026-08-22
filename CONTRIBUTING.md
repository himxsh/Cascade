# Contributing to Cascade

Thanks for wanting to help. Cascade is a Python CLI and GitHub Action: it reads DataHub lineage, rewrites downstream SQL, and opens a remediation PR. Keep changes small and correct.

By opening a pull request you agree that your contribution is licensed under [Apache-2.0](LICENSE), as described in section 5 of that license.

## Development setup

Python 3.11 or newer.

```bash
git clone https://github.com/himxsh/Cascade.git
cd Cascade
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cascade --help
```

Optional extras: `[ui]` for the local playground, `[writeback]` for the DataHub ingest SDK.

Copy `.env.example` to `.env` only if you are hitting a live GMS. Do not commit `.env`.

```bash
cascade doctor
```

`doctor` is useful for live DataHub work. Unit tests do not need it.

## Tests

CI runs this, and so should you before a PR:

```bash
python -m unittest discover -s tests -v
```

The default path is **fixture + deterministic rewrite**. Tests must stay green with no `DATAHUB_GMS_URL`, no GitHub token, and no LLM key.

If you change impact, rewrite, or apply behavior, update the golden artifacts under `tests/golden/` and `examples/rewritten/` in the same PR. Do not weaken a golden test to make a refactor pass.

## Project layout

| Path | Role |
| --- | --- |
| `cascade/` | Engine and CLI (`impact`, `generate`, `apply`, `policy`, `init`, `doctor`, `demo`) |
| `cascade/templates/` | Files `cascade init` writes into a consumer repo |
| `tests/` | Unit tests and golden-diff eval |
| `examples/` | Sample diffs, models, and the consumer Action template |
| `demo/fixtures/` | Offline catalog used by `--source fixture` |
| `.github/workflows/` | CI plus this repo’s Cascade workflows |
| `frontend/` / `api/` | Optional local UI — not the install path |

## What to change

Fix the shared function, not every caller. Prefer the standard library over a new dependency. The engine is meant to stay installable without FastAPI, Vite, or a warehouse driver.

Do not add:

- Warehouse credentials or connectors (Snowflake, Postgres, BigQuery, …)
- Autonomous merge of remediation PRs
- Fixture fallback on the **consumer** Action template (`examples/github-action/` stays `--source live` and fail-closed)
- Secrets, tokens, or live GMS URLs in tests, fixtures, or docs examples

Mark a deliberate shortcut with a `ponytail:` comment that names the ceiling and how to replace it.

## Pull requests

1. One concern per PR.
2. Describe *why*, not a file list.
3. Include a test or a golden update when behavior changes.
4. Leave `cascade demo --out artifacts/demo` working for the default rename example.
5. Do not set `CASCADE_WRITEBACK=1` in workflows that run on forks.

## Issues

Include the command you ran, `--source` (`fixture` / `live` / `auto`), whether `CASCADE_MODE` was `deterministic` or `llm`, and a redacted snippet of the diff or impact JSON. Strip tokens, GMS URLs with credentials, and warehouse passwords.

Security-sensitive reports (token leak, write-back against the wrong GMS, untrusted-diff prompt injection): do not paste secrets into a public issue. Open a private advisory on the GitHub repo if you can, or describe the issue without credentials.

## License

Apache License 2.0. See [LICENSE](LICENSE).
