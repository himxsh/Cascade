# Cascade GitHub Action (consumer template)

Copy [cascade.yml](./cascade.yml) into your repo as `.github/workflows/cascade.yml`.

Requires:

- `.cascade/config.json` (path→URN, `models_dir`, optional `urn_files`)
- Secret `DATAHUB_GMS_URL` (HTTPS GMS; fail closed — no fixture fallback)
- Optional: `DATAHUB_TOKEN`, `LLM_API_KEY`, `CASCADE_WRITEBACK`

Pin Cascade to a commit/tag in the install step. See [cascade-shop](https://github.com/himxsh/cascade-shop) for a full reference repo.
