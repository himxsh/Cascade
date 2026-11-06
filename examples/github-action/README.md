# Cascade GitHub Action (consumer template)

Copy [cascade.yml](./cascade.yml) into your repo as `.github/workflows/cascade.yml`, or let `cascade setup` write it. It calls Cascade's reusable workflow ([`run.yml`](../../.github/workflows/run.yml)) pinned to a release tag.

Requires:

- `.cascade/config.json` (path→URN, `models_dir`, optional `urn_files`)
- Secret `DATAHUB_GMS_URL` (HTTPS GMS; fail closed — no fixture fallback)
- Optional secrets: `DATAHUB_TOKEN`, `LLM_API_KEY`, `CASCADE_WRITEBACK`
- For rewrites: variables `CASCADE_MODE=llm` and `LLM_MODEL` (plus `CASCADE_LLM_PROVIDER` / `LLM_BASE_URL` for non-OpenAI providers)

Merge it into the default branch: `/cascade stack` is an `issue_comment` trigger, which GitHub only runs from there. Stacked PRs also need **Settings → Actions → General → Allow GitHub Actions to create and approve pull requests**.
