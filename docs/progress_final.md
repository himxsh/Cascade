# Cascade — Progress (final plan)

**Last updated:** 2026-08-09  
**Tracking:** [final_plan.md](./final_plan.md)  
**Current phase:** Phase 6 — Deepen DataHub / OSS (optional) / Phase 7 submit  
**Overall:** Phases 0–5 done. Core production loop hardened.

Original hackathon MVP progress stays in [progress.md](./progress.md). This file tracks only the production loop.

---

## Status legend

| Symbol | Meaning |
|--------|---------|
| `[ ]` | Not started |
| `[~]` | In progress |
| `[x]` | Done |
| `[-]` | Cut / deferred |

---

## Phase 0 — Reachable DataHub + secrets

| Item | Status | Notes |
|------|--------|-------|
| `.env.example` + README secrets table | [x] | Incl. `OPENAI_API_KEY`, write-back warning |
| Quickstart Cloud + local notes | [x] | `demo/datahub-quickstart.md` Option A/B |
| `gms-smoke.yml` | [x] | Skips when secrets unset |
| Local Docker quickstart GMS | [x] | `datahub docker quickstart --arch m1` (v1.7.0) |
| Seed demo graph on GMS | [x] | Seeded via Python 3.11 venv (`acryl-datahub`) |
| Laptop health + seed URN verify | [x] | `/health` + datasets/ML + lineage via `searchAcrossLineage` (DataHub 1.7) |
| Actions health verify | [-] | N/A while GMS is localhost-only |

