# Cascade — Build Plan

**Hackathon:** [Build with DataHub: The Agent Hackathon](https://datahub.devpost.com/)  
**Deadline:** Aug 10, 2026 @ 5:00pm EDT  
**Categories:** Agents That Do Real Work + Metadata-Aware Code Generation  
**Target:** Grand Prize ($6,000)

---

## Goal

Ship a working end-to-end demo: a PR that breaks a schema → Cascade reads DataHub lineage via MCP → an LLM **reasons** about a per-node remediation strategy → **rewrites the downstream model SQL** → opens coordinated PRs → tags the affected ML model for retrain → writes the decision trail back to DataHub.

Judges must be able to understand and (ideally) run this in under 10 minutes.

### Positioning (locked)

- **It's an agent, not a script.** The LLM owns strategy selection + SQL rewrite; parsing/lineage/GitHub are tools. Reasoning is *visible* in the demo. (spec §2.1)
- **Primary codegen = rewrite**, not a column-alias shim. That's what makes the "code a team would merge" claim survive judging.
- **Scope, not silence.** We turn a *declared, uncoordinated* schema change into a coordinated migration. We do **not** chase silent data-plane drift (occupied lane).
- **3 categories, one run.** Dataset rewrite + coordinated PR + ML retrain tag — thin ML edge in MVP.

---

## Non-goals

- Fancy UI / dashboard (CLI + PR comments are enough)
- Multi-cloud / multi-warehouse production hardening
- Rebuilding Analytics Agent, Ask DataHub, or lineage viz
- Full chatbot interface
- Supporting every SQL dialect

---

## Phases

### Phase 0 — Scaffold (Day 1)

- [ ] Repo layout, Apache 2.0 `LICENSE`, README skeleton
- [ ] `docker compose` / DataHub quickstart notes
- [ ] Seed script: demo lineage graph (1 upstream + 3–4 downstream)
- [ ] Empty `examples/` folder with README explaining what will land there

**Exit:** `datahub docker quickstart` works; seed script registers entities.

### Phase 1 — Read path (Days 2–3)

- [ ] Connect agent to DataHub MCP (local or Cloud)
- [ ] Tools used: `search`, `get_entities`, `list_schema_fields`, `get_lineage`, owners/tags
- [ ] `impact.py`: given a dataset URN + schema diff → blast-radius report (JSON)
- [ ] Unit/self-check: seeded graph returns expected downstream set

**Exit:** CLI `cascade impact --urn ... --diff ...` prints correct blast radius.

### Phase 2 — Reason + generate path (Days 4–5)

- [ ] Diff parser: detect FIELD_REMOVED / FIELD_RENAMED / FIELD_TYPE_CHANGED from SQL/dbt PR (rename = **heuristic first**, annotation confirms/overrides — not required)
- [ ] **Agentic step:** LLM selects a strategy per downstream node with a one-line rationale (`rewrite` / `adapter_view` / `deprecate`) from lineage + owner + severity context
- [ ] **Primary generator = `rewrite`:** edit the downstream dbt model SQL to use the new column (parse the model, rewrite the references). This is the headline artifact
- [ ] Fallbacks: `adapter_view` shim (migration window) and `deprecate` (fail-fast note) when a safe rewrite isn't derivable
- [ ] **Schema-validation gate:** reject any emitted file referencing a column not in DataHub (`list_schema_fields`) — hard fail, no invented columns
- [ ] Thin ML: if a changed column feeds a seeded `mlFeature`, mark the `mlModel` for `retrain-suggested` in the report
- [ ] Golden-diff **eval** (F11): 1 known diff → snapshot expected ImpactReport + rewritten SQL; wire into CI
- [ ] Write sample artifacts into `examples/`, including the one headline rewritten PR diff

**Exit:** Given a known breaking PR, Cascade emits a **rewritten, mergeable** downstream patch + rationale; eval passes; judges can read it without running the agent.

### Phase 3 — Act + write-back (Days 6–7)

- [ ] GitHub Action on `pull_request` (paths: `**.sql`, `**/models/**`)
- [ ] Post blast-radius comment on the source PR **including per-node strategy + rationale** (proves reasoning)
- [ ] Open / update downstream PR(s) with rewritten patches + required reviewers from DataHub owners
- [ ] Write-back via MCP:
  - `save_document` — incident / change plan (with rationale) attached to source
  - `add_tags` — `cascade:breaking-pending`
  - `update_description` — dated root note on culprit dataset
  - ML: `add_tags` `cascade:retrain-suggested` + incident doc on the `mlModel` URN
- [ ] On merge of remediations: clear pending tag, add `cascade:migrated`

**Exit:** Full loop runs on the demo repo without manual DataHub UI clicks; dataset + ML write-backs both visible.

### Phase 4 — Polish + submit (Days 8–10)

- [ ] Harden README: one-command demo, env vars, architecture link
- [ ] Record ≤3 min demo video (YouTube/Vimeo, public) — **against the offline fixture path** for reliability
- [ ] OSS: open the DataHub **Skill** PR (`breaking-change-remediation`) **before the deadline** (named bonus) — link it in README + Devpost
- [ ] Opt into feedback survey ($50 bonus pool)
- [ ] Devpost submission: repo, video, description, live/setup URL

**Exit:** Submission checklist complete; dry-run of judge path.

---

## Milestone calendar (suggestive)

| Window | Focus |
|--------|--------|
| Jul 24–25 | Phase 0–1 |
| Jul 26–28 | Phase 2 (reason + rewrite + eval) |
| Jul 29–31 | Phase 3 (act + write-back, incl. ML tag) |
| Aug 1–5 | Buffer / edge cases / open Skill PR |
| Aug 6–9 | Video, README, Devpost draft |
| Aug 10 | Submit before 5pm EDT |

---

## Demo script (video beats)

1. Show broken PR (column rename on upstream).
2. Cascade Action runs → PR comment with blast radius **+ the agent's per-node strategy and rationale** (this is the "it reasoned" beat).
3. Show the **rewritten** downstream dbt PR — real SQL a team would merge (not just an alias shim).
4. Show DataHub write-back: doc + tags on the dataset, **and** `retrain-suggested` on the ML model — one run, 3 categories.
5. Merge remediation → tag flips to `migrated`.
6. 15s: why this isn't just impact analysis (it reasons, rewrites the code, and feeds the graph back).

---

## Risk → mitigation

| Risk | Mitigation |
|------|------------|
| MCP/auth flaky in demo | Pre-seed + offline fixture mode for video; live path still works locally |
| LLM invents columns | Hard gate: only emit columns present in `list_schema_fields` |
| Scope creep | Cap generators at dbt SQL; Airflow is a stub or skip |
| Judge can’t run | `examples/` + docker-compose + 5-step README |

---

## Definition of done (demo / MVP)

- [ ] End-to-end demo works on fresh clone
- [ ] Primary path is a **rewritten** downstream model (not shim-only)
- [ ] Agent's strategy + rationale visible in PR comment
- [ ] Golden-diff **eval passes in CI** (proves end-to-end)
- [ ] `examples/` contains the headline rewritten PR diff + supporting artifacts
- [ ] Write-back visible in DataHub UI/API — dataset **and** ML model
- [ ] DataHub Skill PR opened + linked
- [ ] Apache 2.0 license detectable on GitHub
- [ ] Video ≤3 min, public (recorded against fixture path)
- [ ] Devpost fields complete

---

## Full plan (if MVP ships early)

Only start this after Phase 4 demo DoD is green. Order is priority for grand-prize differentiation, not calendar days. Cut from the bottom first if time runs out again.

### Rule

**Demo stays demoable.** Every stretch feature must either (a) deepen the same video story or (b) live behind a flag / second scenario — never break the 5-minute judge path.

### Phase 5 — Stronger agent (same story, sharper)

| Item | Why |
|------|-----|
| Multi-hop blast radius with severity scoring (critical marts / SLA-tagged assets first) | Shows real platform judgment, not flat lineage dump |
| Column-level lineage when available; fall back to dataset-level with explicit caveat in report | More precise remediations |
| Contract annotations in SQL (`# cascade: rename a -> b`) + YAML contracts file | Reliable rename detection beyond heuristics |
| Dry-run vs apply modes; `--approve` gate before write-back | Trust / safety for practitioners |
| Richer PR comment: mermaid blast-radius snippet + per-owner checklist | Submission quality + usefulness |
| Idempotent runs (re-run Action updates same downstream PR, doesn’t spam) | Looks production-shaped |

**Exit:** Same demo, but ImpactReport + PR comment look like something a platform team would keep.

### Phase 6 — Cross-repo & multi-artifact generation

| Item | Why |
|------|-----|
| Second demo repo (or path mapping) for true coordinated PR train | Proves “Agents That Do Real Work” beyond mono-repo |
| Generators beyond dbt: Airflow/Dagster task stubs, Great Expectations / dbt tests | Code-gen challenge depth |
| Adapter strategies menu: shim view vs in-place rewrite vs dual-write window | Real migration engineering |
| Owner → GitHub/Slack identity map (config file + DataHub corpUser) | Reviewers actually get pinged |
| Slack (or email) digest to owners with links to Cascaded PRs | Close the human loop |

**Exit:** One upstream PR fans out to ≥2 repos / artifact types; all linked from DataHub doc.

### Phase 7 — Deepen the ML lane (thin version already in MVP)

> The thin ML edge (feature→model, `retrain-suggested` tag, incident doc) is **in the MVP**. This phase deepens it.

| Item | Why |
|------|-----|
| Add `mlModelDeployment` node; gate advice on prod-vs-staging | Safety story judges like |
| Generate a retrain/config patch or a "feature contract broken" test | Metadata-aware code *for ML*, not just a tag |
| Column-level feature→model mapping (which model inputs actually break) | Precision beyond "some model uses this table" |
| Multiple models off one feature; rank by deployment criticality | Real ML platform judgment |

**Exit:** ML remediation is a generated artifact, not only a tag.

### Phase 8 — Runtime / observability loop (not just PR-time)

| Item | Why |
|------|-----|
| Listen to DataHub MetadataChangeLog / Actions for schema assertions already failing | Catch breaks that bypass PR |
| Compare warehouse `INFORMATION_SCHEMA` (or fixture probe) vs catalog schema | Catch silent drift catalog missed |
| Open “break glass” incident PR when prod schema ≠ expected | Agents that do real work continuously |
| Write assertion / freshness guard suggestions back into DataHub | Graph gets smarter each run |

**Exit:** Second scenario in README: “PR path” vs “runtime drift path.”

### Phase 9 — Deepen open-source contribution (base Skill PR already in MVP)

> The `breaking-change-remediation` Skill PR is opened **in the MVP** (before the deadline). This phase adds more.

| Item | Why |
|------|-----|
| Upstream fix / docs / RFC if we hit real MCP or Skill gaps | Credibility with DataHub judges |
| Publish reusable ImpactReport schema + example Action as a template | Community reuse → Town Hall story |
| Contribute a connector or Skill improvement beyond our own recipe | Bonus criterion weight |

**Exit:** ≥1 merged/open upstream PR beyond our own Skill, linked in Devpost + README.

### Phase 10 — Productization polish (only if 5–9 partially done)

| Item | Why |
|------|-----|
| Minimal web UI: paste diff → ImpactReport → download patches (no cards clutter; one job) | Judges who won’t run Docker |
| Policy pack: “block merge if severity=high and no remediation PR” GitHub status check | Platform-team usefulness |
| BigQuery / Snowflake / Postgres dialect profiles (still schema-gated) | Broader realism |
| Audit log of every MCP read/write in `cascade/runs/<id>/` | Debuggability + trust |
| Eval suite: N golden schema diffs → expected blast radius + patch snapshots | Technical execution score |

**Exit:** Cascade feels like a keepable tool, not only a hackathon sketch.

---

### Full-plan priority stack (if we get ~1 extra week)

1. Phase 5 (richer report + idempotent Action) — highest judge ROI  
2. Phase 7 (deepen ML: generated retrain artifact) — originality on top of the MVP tag  
3. Phase 9 (more OSS beyond our Skill) — extra bonus weight  
4. Phase 6 (cross-repo + Airflow/tests) — depth if time  
5. Phase 8 (runtime drift) — wow factor, higher integration cost  
6. Phase 10 (UI / multi-dialect) — only after video is already filmed

> Note: thin ML (Phase 7 base) and the Skill PR (Phase 9 base) are already MVP scope — this stack is about *deepening* them.

### Explicitly still out of scope (even in full plan)

- Replacing DataHub UI or Analytics Agent  
- Autonomous merge without human review  
- Multi-tenant SaaS / billing  
- Guaranteeing perfect semantic rename detection without annotations  
- Supporting every BI tool’s proprietary dialect in one hackathon
