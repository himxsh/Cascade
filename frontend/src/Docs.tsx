import type { ReactNode } from 'react'
import { GhCode } from './Gh'
import { Link } from './Link'
import { CONTRIBUTING, GITHUB, PIP, VERSION } from './site'

export const DOC_IDS = [
  'get-started',
  'install',
  'configure',
  'environment',
  'github-app',
  'action',
  'rewrite',
  'providers',
  'datahub',
  'cli',
  'faq',
] as const

export type DocId = (typeof DOC_IDS)[number]

const NAV: { id: DocId; label: string }[] = [
  { id: 'get-started', label: 'Get started' },
  { id: 'install', label: 'Install' },
  { id: 'configure', label: 'Configure' },
  { id: 'action', label: 'GitHub Action' },
  { id: 'github-app', label: 'GitHub App' },
  { id: 'rewrite', label: 'How it edits' },
  { id: 'providers', label: 'AI models' },
  { id: 'datahub', label: 'DataHub' },
  { id: 'cli', label: 'Commands' },
  { id: 'faq', label: 'FAQ' },
]

export function docFromPath(path: string): DocId {
  if (path === '/docs' || path === '/docs/') return 'get-started'
  const slug = path.replace(/^\/docs\//, '')
  return (DOC_IDS as readonly string[]).includes(slug) ? (slug as DocId) : 'get-started'
}

function hrefFor(id: DocId): string {
  return id === 'get-started' ? '/docs' : `/docs/${id}`
}

function H({ children }: { children: ReactNode }) {
  return <h1 className="display text-[clamp(2rem,4vw,2.75rem)]">{children}</h1>
}

function H2({ children }: { children: ReactNode }) {
  return <h2 className="mt-10 text-xl font-semibold">{children}</h2>
}

function P({ children }: { children: ReactNode }) {
  return <p className="mt-4 max-w-[65ch] text-mute">{children}</p>
}

const LINK = 'text-frost underline decoration-ember/70 underline-offset-4'

function A({ href, children }: { href: string; children: ReactNode }) {
  // Static files (like /install.md) are not SPA routes, so skip client-side nav.
  if (href.endsWith('.md')) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={LINK}>
        {children}
      </a>
    )
  }
  return (
    <Link href={href} className={LINK}>
      {children}
    </Link>
  )
}

function C({ children }: { children: ReactNode }) {
  return <code className="cmd text-[0.9em] text-frost">{children}</code>
}