**Exit:** GMS healthy on laptop; seed entities visible in UI (http://localhost:9002).

---

## Phase 1 — Honest DataHub read + write

| Item | Status | Notes |
|------|--------|-------|
| Replace `cascadeStub` with real aspects | [x] | `globalTags` + editable desc + institutionalMemory via SDK |
| Soft-import `acryl-datahub` / `[writeback]` extra | [x] | `pyproject.toml` optional dep |
| Live ML from GMS when present | [x] | Else fixture + stderr notice |
| `generate` / `apply --source` | [x] | Same `resolve_catalog` as impact/demo |
| Aspect shape unit tests | [x] | `tests/test_apply.py` |
| Live UI verify tags/docs | [x] | Tags + institutional memory + description visible; migrated desc fixed |

**Exit:** Live write-back visible on source dataset + ML model in DataHub UI.

---

## Phase 2 — LLM-primary agent

| Item | Status | Notes |
|------|--------|-------|
| LLM owns strategy + SQL when keyed | [x] | Deterministic fallback on timeout/parse/schema-gate |
| Schema gate hard fail | [x] | Rejects invented columns → fallback |
| Rationale in report/comment/DataHub | [x] | LLM rationale used when agent=llm |
| Structured LLM logging | [x] | stderr: model, latency_ms, fallback reason |
| Action supplies LLM secret | [x] | `cascade.yml` + README cost/latency note |

---

## Phase 3 — Action on real PR diff

| Item | Status | Notes |
|------|--------|-------|
| Workflow off hardcoded example diff | [x] | `pr-impact` uses PR `git diff`; `fixture-ci` keeps golden file |
| Diff from PR base…head | [x] | `*.sql` / `models/` / `schema.yml` filtered in Action |
| URN config mapping | [x] | `.cascade/config.json` + `CASCADE_SOURCE_URN` / `--urn` |
| Live impact + comment | [x] | `SOURCE=live` when GMS secret set; else `auto`→fixture + comment |

---

## Phase 4 — Automatic remediation PR

| Item | Status | Notes |
|------|--------|-------|
| Git Data API branch/commit/PR | [x] | `commit_files_to_branch` + open/update; gated by `CASCADE_OPEN_DOWNSTREAM_PR` |
| Idempotent remediations branch | [x] | `cascade/remediation/{upstream_pr}` |
| Reviewers from owners | [x] | Best-effort request; invalid logins ignored |
| `mark_migrated` on merge | [x] | `cascade-migrated.yml` on remediation PR merge |

---

## Phase 5 — Production hardening

| Item | Status | Notes |
|------|--------|-------|
| dry-run vs apply / env protection | [x] | `--mode dry-run\|apply`; document GH Environment approval |
| Policy status check | [x] | `cascade/policy.py` + `--require-policy` / `cascade policy` |
| Idempotent comments / write-backs | [x] | Edit prior Cascade comment; remediation branch upsert |
| Run audit dir | [x] | `cascade/runs/<id>/` (gitignored) |
| Eval suite expansion | [-] | Existing golden kept; dialects deferred |
| Observability | [x] | `GITHUB_STEP_SUMMARY` + apply_summary policy block |

---

## Phase 6 — Deepen DataHub / OSS

| Item | Status | Notes |
|------|--------|-------|
| Optional MCP / Agent Context Kit | [ ] | |
| Column-level lineage when available | [ ] | |
| Upstream Skill PR | [ ] | In-repo draft only today |

---

## Phase 7 — Product surface + submit assets

| Item | Status | Notes |
|------|--------|-------|
| UI live/auto against GMS | [~] | UI exists; fixture default |
| Deploy UI (Vercel) + server secrets | [~] | Deployed; live secrets optional |
| Live-loop demo video | [ ] | |
| Devpost / survey / Apache About | [ ] | |
| Sync this file to match reality | [~] | |

---

## Definition of done (from final plan)

- [x] Action runs on the PR’s own schema/SQL diff
- [~] Catalog read is live GMS (ML from GMS when available) — laptop yes; Actions when HTTPS GMS secret set
- [x] LLM primary when keyed; deterministic fallback only
- [x] Schema gate rejects invented columns
- [x] Source PR blast-radius comment (pr-impact + fixture-ci)
- [x] Downstream remediation PR auto create/update (`CASCADE_OPEN_DOWNSTREAM_PR`)
- [x] Real DataHub write-back aspects (verified on laptop UI)
- [x] Merge flips pending → `cascade:migrated` (`cascade-migrated.yml`)
- [x] Dry-run default; live gated by secrets
- [x] Idempotent re-runs (same upstream PR → same remediation branch/PR; comment upsert)
- [x] CI eval stays green (fixture)
- [x] README secrets / URN mapping / Production section

---

## Decisions log (final plan)

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-08-09 | Track production work in `progress_final.md` | Keep MVP [progress.md](./progress.md) unchanged |
| 2026-08-09 | Use local Docker quickstart for live GMS (not Cloud) | Laptop demos; Actions stay fixture until HTTPS GMS exists |
| 2026-08-09 | Live write-back = SDK emitter (not `cascadeStub`) | Visible tags/docs in DataHub UI |
| 2026-08-09 | URN mapping = `.cascade/config.json` (not YAML) | Stdlib JSON; no new PyYAML dep |

---

## Blockers

- Actions cannot reach localhost GMS — `pr-impact` uses `--source live` only when `DATAHUB_GMS_URL` secret is an HTTPS GMS; otherwise auto→fixture.

---

## Session notes

### 2026-08-09 — final_plan kickoff (Phase 0–1 code)

- Phase 0 docs/smoke: `.env.example`, README secrets, quickstart notes, `gms-smoke.yml`.
- Phase 1 write: real aspects via soft-imported SDK; dry-run includes `aspects` plan (no `cascadeStub`).
- Phase 1 read/CLI: live ML probe + fixture notice; `generate`/`apply` take `--source`.
- Chose laptop Docker over DataHub Cloud for now.
- Lineage client updated to `searchAcrossLineage` for DataHub 1.7.
- Live write-back verified in UI; `mark_migrated` now refreshes description.
- Phase 2: LLM-primary agent + stderr logging + Action env + tests.

### 2026-08-09 — Phase 3

- `.cascade/config.json` path→URN; `cascade/config.py` + CLI optional `--urn`.
- `pr-impact` job: real `git diff` base…head → `load_changes` / patch parser; separate `fixture-ci`.
- dotenv auto-load kept for laptop CLI/API.
- Merged as PR #15.

### 2026-08-09 — Phase 4

- Git Data API: branch `cascade/remediation/{pr}` + commit rewritten SQL + open/update PR.
- `CASCADE_OPEN_DOWNSTREAM_PR=1` happy path; `CASCADE_DOWNSTREAM_HEAD` optional override.
- Source comment + DataHub plan link remediation URL; `cascade-migrated.yml` on merge.
- Merged as PR #16.

### 2026-08-09 — Phase 5

- `--mode dry-run|apply`; policy gate for high-without-remediation; comment upsert; `cascade/runs/<id>/`; Action step summary.
- Skipped: dialect profiles, large golden expansion (YAGNI for now).

### 2026-08-09 — next

- Phase 6/7 optional: MCP deepen, Skill PR, video/Devpost.
