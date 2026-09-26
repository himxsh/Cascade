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

function P({ children }: { children: ReactNode }) {
  return <p className="mt-4 max-w-[65ch] text-mute">{children}</p>
}

function DocBody({ id }: { id: DocId }) {
  switch (id) {
    case 'get-started':
      return (
        <>
          <H>Get Cascade running</H>
          <P>
            You need SQL files in a GitHub repo, and those tables already listed
            in DataHub. Cascade does not copy tables out of your database.
          </P>
          <ol className="mt-8 space-y-6">
            <li>
              <p className="font-semibold">Install it</p>
              <P>
                Python 3.11 or newer. The install command lives on the{' '}
                <Link
                  href="/docs/install"
                  className="text-frost underline decoration-ember/70 underline-offset-4"
                >
                  Install
                </Link>{' '}
                page.
              </P>
            </li>
            <li>
              <p className="font-semibold">Create the config files</p>
              <GhCode file="terminal">cascade setup</GhCode>
              <P>
                This adds a config file, an example secrets file, and a GitHub
                workflow. It can probe DataHub and set Actions secrets. Use
                --demo if you do not have DataHub yet. It will not write a real
                .env with passwords.
              </P>
            </li>
            <li>
              <p className="font-semibold">Point it at your tables</p>
              <P>
                Open .cascade/config.json. Point your models folder at the table
                DataHub already knows. The long urn string is DataHub's name for
                that table.
              </P>
            </li>
            <li>
              <p className="font-semibold">Try it on your laptop first</p>
              <GhCode file="terminal">{`cascade impact --diff path/to.sql.diff --source live --generate --out artifacts/run
cascade apply --report artifacts/run/impact_report.json --out artifacts/apply`}</GhCode>
              <P>
                This only writes files on your laptop. The GitHub Action is what
                comments. Comment /cascade stack to open a stacked PR.
              </P>
            </li>
          </ol>
        </>
      )
    case 'install':
      return (
        <>
          <H>Install</H>
          <P>
            Cascade is a Python CLI. You need Python 3.11 or newer.
          </P>
          <GhCode file="terminal">{PIP}</GhCode>
          <P>
            That installs cascade-bot from PyPI (latest published release; the
            current one is {VERSION}). Then run cascade setup in your repo. That
            writes the config, an example secrets file, and the GitHub workflow.
            In GitHub Actions, pin a version. Do not install from main.
          </P>
          <P>
            Only add writeback if you want Cascade to leave a note on the table
            in DataHub.
          </P>
          <p className="mt-6">
            <Link href={GITHUB} className="text-frost underline decoration-ember/70 underline-offset-4">
              Source on GitHub
            </Link>
          </p>
        </>
      )
    case 'configure':
      return (
        <>
          <H>Configure</H>
          <P>
            .cascade/config.json tells Cascade which folder in git matches which
            table in DataHub. The urn field is DataHub's name for that table. It
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
  ]
}`}</GhCode>
          <P>
            If one file is a different table, list it under urn_files. Values in
            the environment override this file when both are set.
          </P>
        </>
      )
    case 'environment':
      return (
        <>
          <H>Self-hosting</H>
          <P>
            Keys for DataHub and optional AI rewrites stay in your repo .env and
            in GitHub Actions secrets. Cascade does not host them.
          </P>
          <P>
            Operator setup for the optional hosted dashboard (database URL,
            session signing, GitHub OAuth, GitHub App) lives in the repository
            contributing guide, not on this marketing site.
          </P>
          <p className="mt-6">
            <Link
              href={CONTRIBUTING}
              className="text-frost underline decoration-ember/70 underline-offset-4"
            >
              Contributing guide
            </Link>
          </p>
        </>
      )
    case 'github-app':
      return (
        <>
          <H>GitHub App</H>
          <P>
            A GitHub App can be connected later so this site can track which
            repositories you enable. Credentials stay on the server, never in
            the browser.
          </P>
          <P>
            Today, comments on pull requests come from the GitHub Action you
            add to the repo. That path does not need this dashboard.
          </P>
          <p className="mt-6">
            <Link href="/docs/action" className="btn btn-ghost">
              GitHub Action
            </Link>
          </p>
        </>
      )
    case 'action':
      return (
        <>
          <H>GitHub Action</H>
          <P>
            Add the workflow to .github/workflows. It runs when a pull request
            changes SQL files. It comments first. Comment /cascade stack to
            open a stacked PR. It skips Cascade's own stacked branches. It
            stops if DataHub is missing.
          </P>
          <P>
            The workflow needs permission to write files and to comment on pull
            requests. It will not merge.
          </P>
          <P>
            Required secrets: DATAHUB_GMS_URL, DATAHUB_TOKEN. Optional:
            LLM_API_KEY. Pin the install to a version, not main.
          </P>
          <P>
            cascade setup writes the workflow file. You can also download it.
          </P>
          <p className="mt-6">
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
            Two modes: simple rename, or an AI rewrite. Set CASCADE_MODE, or
            pass --rewrite on the command.
          </P>
          <P>
            Simple rename is the default. It swaps the old column name for the
            new one, then checks the name still exists in DataHub. No AI call.
          </P>
          <P>
            AI rewrite can handle messier SQL. It still cannot invent column
            names. If the AI times out, Cascade falls back to the simple rename.
          </P>
        </>
      )
    case 'providers':
      return (
        <>
          <H>AI models</H>
          <P>
            If you turn on AI edits, pick a provider: openai, anthropic,
            azure-openai, bedrock, ollama, or custom. You must set LLM_MODEL.
            custom also needs LLM_BASE_URL.
          </P>
          <P>Cascade talks HTTP. It does not install a separate SDK per vendor.</P>
        </>
      )
    case 'datahub':
      return (
        <>
          <H>DataHub</H>
          <P>
            Set DATAHUB_GMS_URL to your DataHub site. That is the env name
            DataHub uses. GitHub runners cannot see localhost, so use HTTPS. The
            token needs read access. Write access is only needed if you ask
            Cascade to leave a note on the table.
          </P>
          <P>
            DataHub has to already know your tables and what depends on them.
            Run cascade doctor if you are not sure the URL is reachable.
          </P>
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
              first-time setup: config, workflow, DataHub probe, optional
              GitHub secrets. --demo skips live DataHub.
            </li>
            <li>
              <span className="font-semibold text-frost">init</span> only writes
              the config, example secrets file, and GitHub workflow.
            </li>
            <li>
              <span className="font-semibold text-frost">doctor</span> checks
              Python, config, DataHub, and (if needed) the AI endpoint.
            </li>
            <li>
              <span className="font-semibold text-frost">impact</span> lists
              which files still use the old column. Add --generate to edit them
              in the same run.
            </li>
            <li>
              <span className="font-semibold text-frost">generate</span> edits
              files from a report you already have.
            </li>
            <li>
              <span className="font-semibold text-frost">apply</span> comments on
              the original pull request. A stacked PR opens only if someone
              comments /cascade stack. By default it only writes local files.
            </li>
            <li>
              <span className="font-semibold text-frost">policy</span> fails the
              GitHub check if a stacked PR was requested but did not open.
            </li>
            <li>
              <span className="font-semibold text-frost">demo</span> is for
              Cascade developers. You do not need it to install.
            </li>
          </ul>
        </>
      )
    case 'faq':
      return (
        <>
          <H>FAQ</H>
          <h2 className="mt-8 text-xl font-semibold">Does this work with my database?</h2>
          <P>
            If DataHub already knows that database, yes. Cascade never logs into
            Snowflake or BigQuery. It reads DataHub and edits SQL in git.
          </P>
          <h2 className="mt-8 text-xl font-semibold">DataHub will not connect</h2>
          <P>
            Use an https URL that GitHub Actions can reach, not localhost. Run
            cascade doctor to test it.
          </P>
          <h2 className="mt-8 text-xl font-semibold">It cannot find the table</h2>
          <P>
            The changed file path must match a folder in .cascade/config.json.
            Or pass --urn. That flag is DataHub's name for the table.
          </P>
          <h2 className="mt-8 text-xl font-semibold">The AI timed out</h2>
          <P>
            Cascade falls back to the simple rename. Set CASCADE_MODE=deterministic
            if you do not want AI at all.
          </P>
          <h2 className="mt-8 text-xl font-semibold">Do I need an account?</h2>
          <P>
            No. Install the CLI and add the GitHub Action to your repo. Sign-in
            on this site is optional.
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