function DocBody({ id }: { id: DocId }) {
  switch (id) {
    case 'get-started':
      return (
        <>
          <H>Get Cascade running</H>
          <P>
            You need SQL or dbt files in a GitHub repo, and those tables already
            in DataHub with their downstream lineage. Cascade reads DataHub. It
            never connects to your warehouse.
          </P>
          <P>There are three ways to install it. Pick one.</P>
          <ol className="mt-8 space-y-6">
            <li>
              <p className="font-semibold">Let your AI agent do it</p>
              <P>
                On the home page, copy the &ldquo;Install with an AI agent&rdquo;
                prompt and paste it into Claude Code, Cursor, or Codex in your
                repo. The agent runs setup, asks you about anything it can&apos;t
                work out, has you set secrets yourself, and opens a PR.{' '}
                <A href="/install.md">Read the prompt</A>.
              </P>
            </li>
            <li>
              <p className="font-semibold">Use the CLI</p>
              <GhCode file="terminal">{`${PIP}
cascade setup`}</GhCode>
              <P>
                Setup writes three files, maps your SQL files to DataHub tables,
                and can set GitHub Actions secrets with the gh CLI. Commit the
                files and merge them. See <A href="/docs/install">Install</A>.
              </P>
            </li>
            <li>
              <p className="font-semibold">Install the GitHub App</p>
              <P>
                Sign in, install the Cascade App on a repo, and it adds the
                workflow for you. You still add the secrets and the config
                file. See <A href="/docs/github-app">GitHub App</A>.
              </P>
            </li>
          </ol>
          <H2>Then try it</H2>
          <P>
            Once the workflow is on your default branch, open a PR that renames
            a column in a mapped model. Cascade comments with the downstream
            impact. Comment <C>/cascade stack</C> on that PR to get the
            downstream fixes as a stacked PR.
          </P>
          <P>To try it locally first, without GitHub:</P>
          <GhCode file="terminal">{`cascade impact --diff path/to.sql.diff --source live --generate --out artifacts/run
cascade apply --report artifacts/run/impact_report.json --out artifacts/apply`}</GhCode>
          <P>That only writes files under artifacts/. Nothing is posted.</P>
        </>
      )
    case 'install':
      return (
        <>
          <H>Install</H>
          <H2>With an AI agent</H2>
          <P>
            The home page has an &ldquo;Install with an AI agent&rdquo; button.
            It copies a prompt for Claude Code, Cursor, Codex, or any agent that
            can run commands in your repo. The agent:
          </P>
          <ul className="mt-4 max-w-[65ch] list-disc space-y-2 pl-5 text-mute">
            <li>explains what will change before it changes anything,</li>
            <li>installs the CLI and runs cascade setup on a new branch,</li>
            <li>asks you which DataHub table each unmapped file is,</li>
            <li>
              has you run gh secret set yourself, so keys never reach the chat,
            </li>
            <li>runs cascade doctor, then opens a PR for you to review.</li>
          </ul>
          <P>
            You can point an agent at the prompt directly too: &ldquo;Follow{' '}
            <A href="/install.md">/install.md</A> on this site to install
            Cascade.&rdquo;
          </P>

          <H2>With the CLI</H2>
          <P>You need Python 3.11 or newer.</P>
          <GhCode file="terminal">{`${PIP}
cascade setup`}</GhCode>
          <P>
            That installs cascade-bot {VERSION} from PyPI. Run setup from inside
            your repo. It writes .cascade/config.json, .env.example, and
            .github/workflows/cascade.yml, and adds .env to .gitignore.
          </P>
          <P>
            If DATAHUB_GMS_URL is set, setup checks DataHub and maps your SQL
            files to tables. If the gh CLI is signed in, it can also set your
            Actions secrets. Useful flags:
          </P>
          <ul className="mt-4 max-w-[65ch] list-disc space-y-2 pl-5 text-mute">
            <li>
              <C>--demo</C> skips DataHub and uses the sample catalog.
            </li>
            <li>
              <C>--non-interactive</C> fails instead of prompting (CI, scripts,
              agents).
            </li>
            <li>
              <C>--skip-secrets</C> leaves GitHub secrets alone.
            </li>
          </ul>
          <P>
            Commit the three files and merge them into your default branch.
            Cascade does not run until the workflow is there.
          </P>
          <P>
            The pip extra [writeback] is only needed if you want Cascade to tag
            tables in DataHub.
          </P>

          <H2>With the GitHub App</H2>
          <P>
            The App adds the workflow for you. See{' '}
            <A href="/docs/github-app">GitHub App</A>.
          </P>
          <p className="mt-6">
            <A href={GITHUB}>Source on GitHub</A>
          </p>
        </>
      )
    case 'configure':
      return (
        <>
          <H>Configure</H>
          <P>
            .cascade/config.json tells Cascade which files in git belong to
            which table in DataHub. A urn is DataHub&apos;s ID for a table. It
            never asks for a database password.
          </P>
          <GhCode file=".cascade/config.json">{`{
  "models_dir": "models",
  "default_urn": "urn:li:dataset:(urn:li:dataPlatform:postgres,db.public.orders,PROD)",
  "mappings": [
    {
      "path": "models/",
      "urn": "urn:li:dataset:(urn:li:dataPlatform:postgres,db.public.orders,PROD)"
    }
  ],
  "urn_files": {},
  "rewrite": { "mode": "off", "provider": "openai", "model": "" }
}`}</GhCode>
          <P>
            The longest matching path wins. Pin a single file under urn_files.
            Remove any entry still containing YOUR_DB or YOUR_TABLE: a wrong
            urn means Cascade stays quiet on PRs it should comment on.
          </P>
          <P>
            Environment variables and Actions variables override this file. For
            example, CASCADE_MODE wins over rewrite.mode.
          </P>
        </>
      )
    case 'environment':
      return (
        <>
          <H>Self-hosting</H>
          <P>
            Keys for DataHub and AI rewrites stay in your repo&apos;s GitHub
            Actions secrets, or a local .env that is never committed. Cascade
            does not host them.
          </P>
          <P>
            Setup for the optional hosted dashboard (database URL, session
            signing, GitHub OAuth, GitHub App) is in the contributing guide.
          </P>
          <p className="mt-6">
            <A href={CONTRIBUTING}>Contributing guide</A>
          </p>
        </>
      )
    case 'github-app':
      return (
        <>
          <H>GitHub App</H>
          <P>
            The App installs the workflow for you. Sign in on this site, open
            the dashboard, and choose Install Cascade App. GitHub asks which
            repos to give it.
          </P>
          <P>For each repo, the App then:</P>
          <ul className="mt-4 max-w-[65ch] list-disc space-y-2 pl-5 text-mute">
            <li>
              commits .github/workflows/cascade.yml to the default branch, or
            </li>
            <li>
              opens a cascade/setup PR when the branch is protected. Merge it
              to turn Cascade on.
            </li>
          </ul>
          <P>
            The App only adds the workflow. You still need to:
          </P>
          <ul className="mt-4 max-w-[65ch] list-disc space-y-2 pl-5 text-mute">
            <li>
              add the Actions secret DATAHUB_GMS_URL (and DATAHUB_TOKEN if your
              DataHub needs one),
            </li>
            <li>
              for AI fixes, add the secret LLM_API_KEY and the variables
              CASCADE_MODE=llm and LLM_MODEL,
            </li>
            <li>
              commit a .cascade/config.json. Run cascade setup or the AI agent
              prompt to make one.
            </li>
          </ul>
          <P>
            The dashboard links straight to each of those GitHub settings pages
            after you install. Your keys stay in your repository&apos;s secrets.
            This site never receives them.
          </P>
          <p className="mt-6">
            <Link href="/app" className="btn btn-ember">
              Open the dashboard
            </Link>
          </p>
        </>
      )
    case 'action':
      return (
        <>
          <H>GitHub Action</H>
          <P>
            .github/workflows/cascade.yml is a short file that calls
            Cascade&apos;s reusable workflow, pinned to a release (v{VERSION}).
            cascade setup and the GitHub App both write it, or you can download
            it below.
          </P>
          <P>
            It runs when a pull request changes .sql files, models/, or
            schema.yml. It comments on that PR with what is affected
            downstream. Re-runs edit the same comment. It skips Cascade&apos;s
            own stacked branches, and fails if DataHub is missing.
          </P>
          <P>
            Commenting <C>/cascade stack</C> opens a stacked PR with the
            rewritten SQL. Only the PR author and repo collaborators can
            trigger it.
          </P>
          <H2>Secrets and variables</H2>
          <ul className="mt-4 max-w-[65ch] list-disc space-y-2 pl-5 text-mute">
            <li>
              Required secret: DATAHUB_GMS_URL. Use HTTPS: runners cannot reach
              localhost.
            </li>
            <li>Optional secrets: DATAHUB_TOKEN, CASCADE_WRITEBACK.</li>
            <li>
              For AI fixes: secret LLM_API_KEY, and variables CASCADE_MODE=llm
              and LLM_MODEL. Add CASCADE_LLM_PROVIDER and LLM_BASE_URL for
              providers other than OpenAI.
            </li>
          </ul>
          <H2>Things to know</H2>
          <ul className="mt-4 max-w-[65ch] list-disc space-y-2 pl-5 text-mute">
            <li>
              The workflow can write contents and pull requests. It needs that
              to comment and to push the stacked branch. It never merges.
            </li>
            <li>
              /cascade stack only works once the workflow is on the default
              branch. GitHub runs comment-triggered workflows from there.
            </li>
            <li>
              For stacked PRs, turn on &ldquo;Allow GitHub Actions to create
              and approve pull requests&rdquo; under Settings → Actions →
              General.
            </li>
            <li>
              If your org limits which actions can run, allow himxsh/Cascade.
            </li>
          </ul>
          <p className="mt-8">
            <Link href="/cascade.yml" download="cascade.yml" className="btn btn-ember">
              Download workflow
            </Link>
          </p>
        </>
      )
    case 'rewrite':
      return (
        <>
          <H>How it edits files</H>
          <P>
            Two modes, set with CASCADE_MODE (or rewrite.mode in the config,
            or --rewrite on the command line).
          </P>
          <ul className="mt-4 max-w-[65ch] list-disc space-y-2 pl-5 text-mute">
            <li>
              <span className="font-semibold text-frost">off</span> is the
              default. Cascade reports what is affected and edits nothing.
            </li>
            <li>
              <span className="font-semibold text-frost">llm</span> makes one AI
              call that edits every affected SQL model, macro, and schema.yml
              together. It needs LLM_API_KEY and LLM_MODEL.
            </li>
          </ul>
          <P>
            There is no fallback. If the AI call fails or times out, Cascade
            posts the report without fixes. An API key alone does not turn AI
            on: the mode must be llm.
          </P>
          <P>
            In llm mode, the affected SQL is sent to the provider you chose, on
            your key.
          </P>
        </>
      )
    case 'providers':
      return (
        <>
          <H>AI models</H>
          <P>
            Set CASCADE_LLM_PROVIDER to openai (the default), anthropic,
            azure-openai, bedrock, ollama, or custom. LLM_MODEL is always
            required.
          </P>
          <P>
            anthropic, azure-openai, bedrock, and custom also need LLM_BASE_URL.
            ollama defaults to localhost, which GitHub runners cannot reach, so
            set LLM_BASE_URL for CI too.
          </P>
          <P>Cascade talks HTTP. It does not install a separate SDK per vendor.</P>
        </>
      )
    case 'datahub':
      return (
        <>
          <H>DataHub</H>
          <P>
            Set DATAHUB_GMS_URL to your DataHub GMS URL. GitHub runners cannot
            see localhost, so use HTTPS. The token needs read access. Write
            access is only needed if you ask Cascade to tag tables
            (CASCADE_WRITEBACK).
          </P>
          <P>
            DataHub has to already know your tables and what depends on them.
            With column-level lineage, Cascade narrows impact to the columns
            that changed. Without it, it falls back to table-level lineage.
          </P>
          <P>Run cascade doctor to check that DataHub is reachable.</P>
        </>
      )
    case 'cli':
      return (
        <>
          <H>Commands</H>
          <P>After install, cascade --help and cascade --version should work.</P>
          <ul className="mt-6 max-w-[65ch] space-y-3 text-mute">
            <li>
              <span className="font-semibold text-frost">setup</span> is
              first-time setup: files, DataHub check, table mapping, optional
              GitHub secrets. Flags: --demo, --non-interactive, --skip-secrets.
            </li>
            <li>
              <span className="font-semibold text-frost">init</span> only writes
              the config, example secrets file, and GitHub workflow.
            </li>
            <li>
              <span className="font-semibold text-frost">doctor</span> checks
              Python, config, table mapping, DataHub, AI settings, and (with gh)
              which Actions secrets and variables are set.
            </li>
            <li>
              <span className="font-semibold text-frost">impact</span> lists
              what is affected downstream. Add --generate to write fixes in the
              same run.
            </li>
            <li>
              <span className="font-semibold text-frost">generate</span> writes
              fixes from a report you already have.
            </li>
            <li>
              <span className="font-semibold text-frost">apply</span> writes the
              PR comment and patch locally. With --mode apply and secrets set, it
              posts the comment, and opens the stacked PR after /cascade stack.
            </li>
            <li>
              <span className="font-semibold text-frost">policy</span> fails the
              check if a stacked PR was requested but did not open.
            </li>
            <li>
              <span className="font-semibold text-frost">demo</span> runs the
              whole loop offline against a sample catalog.
            </li>
          </ul>
        </>
      )
    case 'faq':
      return (
        <>
          <H>FAQ</H>
          <H2>Does this work with my database?</H2>
          <P>
            If DataHub already knows that database, yes. Cascade never logs into
            Snowflake or BigQuery. It reads DataHub and edits SQL in git.
          </P>
          <H2>DataHub will not connect</H2>
          <P>
            Use an https URL that GitHub Actions can reach, not localhost. Run
            cascade doctor to test it.
          </P>
          <H2>Cascade did not comment on my PR</H2>
          <P>
            Check that the workflow is merged into the default branch, the PR
            changes a file Cascade watches, and the file maps to a real urn in
            .cascade/config.json. The Actions tab shows the run log.
          </P>
          <H2>/cascade stack does nothing</H2>
          <P>
            The workflow must be on the default branch, the comment must come
            from the PR author or a collaborator, and &ldquo;Allow GitHub
            Actions to create and approve pull requests&rdquo; must be on.
          </P>
          <H2>The AI call failed</H2>
          <P>
            Cascade posts the report without fixes. Check LLM_API_KEY,
            LLM_MODEL, and LLM_BASE_URL. Set CASCADE_MODE=off for report only.
          </P>
          <H2>Do I need an account?</H2>
          <P>
            No. The CLI and the AI agent prompt work without one. Sign-in is
            only for the GitHub App.
          </P>
        </>
      )
    default: {
      const _never: never = id
      return _never
    }
  }
}

export function Docs({ path }: { path: string }) {
  const current = docFromPath(path)
  return (
    <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-10 px-5 py-14 sm:px-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
      <nav aria-label="Docs" className="lg:sticky lg:top-24 lg:self-start">
        <p className="mb-3 text-sm font-semibold text-frost">Docs</p>
        <ul className="flex flex-row flex-wrap gap-2 lg:flex-col lg:gap-1">
          {NAV.map((item) => {
            const on = item.id === current
            return (
              <li key={item.id}>
                <Link
                  href={hrefFor(item.id)}
                  className={[
                    'block rounded-full px-3 py-2 text-sm',
                    on ? 'bg-panel text-frost' : 'text-mute hover:text-frost',
                  ].join(' ')}
                >
                  {item.label}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>
      <article>
        <DocBody id={current} />
      </article>
    </div>
  )
}
