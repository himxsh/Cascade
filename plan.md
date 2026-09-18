# Cascade — Greptile-style GitHub Agent Plan

## Goal
Make Cascade work like Greptile:
1. Users **sign in with GitHub** on the Cascade website.
2. Users **install the Cascade GitHub App** (logo = PR comment avatar).
3. On the Cascade site, users **enable which repos** get replies.
4. Cascade receives **webhooks** and comments/stacks PRs **as the App** (not `github-actions[bot]`).
5. Per-repo behavior still comes from **`.cascade/`** in the repo.

## Non-goals (MVP)
- GitHub Marketplace listing, billing, multi-team RBAC beyond “logged-in installer”.
- GitLab/Bitbucket.
- Replacing the open-source CLI / optional Actions path entirely (keep CLI; App path is the product).

## Current state (repo)
- Site: `frontend/` (Vite/React) + `api/server.py` (FastAPI on Vercel).
- Marketing pages: home, docs, changelog, security. `InstallPanel` is CLI pip install only — not GitHub App.
- Engine: `cascade/` CLI; Actions workflow posts with `secrets.GITHUB_TOKEN` → `github-actions[bot]` avatar (unchangeable).
- Logo assets: `frontend/public/logo.png`, `apple-touch-icon.png`, etc.

## Architecture (simple)
| Component | Why |
|-----------|-----|
| GitHub OAuth (Sign-In) | Know which human is using the dashboard |
| GitHub App | Cascade’s identity; logo avatar; repo permissions; webhooks |
| Install callback | After Install, Cascade learns the installation id |
| Database | Users, installations, enabled repos |
| Dashboard | Enable/disable repos without editing DB by hand |
| Webhooks | GitHub tells Cascade when PRs/comments happen |
| Worker | Runs impact → apply/comment using an installation token |
| Installation token | Short-lived creds so comments post *as Cascade* |
| `.cascade/` in repo | Path→URN / models config — site decides *whether*, repo decides *how* |

## Phases

### Phase 0 — GitHub App registration (USER LAPTOP — DELAYED)
User creates the App when back on laptop:
- Name: Cascade; avatar = logo from `frontend/public/`.
- Permissions: Pull requests R/W, Contents R/W, Metadata R; events: `pull_request`, `issue_comment`.
- Callback URLs / webhook URL → Cascade production host.
- Save: App ID, private key PEM, webhook secret, OAuth client id/secret → server env only.

**Agent must not block on this.** Scaffold env var names and docs; use mocks/placeholders until secrets exist.

### Phase 1 — Database
Persist:
- `users` — GitHub user id, login, avatar URL, created_at
- `oauth_sessions` / session cookie mapping
- `installations` — installation_id, account_login, account_type, installer_user_id
- `repos` — installation_id, owner, name, github_repo_id, enabled (bool)
- optional `webhook_deliveries` — id, for idempotency/debug

Choice for MVP: SQLite locally + same schema on a small hosted DB (e.g. Turso/Postgres/Vercel-friendly) via env `DATABASE_URL`. Abstract with a thin repo layer.

### Phase 2 — GitHub Sign-In (OAuth)
- Routes: `/auth/github`, `/auth/github/callback`, `/auth/logout`, `/api/me`
- Session cookie (HTTP-only, Secure)
- Frontend: Sign in / Sign out in Chrome; redirect to dashboard when authed
- Env: `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, `SESSION_SECRET`

Can ship with placeholder env; UI + flow complete.

### Phase 3 — Dashboard shell
- New routes: `/app` (or `/dashboard`) — requires auth
- Pages: Overview, Repositories, Connect GitHub (install App CTA)
- Match existing Cascade visual language (`Chrome`, tokens in `index.css`)
- Empty states when no install yet

### Phase 4 — App install callback (stub-ready)
- Link: “Install Cascade App” → `https://github.com/apps/<slug>/installations/new` (slug configurable via env)
- Callback `/api/github/setup` (or GitHub App setup URL) stores `installation_id`
- List repos via GitHub API for that installation (when token available)
- Until App exists: mock list + clear “App not configured” banner when env missing

### Phase 5 — Enable repos
- UI toggles write `repos.enabled`
- API: `GET/PATCH /api/repos`
- Rule documented: workers only process enabled repos

### Phase 6 — Webhooks (skeleton now; live later)
- `POST /api/github/webhook`
- Verify `X-Hub-Signature-256` with `GITHUB_WEBHOOK_SECRET`
- Parse `pull_request`, `issue_comment` (`/cascade stack`)
- Skip `cascade/remediation/*` and disabled repos
- **Now:** validate + enqueue/log + return 200; optional dry-run fixture path
- **Later (after App):** mint installation token → call existing `cascade` apply/comment

### Phase 7 — Act as Cascade (AFTER App exists)
- Installation access token from App JWT
- Reuse `cascade.github_act.post_pr_comment` / apply pipeline with that token + `GITHUB_REPOSITORY`
- Ensure comment author is the App (logo avatar)
- Keep Actions workflow as optional self-hosted path; document App path as preferred product

### Phase 8 — Docs & polish
- Docs page: Connect GitHub → enable repos → first PR
- `.env.example` for all secrets
- Security notes: never expose private key to frontend

## Build-now scope (this iteration)
Implement Phases **1–6 + docs stubs** in-repo:
1. DB schema + migrations/bootstrap
2. GitHub OAuth sign-in + session + `/api/me`
3. Dashboard UI (auth-gated) + repo enable toggles
4. App install CTA + install/setup callback handlers (graceful without App secrets)
5. Webhook endpoint with signature verification + event filtering + structured logging (no live App comments yet)
6. `plan.md` committed; `.env.example` + short docs section “GitHub App (when ready)”

Explicitly **out of this iteration:**
- Creating/registering the GitHub App on github.com
- Uploading the logo to GitHub
- Real installation tokens / posting PR comments as the App
- Removing or breaking the existing CLI/Actions path

## Acceptance (build now)
- Logged-out user can open marketing site; dashboard redirects to sign-in
- With OAuth env set (or test harness), user can sign in and see `/app`
- User can see repo list UI and toggle enabled (persisted in DB)
- Webhook with invalid signature → 401; valid test payload → 200 and logged/filtered correctly
- Without App secrets, UI explains “create App when on laptop” and does not crash
- Existing demo `/api/run` and static site still work

## Agent constraints
- Prefer extending `api/server.py` + `frontend/`; don’t invent a parallel stack without reason
- No secrets in git; use env vars
- Open a PR with clear test/run instructions
