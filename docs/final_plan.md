# Cascade — Final Plan (full production loop)

**Goal:** Ship the ideal pipeline end-to-end:

```text
Breaking PR diff → live DataHub (GMS) → LLM reasons + rewrites
  → remediation PR (+ reviewers) → real DataHub write-back
  → on merge: cascade:migrated
```

This plan ignores calendar pressure. Do phases in order; later phases assume earlier ones are green.

Related: [plan.md](./plan.md) (original hackathon MVP), [spec.md](./spec.md), [progress.md](./progress.md) (MVP), [progress_final.md](./progress_final.md) (this plan).  
Timeboxed cut: [backup_final.md](./backup_final.md).

---

## Definition of done (production)

- [ ] Action runs on the **PR’s own** schema/SQL diff (not a hardcoded example file)
- [ ] Catalog read is **live GMS** (datasets, lineage, owners; ML from GMS when available)
- [ ] LLM is the **primary** strategy + rewrite path when keyed; deterministic is fallback only
- [ ] Schema gate rejects invented columns
- [ ] Source PR gets a blast-radius comment with per-node strategy + rationale
- [ ] Downstream remediation PR is **created/updated automatically** (branch + commit + PR)
- [ ] DataHub write-back uses **real aspects** (tags, description/docs) visible in UI — dataset **and** ML model
- [ ] Merge of remediation flips pending → `cascade:migrated`
- [ ] Dry-run default; live Act gated by secrets / explicit apply
- [ ] Re-runs are idempotent (same upstream PR → same downstream PR)
- [ ] CI eval (golden + live smoke where secrets exist) stays green
- [ ] README documents secrets, URN mapping, judge path, and failure modes

---

## Phase 0 — Reachable DataHub + secrets

**Why:** Nothing “live” works without a GMS the runner (and you) can hit. Localhost Docker is for laptop demos only; GitHub Actions needs Cloud or a public/self-hosted GMS.

### Steps

1. Provision DataHub Cloud **or** a durable self-hosted GMS (HTTPS).
2. Create a token with read + aspect ingest.
3. Configure repo secrets / env:
   - `DATAHUB_GMS_URL`
   - `DATAHUB_TOKEN`
   - `LLM_API_KEY` (or `OPENAI_API_KEY`)
   - `LLM_BASE_URL` (optional)
   - `CASCADE_WRITEBACK=1` only on trusted environments (or set in a dedicated apply job)
4. Ingest or seed a lineage graph that matches production demo URNs (extend `demo/seed_demo_graph.py` or use real warehouse ingestion).
5. Verify from laptop: `GET {GMS}/health`, GraphQL dataset + lineage for seed URN.
6. Verify from a throwaway workflow step: same health check with secrets.

### Exit

GMS healthy from laptop **and** Actions; seed/real entities visible in DataHub UI.

### Touch

- `.env.example`, README secrets table
- `demo/seed_demo_graph.py`, `demo/datahub-quickstart.md` (local still supported for offline)
- Optional: `.github/workflows/gms-smoke.yml`

---

## Phase 1 — Honest DataHub read + write

**Why:** Today live write posts `cascadeStub`; generate/apply can ignore live catalog. Judges and operators must see real tags/docs.

### Steps

1. **Write-back:** Replace `cascadeStub` in `cascade/datahub_write.py` with real aspects via SDK emitter (same pattern as `demo/seed_demo_graph.py`):
   - Dataset: `globalTags` (`cascade:breaking-pending`, clear on migrate), editable description and/or institutional memory (change plan + rationale)
   - ML model: `globalTags` (`cascade:retrain-suggested`) + incident doc
   - `mark_migrated`: remove pending, add `cascade:migrated`
