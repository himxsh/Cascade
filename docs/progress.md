# Cascade — Progress

**Last updated:** 2026-07-23  
**Current phase:** Phase 1 — Read path (fixture-backed impact CLI checkpoint)  
**Overall:** ~35%

---

## Status legend

| Symbol | Meaning |
|--------|---------|
| `[ ]` | Not started |
| `[~]` | In progress |
| `[x]` | Done |
| `[-]` | Cut / deferred |

---

## Phase 0 — Scaffold

| Item | Status | Notes |
|------|--------|-------|
| `docs/plan.md` | [x] | Initial plan |
| `docs/spec.md` | [x] | Initial spec |
| `docs/progress.md` | [x] | This file |
| `docs/architecture.drawio` | [x] | Initial architecture |
| Repo root + Apache 2.0 LICENSE | [x] | scaffold PR |
| README skeleton | [x] | scaffold PR |
| Project package layout (`cascade/`, `tests/`, `examples/`, `demo/`) | [x] | scaffold PR |
| DataHub quickstart notes / compose | [x] | demo/datahub-quickstart.md + health-check script |
| Seed script for demo lineage | [x] | `demo/fixtures/demo_graph.json` + `demo/seed_demo_graph.py` + `demo/check_demo_graph.py` |

## Phase 1 — Read path

| Item | Status | Notes |
|------|--------|-------|
| MCP / Agent Context Kit wiring | [~] | fixture first; live MCP next |
| `cascade impact` CLI | [x] | argparse subcommand, fixture-backed |
| ImpactReport JSON dataclass + to_dict | [x] | `cascade/models.py` – stdlib dataclasses |
| Fixture catalog (lineage BFS, schema, owners, ML impact) | [x] | `cascade/datahub_fixture.py` |
| `build_impact_report` with severity heuristic | [x] | `cascade/impact.py` |
| Self-check against seeded graph | [x] | `tests/test_impact_fixture.py` (stdlib unittest) |
| Sample diff (raw_orders rename user_id) | [x] | `examples/diffs/raw_orders_rename_user_id.json` |

## Phase 2 — Reason + generate path

| Item | Status | Notes |
|------|--------|-------|
| Diff / change classifier (rename heuristic-first) | [ ] | |
| **Agentic strategy selection + rationale** (LLM) | [ ] | The "it's an agent" bit |
| **Primary generator: `rewrite` downstream SQL** | [ ] | Headline artifact, not shim-only |
| Fallbacks: `adapter_view` / `deprecate` | [ ] | |
| Schema gate (no invented columns) | [ ] | Hard fail |
| Thin ML: mark `mlModel` retrain-suggested | [ ] | feature→model edge |
| Golden-diff eval in CI | [ ] | Proves end-to-end |
| `examples/` incl. headline rewritten PR diff | [ ] | |

## Phase 3 — Act + write-back

| Item | Status | Notes |
|------|--------|-------|
| GitHub Action | [ ] | |
| PR comment with blast radius **+ rationale** | [ ] | |
| Downstream PR open/update (rewritten files) | [ ] | |
| DataHub write-back (doc/tags/description) | [ ] | |
| ML write-back (retrain tag + model doc) | [ ] | |
| Migrated lifecycle on merge | [ ] | |

## Phase 4 — Polish + submit

| Item | Status | Notes |
|------|--------|-------|
| Demo video ≤3 min (fixture path) | [ ] | |
| Devpost submission | [ ] | |
| DataHub Skill PR (before deadline) | [ ] | Named bonus — now MVP |
| Feedback survey opt-in | [ ] | |

## Full plan (Phases 5–10) — only after MVP DoD

See [plan.md § Full plan](./plan.md). Do not start until Phase 4 demo is green.

| Phase | Theme | Status |
|-------|--------|--------|
| 5 | Stronger agent (severity, contracts, idempotent Action) | [ ] |
| 6 | Cross-repo + multi-artifact generators | [ ] |
| 7 | Deepen ML (generated retrain artifact; thin ver. in MVP) | [ ] |
| 8 | Runtime drift / MetadataChangeLog loop | [ ] |
| 9 | Deepen OSS beyond our Skill (base Skill in MVP) | [ ] |
| 10 | Productization (UI, policy check, evals) | [ ] |

**If extra week only:** 5 → 7 → 9 → 6 → 8 → 10.

---

