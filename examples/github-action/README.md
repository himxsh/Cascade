# Cascade GitHub Action (consumer template)

Copy [cascade.yml](./cascade.yml) into your repo as `.github/workflows/cascade.yml`.

Requires:

- `.cascade/config.json` (path→URN, `models_dir`, optional `urn_files`)
- Secret `DATAHUB_GMS_URL` (HTTPS GMS; fail closed — no fixture fallback)
- Optional: `DATAHUB_TOKEN`, `LLM_API_KEY`, `CASCADE_WRITEBACK`

Pin Cascade to a commit/tag in the install step.

## Comment avatar

Comments post as whoever owns the token. Default `GITHUB_TOKEN` is **github-actions[bot]**; you cannot change that avatar.

To show the Cascade logo in the circular PR-thread avatar, create a GitHub App named `Cascade`, upload [`frontend/public/apple-touch-icon.png`](../../frontend/public/apple-touch-icon.png) (or [`logo.png`](../../frontend/public/logo.png)) as the App logo, install it on this repo, then set:

| Kind | Name | Value |
| --- | --- | --- |
| Variable | `CASCADE_GITHUB_APP_ID` | Numeric App ID |
| Secret | `CASCADE_GITHUB_APP_PRIVATE_KEY` | App `.pem` |

Repository permissions: Contents, Issues, and Pull requests — Read and write. Disable the App webhook.

Fallback: a machine user’s profile picture + secret `CASCADE_GITHUB_TOKEN`.

Full steps: [README — Comment avatar](../../README.md#comment-avatar-github-identity).