2. Soft-import `acryl-datahub` for live write; dry-run remains stdlib JSON artifacts when `CASCADE_WRITEBACK` unset.
3. **Read:** Complete live catalog in `cascade/datahub_live.py` — datasets, lineage, owners from GMS; read ML entities from GMS when aspects exist; fixture ML only as explicit fallback with stderr notice.
4. **CLI:** `cascade generate` and `cascade apply --generate` use `resolve_catalog` + `--source fixture|live|auto` (same as `impact` / `demo`).
5. Unit tests for aspect payload shape; optional `@unittest.skipUnless` live integration when `DATAHUB_GMS_URL` + credentials present.

### Exit

`CASCADE_WRITEBACK=1 cascade demo --source live` leaves **visible** tags + docs on source dataset and ML model in DataHub UI.

### Touch

- `cascade/datahub_write.py`, `cascade/datahub_live.py`, `cascade/cli.py`
- `tests/test_apply.py`, new write/live tests
- `demo/requirements.txt` / optional `[writeback]` extra in `pyproject.toml`

---

## Phase 2 — LLM-primary agent

**Why:** Hackathon positioning: agent reasons; tools do parse/lineage/GitHub. Deterministic-only is a script.

### Steps

1. When `LLM_API_KEY` / `OPENAI_API_KEY` is set, LLM owns strategy + SQL; deterministic `_demo_choose_and_rewrite` is fallback on timeout/parse failure.
2. Keep schema gate as hard fail after LLM output.
3. Ensure every remediation has `strategy` + one-line `rationale` in report, PR comment, and DataHub doc body.
4. Structured logging of model, latency, fallback reason (no secrets).
5. Action/job supplies LLM secret; document cost/latency expectations in README.

### Exit

Live run with key set: PR comment rationales come from LLM path; without key: clear fallback, still correct rewrites for the golden rename.

### Touch

- `cascade/agent.py`, `cascade/schema_gate.py`, `cascade/comment.py`
- `.github/workflows/cascade.yml` env
- `tests/` agent fallback coverage

---

## Phase 3 — Action on the real PR diff

**Why:** Hardcoded `examples/diffs/raw_orders_rename_user_id.json` + `--source fixture` is a showcase, not a product.

### Steps

1. Rewrite `.github/workflows/cascade.yml` job away from `fixture-dry-run` naming for the production job (keep a separate fixture job for offline CI).
2. On `pull_request`: compute changes from the PR (`git diff` base…head for `*.sql`, `**/models/**`, `schema.yml`) and feed `load_changes` / diff parser.
3. Resolve seed dataset URN via repo config (e.g. `cascade.yml` or `.cascade/config.json`: path prefix → URN). Fallback: workflow input / repository variable.
4. Run `cascade impact --source live --generate` with GMS + LLM secrets.
5. `cascade apply` dry-run artifacts always; live comment on source PR (existing `post_pr_comment`).
6. Upload artifacts; fail the check on schema-gate / impact errors (configurable).

### Exit

A real breaking SQL PR against a mapped URN triggers live impact + comment without touching `examples/diffs/`.

### Touch

- `.github/workflows/cascade.yml`
- New thin config loader (stdlib) + README
- `cascade/diff_parser.py` / CLI flags for stdin / multi-file diff if needed
- Keep fixture workflow or CI job for PRs without secrets

---

## Phase 4 — Automatic remediation PR

**Why:** Ideal “Act” is a second PR reviewers can merge. Pre-pushed `CASCADE_DOWNSTREAM_HEAD` is not production.

### Steps

1. Implement Git Data API (or Contents API) flow in `cascade/github_act.py`:
   - Create/update branch from base
   - Commit rewritten files
   - Open or update PR (idempotent key: e.g. `cascade/remediation/{upstream_pr}` branch name)
2. Remove happy-path dependency on pre-pushed head; keep env override for advanced users.
3. Request reviewers from DataHub owners; optional `owners_map.yaml` (corpUser → GitHub login).
4. Link remediation PR URL in source PR comment and DataHub change-plan doc.
5. On remediation merge (workflow `pull_request` closed/merged or `workflow_run`): call `mark_migrated` with write-back enabled.

### Exit

One upstream breaking PR → one updated remediation PR with SQL a team would merge; merge flips DataHub tags.