## Decisions log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-23 | Build **Cascade** (schema cascade remediator) | Hits read + act + write-back + mergeable artifacts; avoids rebuilding Analytics Agent |
| 2026-07-23 | Target Grand Prize via Challenges 1+2 | Strongest judging fit for DataHub agent brief |
| 2026-07-23 | MVP generators = dbt/SQL only | Ponytail: ship one dialect well |
| 2026-07-23 | Primary strategy = **`rewrite`**, shim is fallback | Keeps "code a team would merge" honest; avoids shim-only trap (review fix) |
| 2026-07-23 | LLM owns strategy + rewrite; deterministic parts = tools | Makes it a real *agent* for The Agent Hackathon (review fix) |
| 2026-07-23 | Rename detection heuristic-first, annotation confirms | Demo shows agent reasoning, not a required hint (review fix) |
| 2026-07-23 | Thin ML edge + Skill PR + golden-diff eval moved **into MVP** | 3-category coverage, named OSS bonus, "actually works" score (review fix) |
| 2026-07-23 | Reframe problem: *uncoordinated* not *silent* | Avoids occupied silent-failure lane; matches what MVP catches (review fix) |
| 2026-07-23 | Phase 1 ships fixture-backed impact before live MCP | Spec decision #7 + demo resilience |

---

## Blockers

_None yet._

---

## Session notes

### 2026-07-23

- Chose Cascade over chat/T2SQL and over pure ML silent-failure agents (crowded / partially claimed).
- Created `Cascade/docs` with plan, spec, progress, architecture.
- Ran a grand-prize gap review; applied 4 fixes to plan + spec: (1) rewrite-first codegen, (2) visible agentic reasoning, (3) thin ML + eval + Skill PR into MVP, (4) reframed "silent" → "uncoordinated".
- Next: scaffold repo + seed DataHub graph (now incl. a feature→model edge).

### 2026-07-23 (late)

- Phase 0 scaffold checkpoint: LICENSE, README, package layout, pyproject.toml, .env.example, cascade/ package stub, tests/ version check, examples/ + demo/ READMEs.
- `pip install -e .` and console script `cascade` verified clean.

### 2026-07-23 (night)

- DataHub quickstart docs: `demo/datahub-quickstart.md` with prerequisites, install, run, health check, env mapping, offline/fixture note.
- Added `demo/scripts/check_datahub.sh` — GMS health check script.
- Wired README Setup with link to quickstart doc.
- Updated progress.md with checkpoint status.
- Next: seed script for demo lineage graph.

### 2026-07-23 (seed checkpoint)

- Created `demo/fixtures/demo_graph.json` — 4 datasets (raw/stg/fct/features), 3 lineage edges, 1 ML feature, 1 ML model, owners (alice/bob), schema fields including `user_id` on raw + fct.
- Created `demo/seed_demo_graph.py` — reads fixture, builds MCPs for datasets (properties + schema + ownership + upstreamLineage), ML features, and ML models. Dry-run by default, `--apply` emits via `DatahubRestEmitter`.
- Created `demo/check_demo_graph.py` — validates fixture without live DataHub: checks URNs, lineage path, ML edge, `user_id` fields, owners. Exits 0 on pass.
- Created `demo/requirements.txt` — `acryl-datahub` (demo tooling, not cascade hard dep).
- Updated progress.md: Overall ~20%, Phase 0 scaffold items all [x], noted pending live DataHub verify.

### 2026-07-23 (Phase 1 checkpoint — fixture-backed impact CLI)

- `cascade/models.py` — ImpactReport + Change + DownstreamNode + MLImpact + Remediation dataclasses, `to_dict()`.
- `cascade/datahub_fixture.py` — fixture loader (demo_graph.json), BFS downstream lineage, schema field lookup, owner lookup, ML impact (feature→model retrain-suggested).
- `cascade/impact.py` — `build_impact_report()` with simple severity heuristic: high if breaking change + downstream exists.
- `cascade/cli.py` — `cascade impact --urn --diff [--fixture]` subcommand, prints JSON report to stdout.
- `examples/diffs/raw_orders_rename_user_id.json` — sample FIELD_RENAMED change for demo scenario.
- `tests/test_impact_fixture.py` — 6 test methods covering downstream BFS, owners, severity, ml_impact, JSON serialization.
- No new deps. No live MCP client. No diff parser. No remediations/rewrite.
