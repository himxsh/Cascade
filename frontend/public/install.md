# Install Cascade in this repository

You are helping a user install Cascade (https://github.com/himxsh/Cascade) in the git repository open in this session.

Cascade is a GitHub Action. When a pull request changes SQL, dbt models, or schema.yml, it looks up downstream tables in the user's DataHub catalog and comments on the PR with what will break. If the user comments `/cascade stack`, it opens a second PR with the downstream SQL rewritten. It never connects to a warehouse.

## Rules for you, the agent

- Work in small steps. Before each step, tell the user in one or two plain sentences what you are about to do and why. Wait for a yes before anything that changes their repository, their GitHub settings, or their secrets.
- Never ask the user to paste a secret (API key, token) into this chat, and never write one into a file that could be committed. Secrets go in GitHub Actions secrets, which the user sets with commands that prompt for the value. The only local secret file is `.env`, which must stay gitignored.
- Do not push to the default branch. All changes go on a new branch and a pull request.
- If a command fails, show the user the error, explain it in one sentence, and suggest the fix. Do not loop on retries.
- When you see a line below marked **Tell the user**, say that to the user in your own words at that point. These are the things people get surprised by later.

## Step 0: Explain the plan first

**Tell the user**, before running anything:

- Installing Cascade adds three files to the repo: `.cascade/config.json`, `.env.example`, and `.github/workflows/cascade.yml`. It may also add `.env` to `.gitignore`.
- These files have to be **committed and merged into the default branch** for Cascade to run. You will put them on a branch and open a PR; the user reviews and merges it.
- Cascade needs a **DataHub** instance that GitHub's runners can reach over HTTPS (not `localhost`). Without it, Cascade can only run in a local demo mode.
- By default Cascade only **reports** on PRs. Rewriting SQL needs an LLM API key, which is optional and set up at the end.

Then ask the user:

1. Do they have a DataHub GMS URL reachable over HTTPS? If not, offer demo mode (step 3, `--demo`) and explain that real PR comments will need DataHub later.
2. Does their DataHub need an access token?
3. Do they want SQL rewrites (needs an LLM API key) or report-only for now? Report-only is a fine place to start.

## Step 1: Check prerequisites

Check each and report the results to the user in a short list:

- This is a git repository with a GitHub remote: `git remote -v`
- The repo contains SQL or dbt files (`*.sql`, a `models/` folder, or `schema.yml`). If it has none, stop and tell the user Cascade has nothing to watch here.
- Python 3.11 or newer: `python3 --version`
- GitHub CLI installed and signed in: `gh auth status`. If it is missing, the user can still finish, but they will set secrets in the GitHub web UI instead (Settings → Secrets and variables → Actions).
- The working tree is clean: `git status`. If not, ask before continuing.

## Step 2: Install the CLI

Create a branch, then install:

```bash
git checkout -b add-cascade
python3 -m pip install cascade-bot
cascade --version
```

If `pip` refuses because the Python is externally managed, use `pipx install cascade-bot` or a virtual environment instead, and tell the user which you used.

## Step 3: Run setup

If DataHub needs a token, ask the user to create a `.env` file at the repo root themselves with `DATAHUB_TOKEN=...` in it (setup reads it, and `.env` is gitignored). Do not create it with the token yourself.

Run setup without prompts and without touching secrets, since the user sets those in step 5:

```bash
DATAHUB_GMS_URL="<the URL the user gave you>" cascade setup --non-interactive --skip-secrets
```

Or, for demo mode with no DataHub:

```bash
cascade setup --demo --non-interactive
```

Show the user the summary of what setup printed: which files it wrote, which SQL files it matched to DataHub tables, and which it could not match.

## Step 4: Check the table mappings

Open `.cascade/config.json`. It maps folders or files in this repo to DataHub dataset URNs, which are DataHub's IDs for tables, like `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.orders,PROD)`.

- Remove any entry still containing the placeholders `YOUR_DB` or `YOUR_TABLE`.
- For files setup listed as unmapped, ask the user which DataHub table each one is. Do not guess URNs.
- Make sure `models_dir` points at the folder where this repo keeps its models.

**Tell the user**: this file decides which tables Cascade watches. A wrong URN means Cascade stays quiet on PRs it should comment on.

## Step 5: GitHub Actions secrets and variables

**Tell the user**: the workflow reads its settings from this repo's GitHub Actions secrets. Cascade's servers never see them. They should run these commands themselves in their terminal, because `gh secret set` prompts for the value and keeps it out of this chat:

```bash
gh secret set DATAHUB_GMS_URL
gh secret set DATAHUB_TOKEN        # only if DataHub needs a token
```

For report-only mode:

```bash
gh variable set CASCADE_MODE --body off
```

If they want SQL rewrites:

```bash
gh secret set LLM_API_KEY
gh variable set CASCADE_MODE --body llm
gh variable set LLM_MODEL --body "<model name, e.g. gpt-4o>"
```

The default provider is OpenAI-compatible. For Anthropic, Azure OpenAI, Bedrock, or another endpoint they also need `gh variable set CASCADE_LLM_PROVIDER --body <anthropic|azure-openai|bedrock|custom>` and `gh variable set LLM_BASE_URL --body <url>`. For Ollama, set the provider to `ollama`.

**Tell the user**, if they chose rewrites: with `CASCADE_MODE=llm`, the affected downstream SQL is sent to the LLM provider they chose, on their API key and their bill.

Wait until the user says they are done, then check with `gh secret list` and `gh variable list` (these show names, never values).

## Step 6: Verify

```bash
cascade doctor
```

Go through anything marked `fail` or `warn` with the user and fix what you can. `warn DATAHUB_GMS_URL unset` is expected locally if they only set it as a GitHub secret.

## Step 7: Commit and open the PR

**Tell the user**, before committing:

- You are about to commit the Cascade files to the `add-cascade` branch and open a pull request. Nothing reaches the default branch until they merge it.
- The workflow runs on pull requests that touch SQL, models, or schema files. It has write access to contents and pull requests: it needs that to comment, and to push a branch when someone comments `/cascade stack`. It does not push or open PRs on its own.
- `/cascade stack` only works **after this PR is merged**, because GitHub runs comment-triggered workflows from the default branch.
- For stacked PRs, the repo (or org) setting "Allow GitHub Actions to create and approve pull requests" must be on: Settings → Actions → General → Workflow permissions. If the org restricts which actions can run, it also has to allow `himxsh/Cascade`.

Check that `.env` is not staged, then (include `.gitignore` only if setup changed it):

```bash
git add .cascade/config.json .env.example .github/workflows/cascade.yml .gitignore
git commit -m "Add Cascade"
git push -u origin add-cascade
gh pr create --title "Add Cascade" --body "Adds the Cascade GitHub Action, which comments on schema PRs with downstream impact from DataHub. See https://github.com/himxsh/Cascade"
```

## Step 8: Wrap up

Give the user the PR link and a short summary:

- What was installed, and whether it is report-only or rewriting SQL.
- What they still have to do: review and merge the PR, plus anything left over (unmapped tables, missing secrets, the Actions PR setting).
- How to try it: after merging, open a PR that renames a column in one of the mapped models. Cascade should comment on it. Comment `/cascade stack` on that PR to get the downstream rewrite as a stacked PR.