### Touch

- `cascade/github_act.py`, `cascade/apply.py`, `cascade/comment.py`
- `.github/workflows/cascade.yml` (+ optional `cascade-migrated.yml`)
- `tests/test_apply.py` (mock GitHub API)

---

## Phase 5 — Production hardening

**Why:** Safe to leave on overnight; operators trust it.

### Steps

1. Modes: `dry-run` (default) vs `apply`; environment protection / manual approval for write-back + PR open on protected branches.
2. Policy status check: severity=high and no open remediation PR → fail.
3. Idempotent write-backs and comment updates (edit prior Cascade comment instead of spam).
4. Run audit dir: `cascade/runs/<id>/` (inputs, report, LLM fallback, GH URLs, write-back receipts).
5. Eval suite: N golden diffs → expected blast radius + patches; optional nightly live smoke.
6. Dialect profiles (BigQuery / Snowflake / Postgres) still schema-gated — only after core loop is stable.
7. Observability: structured logs + Action summary markdown.

### Exit

Re-run on the same PR is safe; failure modes are documented; policy check optional but working.

### Touch

- `cascade/apply.py`, new `cascade/policy.py` (minimal), workflows
- `tests/golden/` expansion
- README “Production” section

---

## Phase 6 — Deepen DataHub / OSS (differentiation)

**Why:** Grand-prize / bonus: depth of DataHub use + OSS contribution.

### Steps

1. Optional: swap GraphQL urllib for official MCP / Agent Context Kit where it reduces custom code — without breaking fixture offline path.
2. Column-level lineage when GMS provides it; caveat in report when falling back to dataset-level.
3. Open/refresh upstream Skill PR (`breaking-change-remediation`); link in README + Devpost.
4. Extra OSS only if Skill is merged/open: docs fix, second Skill, or RFC.

### Exit

Skill PR linked; live path uses the richest metadata GMS can give; MCP optional but documented if adopted.

---

## Phase 7 — Product surface + submit assets

**Why:** Judges who won’t run Docker still need a story; submission quality is scored.

### Steps

1. Keep Phase 10 UI: paste-diff → live/auto source against Cloud GMS; show remediations + write-back receipts.
2. Deploy UI (Vercel) with server-side secrets; never expose tokens to the browser.
3. Record ≤3 min video of the **live** loop (DataHub UI tags, PR comment, remediation PR).
4. Devpost: repo, video, description, live URL; survey opt-in; Apache 2.0 visible on GitHub About.
5. Sync `docs/progress.md` to match reality.

### Exit

Submission checklist complete; live URL and video match the production path.

---

## Suggested build order (no timebox)

| Order | Phase | Depends on |
|------:|-------|------------|
| 1 | 0 Reachable GMS | — |
| 2 | 1 Honest read/write | 0 |
| 3 | 2 LLM-primary | 1 (can overlap) |
| 4 | 3 Action on real PR | 0–2 |
| 5 | 4 Remediation PR | 3 |
| 6 | 5 Hardening | 4 |
| 7 | 6 OSS / MCP deepen | 1+ |
| 8 | 7 UI + submit assets | 4 minimum for video |

---

## Explicit non-goals (still)

- Replacing DataHub UI / Analytics Agent
- Autonomous merge without human review
- Multi-tenant SaaS
- Perfect semantic rename detection without annotations/heuristics
- Every BI/SQL dialect in one project

---

## Reality scorecard (target)

| Capability | Target state |
|------------|--------------|
| Offline fixture E2E | Kept for CI / no-secrets |
| Live dataset/lineage/owners | GMS GraphQL (or MCP) |
| Live ML | GMS when present |
| Strategy + SQL | LLM primary + schema gate |
| Source PR comment | Live, from real report |
| Remediation PR | Auto branch + commit + open/update |
| DataHub write-back | Real tags + docs in UI |
| Migrated lifecycle | On remediation merge |
| MCP Agent Context Kit | Optional Phase 6 |
