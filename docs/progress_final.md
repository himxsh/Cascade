# Cascade — Progress (final plan)

**Last updated:** 2026-08-09  
**Tracking:** [final_plan.md](./final_plan.md)  
**Current phase:** Phase 4 — Automatic remediation PR  
**Overall:** Phases 0–3 done (local GMS; PR Action uses real diff + fixture-ci). Next: auto remediation PR.

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
| Git Data API branch/commit/PR | [ ] | Still needs `CASCADE_DOWNSTREAM_HEAD` |
| Idempotent remediations branch | [ ] | |
| Reviewers from owners | [~] | Dry-run reviewers work |
| `mark_migrated` on merge | [ ] | |

---

## Phase 5 — Production hardening

| Item | Status | Notes |
|------|--------|-------|
| dry-run vs apply / env protection | [ ] | |
| Policy status check | [ ] | |
| Idempotent comments / write-backs | [ ] | |
| Run audit dir | [ ] | |
| Eval suite expansion | [ ] | |
| Observability | [ ] | |

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
- [ ] Downstream remediation PR auto create/update
- [x] Real DataHub write-back aspects (verified on laptop UI)
- [ ] Merge flips pending → `cascade:migrated`
- [x] Dry-run default; live gated by secrets
- [ ] Idempotent re-runs
- [x] CI eval stays green (fixture)
- [x] README secrets / URN mapping (`.cascade/config.json`)

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

### 2026-08-09 — next

- Phase 4: automatic remediation PR (Git Data API; drop happy-path `CASCADE_DOWNSTREAM_HEAD`).
