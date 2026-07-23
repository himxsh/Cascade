# Cascade — Progress

**Last updated:** 2026-07-23  
**Current phase:** Phase 0 — Scaffold (docs only)  
**Overall:** 5%

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
| Repo root + Apache 2.0 LICENSE | [ ] | |
| README skeleton | [ ] | |
| Project package layout (`cascade/`, `tests/`, `examples/`, `demo/`) | [ ] | |
| DataHub quickstart notes / compose | [ ] | |
| Seed script for demo lineage | [ ] | |

## Phase 1 — Read path

| Item | Status | Notes |
|------|--------|-------|
| MCP / Agent Context Kit wiring | [ ] | |
| `cascade impact` CLI | [ ] | |
| ImpactReport JSON schema (incl. strategy + rationale + ml_impact) | [ ] | |
| Self-check against seeded graph | [ ] | |

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
