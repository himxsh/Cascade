# Cascade — Backup Plan (timeboxed)

**When to use:** Not enough time for [final_plan.md](./final_plan.md).  
**Goal:** Strongest *credible* live story for judges without building full production Act.

```text
Live GMS read → rewrite (LLM if keyed, else demo agent) → visible DataHub write-back
  → source PR comment → remediation patch artifacts (PR auto-open optional)
```

---

## Definition of done (backup)

- [ ] Reachable GMS (Cloud **or** local Docker for laptop/video; Actions live only if Cloud)
- [ ] Real write-back aspects (no `cascadeStub`) — tags/docs visible in DataHub UI
- [ ] `cascade demo --source live` (+ `CASCADE_WRITEBACK=1`) works end-to-end
- [ ] Source PR comment works (fixture or live report)
- [ ] Headline artifacts: rewritten SQL + `downstream_pr.diff` + rationale comment
- [ ] Video ≤3 min against **live DataHub UI** (not only fixture JSON)
- [ ] Devpost + survey + Apache 2.0 About; Skill PR if one hour left
- [ ] README honest: what is live vs dry-run vs not built yet

**Explicitly cut:** auto branch/commit remediation PR, PR-diff-from-Action, MCP swap, policy checks, multi-golden eval expansion, cross-repo.

---

## P0 — Stand up GMS + seed (must)

1. Prefer DataHub Cloud if Actions live matters; else `datahub docker quickstart` + seed for laptop/video.
2. `python demo/seed_demo_graph.py --apply`
3. `.env`: `DATAHUB_GMS_URL`, optional `DATAHUB_TOKEN`
4. Confirm UI: demo URN + lineage at http://localhost:9002 (or Cloud UI)

**Exit:** Seed entities visible in UI.

---

## P1 — Fix the lies (must)

1. Replace `cascadeStub` in `cascade/datahub_write.py` with real tags + description/doc (SDK emitter like seed script).
2. Add `--source` to `generate` / `apply` via `resolve_catalog` in `cascade/cli.py`.
3. Smoke:

```bash
cascade impact --source live --urn 'urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)' \
  --diff examples/diffs/raw_orders_rename_user_id.json \
  --generate --models-dir examples/models --out /tmp/cascade-live

CASCADE_WRITEBACK=1 cascade apply --report /tmp/cascade-live/impact_report.json \
  --out /tmp/cascade-live-apply --mark-migrated
```

**Exit:** Tags + docs visible on dataset + ML model in DataHub UI.

---

## P2 — Judge-visible Act (pick one hour)

**Do A (preferred for video):** Open a PR that touches `examples/diffs/**` or `*.sql` so `.github/workflows/cascade.yml` posts a **live comment** on the source PR. Accept that the job may still be fixture-backed if Cloud GMS isn’t ready — say so in README; still show comment + artifacts.

**Do B (if Cloud GMS + secrets ready):** Point Action at `--source live` + GMS secrets; still OK to keep hardcoded demo diff for backup.

**Skip:** Git Data API auto remediation PR. Ship `downstream_pr.diff` + `examples/rewritten/` as the mergeable artifact; narrate “coordinated PR” from patch + optional manual PR from the branch if you have five spare minutes.

---

## P3 — LLM (only if key exists)

1. Set `LLM_API_KEY` locally (and Action secret if using live Action).
2. Don’t rebuild agent — optional overlay already in `cascade/agent.py`.
3. If no key: keep demo agent; don’t claim LLM-primary in Devpost.

---

## P4 — Submit (non-negotiable)

1. Video beats (≤3 min): broken change → Cascade run → DataHub UI tags → PR comment / patch → one-liner “coordinates migration.”
2. Devpost: repo, video, description, setup or live UI URL; survey opt-in.
3. GitHub About: description, homepage, Apache 2.0 visible.
4. Skill: open upstream PR **only if** P0–P1 green and ≥1 hour left; else link in-repo `oss/datahub-skills/` and note “draft.”

---

## Cut order if still slipping

| Drop first | Keep until last |
|------------|-----------------|
| MCP / Agent Context Kit | Real write-back (P1) |
| Auto remediation PR | Live GMS seed + UI proof |
| Action live source | Video + Devpost |
| LLM-primary | Fixture CI green |
| Skill upstream PR | Honest README |

---

## Map to full plan

| Backup | Full plan ([final_plan.md](./final_plan.md)) |
|--------|-----------------------------------------------|
| P0 | Phase 0 (local allowed for video) |
| P1 | Phase 1 only |
| P2 | Slice of Phase 3–4 (comment + artifacts, not auto PR) |
| P3 | Thin Phase 2 |
| P4 | Phase 7 submit only |

Resume full plan at Phase 3 (real PR diff) → Phase 4 (auto remediation PR) after submit if time appears.
