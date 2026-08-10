# Cascade — Extension plan (make it usable on other repos)

**Goal:** Turn Cascade from “works in this monorepo / demo” into something a team can drop onto **their own** dbt/SQL repo.

Related: [final_plan.md](./final_plan.md) (production loop — mostly done), [progress_final.md](./progress_final.md).

This file is **not** the core loop. The core loop already exists. These are the packaging, config, and adoption pieces still missing.

---

## Current state (honest)

| What works today | What doesn’t for strangers |
|------------------|----------------------------|
| Full loop in *this* repo | Workflow assumes `pip install -e .` (Cascade *is* the repo) |
| `.cascade/config.json` path → URN | Config is demo URNs (`analytics.raw_orders`) |
| Live GMS on laptop | GitHub Actions need HTTPS GMS; localhost won’t work for them either |
| Remediation PR + PR comment | URN → SQL file mapping is naive (`models/<last_urn_segment>.sql`) |
| Fixture fallback for CI | No copy-paste Action / install story for other repos |
| README for Cascade itself | No “bring your own repo” guide |

**Adoption cost that never goes away:** their DataHub must already have lineage for the tables Cascade will touch. Cascade does not invent the warehouse graph.

---

## What “usable on your repo” means

A stranger should be able to:

1. Install Cascade as a **tool** (not clone this whole project as their app).
2. Add a small **config** mapping their paths → their DataHub URNs.
3. Add one **GitHub Action** workflow.
4. Set a few **secrets**.
5. Open a breaking SQL PR and get: blast-radius comment + remediation PR (+ optional DataHub tags).

---

## Feature backlog

Do in order. Later items assume earlier ones exist.

### E1 — Installable package

**Why:** Other repos can’t `pip install -e .` on Cascade’s source tree.

**Add:**

- Clear install path, e.g. `pip install "cascade-agent @ git+https://github.com/himxsh/Cascade.git"` (PyPI later if you care).
- Pin a version / tag for Actions (`@v0.1.0`), not floating `main`.
- Keep console script `cascade` (already in `pyproject.toml`).
- Optional extras stay optional: `[writeback]`, `[ui]` — consumers shouldn’t pull FastAPI/Vite deps for CI.

**Done when:** Empty repo can `pip install …` and run `cascade --help`.

---

### E2 — Copy-paste / reusable GitHub Action

**Why:** Today `.github/workflows/cascade.yml` is Cascade’s own CI (fixture job + demo paths).

**Add:**

1. **Template workflow** under `examples/github-action/cascade.yml` that:
   - Installs Cascade from git/PyPI (not `pip install -e .`)
   - Diffs PR `*.sql` / `models/` / `schema.yml`
   - Runs `cascade impact` → `cascade apply`
   - Does **not** depend on `examples/diffs/` or this repo’s package layout
2. **Short setup doc** in that folder (secrets table + minimal `.cascade/config.json` example).
3. Later (optional): real reusable Action (`uses: himxsh/cascade-action@v1`) wrapping the same steps.

**Done when:** A fork of a toy dbt repo can add the template + secrets and get a PR comment without vendoring Cascade source.

---

### E3 — Bring-your-own config (first-class)

**Why:** Config exists but is demo-shaped; mapping rules need to be documented and slightly stronger.

**Add / tighten:**

| Knob | Purpose |
|------|---------|
| `.cascade/config.json` | `default_urn`, `models_dir`, `mappings[]` (path prefix → URN) |
| `CASCADE_SOURCE_URN` | Override when mapping misses |
| Optional `owners_map.yaml` | DataHub corpUser → GitHub login for reviewer requests |
| Optional write-back flag | `CASCADE_WRITEBACK=1` only on trusted jobs |

**Improve file resolution:**

- Today: URN `…,analytics.fct_orders,PROD` → `models_dir/fct_orders.sql`
- Needed: allow explicit `urn → path` in config, or dbt-style nested paths (`models/marts/fct_orders.sql`), so real repos aren’t forced into flat filenames.

**Done when:** README “BYO repo” section shows one real-looking config (not demo URNs only), and a nested model path can be remapped without renaming files.

---

### E4 — Consumer README / “Bring your own repo”

**Why:** Judges and adopters need a 5-minute path that isn’t “run our demo.”

**Add a short guide (can live in README or `docs/byo.md`) covering:**

1. Prerequisites: DataHub with lineage for your tables; GitHub repo with SQL/dbt.
2. Install Cascade in CI.
3. Add `.cascade/config.json`.
4. Add workflow from `examples/github-action/`.
5. Set secrets: `DATAHUB_GMS_URL`, `DATAHUB_TOKEN`, optional `LLM_API_KEY`.
6. Modes: dry-run vs apply; when write-back is safe.
7. Failure modes: no GMS → no live lineage; no LLM key → deterministic rewrite; schema gate rejects bad SQL.

**Done when:** Someone who never opened this monorepo can follow the guide without reading `final_plan.md`.

---

### E5 — Hardening for multi-repo use

**Why:** Demo assumptions break outside Cascade.

| Item | Notes |
|------|--------|
| Skip remediation branches | Already skips `cascade/remediation/*` — keep that contract documented |
| Permissions | Workflow needs `contents: write` + `pull-requests: write` for auto PR |
| Idempotency | Same upstream PR → same remediation branch (already true) — document it |
| Policy check | Optional `--require-policy` for “high severity needs open remediation PR” |
| Dialect honesty | Still SQL/dbt-first; document “not every warehouse dialect” |
| Secrets never in UI | Vercel/UI path must keep tokens server-side only (already the intent) |

**Done when:** Failure modes and permissions are in the BYO doc; no silent demo fallbacks in *their* Action when they asked for `live`.

---

### E6 — Optional product extras (only if E1–E4 are green)

| Extra | Value | Skip if… |
|-------|--------|----------|
| PyPI release + versioning | One-line install | Git install is enough for hackathon |
| Reusable Action marketplace entry | Discoverability | Template YAML is enough |
| Column-level lineage | Better blast radius | GMS doesn’t have it |
| MCP / Agent Context Kit | Less custom GraphQL | Stdlib client is fine |
| Cross-repo remediation | Monorepo-only is enough for most | Out of MVP |
| Multi-dialect profiles | Snowflake / BQ / Postgres | Core loop unstable |
| Upstream DataHub Skill PR | OSS bonus | Timeboxed |

---

## Suggested ship order

```text
E1 install from git
  → E2 template Action + example config
    → E3 nested path / urn→file mapping
      → E4 BYO docs
        → E5 document permissions + failure modes
          → E6 only if time / demand
```

Do **not** block on E6 for “usable.”

---

## Minimal “hello other repo” checklist

- [ ] `pip install` Cascade without cloning into the consumer repo
- [ ] Template workflow with no `examples/diffs/` dependency
- [ ] Sample `.cascade/config.json` using placeholder URNs + comments
- [ ] Secrets table for consumers
- [ ] BYO section: prerequisites → config → Action → first PR
- [ ] Document: DataHub lineage is required; Cascade won’t invent it
- [ ] Optional: `urn → path` overrides for non-flat dbt layouts

---

## Explicit non-goals (still)

- Multi-tenant SaaS “sign up and connect GitHub”
- Autonomous merge without human review
- Replacing DataHub UI
- Supporting every BI tool / every SQL dialect on day one
- Hosting customers’ DataHub for them

---

## One-line summary

**Core agent is done. Usability = package it, give a template Action, let them map their paths to their URNs, and tell them they need DataHub lineage.**
