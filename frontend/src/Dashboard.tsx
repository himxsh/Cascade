import { useEffect, useState } from 'react'
import {
  fetchAuthConfig,
  fetchRepos,
  patchRepo,
  type AuthConfig,
  type Me,
  type Repo,
} from './api'
import { Link } from './Link'
import { pathOf } from './site'

type Tab = 'overview' | 'repos' | 'connect'

function tabFor(path: string): Tab {
  if (path.endsWith('/repos') || path.endsWith('/repositories')) return 'repos'
  if (path.endsWith('/connect')) return 'connect'
  return 'overview'
}

function hrefFor(tab: Tab): string {
  switch (tab) {
    case 'overview':
      return '/app'
    case 'repos':
      return '/app/repos'
    case 'connect':
      return '/app/connect'
    default: {
      const _never: never = tab
      return _never
    }
  }
}

function Banner({ children }: { children: string }) {
  return (
    <p className="slab border-ember/30 px-4 py-3 text-sm text-mute" role="status">
      {children}
    </p>
  )
}

function Toggle({
  checked,
  onToggle,
  label,
}: {
  checked: boolean
  onToggle: () => void
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={['toggle', checked ? 'toggle-on' : ''].filter(Boolean).join(' ')}
      onClick={onToggle}
    >
      <span className="toggle-knob" />
    </button>
  )
}

export function Dashboard({ me }: { me: Me }) {
  const [path, setPath] = useState(pathOf)
  const [config, setConfig] = useState<AuthConfig | null>(null)
  const [repos, setRepos] = useState<Repo[] | null>(null)
  const [mock, setMock] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const tab = tabFor(path)
  const banner = config?.banner || me.banner

  useEffect(() => {
    const onPop = () => setPath(pathOf())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  useEffect(() => {
    void fetchAuthConfig().then(setConfig).catch(() => setConfig(null))
  }, [])

  useEffect(() => {
    let cancelled = false
    void fetchRepos()
      .then((data) => {
        if (cancelled) return
        setRepos(data.repos)
        setMock(data.mock)
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Could not load repositories')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const onToggle = async (repo: Repo) => {
    setBusyId(repo.id)
    setError(null)
    try {
      const updated = await patchRepo(repo.id, !repo.enabled)
      setRepos((current) =>
        (current ?? []).map((item) => (item.id === updated.id ? updated : item)),
      )
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not update repository')
    } finally {
      setBusyId(null)
    }
  }

  const enabledCount = (repos ?? []).filter((r) => r.enabled).length
  const installUrl = me.app_install_url || config?.app_install_url
  const installed = (me.installations ?? []).some((i) => i.installation_id > 0)

  return (
    <div className="mx-auto max-w-[1120px] px-5 py-12 sm:px-6">
      <p className="text-sm font-semibold tracking-wide text-mute">Dashboard</p>
      <h1 className="display mt-2 text-[clamp(2rem,4vw,2.75rem)]">
        {tab === 'overview' ? 'Overview' : tab === 'repos' ? 'Repositories' : 'Connect GitHub'}
      </h1>
      <p className="mt-3 max-w-[62ch] text-mute">
        Signed in as {me.login}
        {me.dev ? ' (local test user)' : ''}. Enable a repo here before Cascade
        will process its pull requests.
      </p>

      <nav className="mt-8 flex flex-wrap gap-2" aria-label="Dashboard">
        {([
          ['overview', 'Overview'],
          ['repos', 'Repositories'],
          ['connect', 'Connect GitHub'],
        ] as const).map(([id, label]) => {
          const on = tab === id
          return (
            <Link
              key={id}
              href={hrefFor(id)}
              className={[
                'rounded-full px-4 py-2 text-sm font-medium',
                on ? 'bg-panel text-frost' : 'text-mute hover:text-frost',
              ].join(' ')}
            >
              {label}
            </Link>
          )
        })}
      </nav>

      <div className="mt-8 space-y-4">
        {banner ? <Banner>{banner}</Banner> : null}
        {error ? (
          <p className="slab px-4 py-3 text-sm text-frost" role="alert">
            {error}
          </p>
        ) : null}
      </div>

      {tab === 'overview' ? (
        <section className="mt-10 grid gap-4 sm:grid-cols-3">
          <article className="slab p-5">
            <p className="text-sm text-mute">GitHub identity</p>
            <p className="mt-2 text-lg font-semibold">{me.login}</p>
          </article>
          <article className="slab p-5">
            <p className="text-sm text-mute">App install</p>
            <p className="mt-2 text-lg font-semibold">
              {installed ? 'Installed' : config?.app_configured ? 'Not installed' : 'Not configured'}
            </p>
          </article>
          <article className="slab p-5">
            <p className="text-sm text-mute">Repos enabled</p>
            <p className="mt-2 text-lg font-semibold">
              {repos ? `${enabledCount} / ${repos.length}` : `${me.enabled_count} / ${me.repo_count}`}
            </p>
          </article>
          <div className="sm:col-span-3 mt-4 flex flex-wrap gap-3">
            <Link href="/app/repos" className="btn btn-ember">
              Choose repositories
            </Link>
            <Link href="/app/connect" className="btn btn-ghost">
              Connect GitHub App
            </Link>
          </div>
        </section>
      ) : null}

      {tab === 'repos' ? (
        <section className="mt-10">
          {mock ? (
            <p className="mb-4 text-sm text-mute">
              Showing a mock list so you can persist enable/disable without a live
              GitHub App installation token.
            </p>
          ) : null}
          {repos === null ? (
            <p className="text-mute">Loading repositories…</p>
          ) : repos.length === 0 ? (
            <div className="slab p-6">
              <p className="font-semibold">No repositories yet</p>
              <p className="mt-2 text-sm text-mute">
                Install the Cascade GitHub App, then return here to enable the
                repos that should get replies.
              </p>
              <Link href="/app/connect" className="btn btn-ember mt-5">
                Connect GitHub
              </Link>
            </div>
          ) : (
            <ul className="slab divide-y divide-line overflow-hidden">
              {repos.map((repo) => (
                <li key={repo.id} className="flex items-center justify-between gap-4 px-5 py-4">
                  <div>
                    <p className="font-semibold">{repo.full_name}</p>
                    <p className="text-sm text-mute">
                      {repo.enabled ? 'Cascade will process this repo' : 'Ignored until enabled'}
                    </p>
                  </div>
                  <Toggle
                    checked={repo.enabled}
                    label={`${repo.enabled ? 'Disable' : 'Enable'} ${repo.full_name}`}
                    onToggle={() => {
                      if (busyId === repo.id) return
                      void onToggle(repo)
                    }}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {tab === 'connect' ? (
        <section className="mt-10 max-w-[62ch] space-y-5">
          <p className="text-mute">
            Installing the Cascade GitHub App grants pull request and contents
            access so comments post as Cascade (logo avatar), not
            github-actions[bot]. Per-repo behavior still comes from .cascade/ in
            the repository. This site only decides whether a repo is enabled.
          </p>
          {installUrl ? (
            <a href={installUrl} className="btn btn-ember">
              Install Cascade App
            </a>
          ) : (
            <p className="slab px-4 py-3 text-sm text-mute">
              GITHUB_APP_SLUG is not set, so there is no install URL yet. After
              you create the App on github.com, set the slug and secrets from
              .env.example. The setup callback at /api/github/setup will store
              the installation id.
            </p>
          )}
          <p className="text-sm text-mute">
            Setup URL for the App registration:{' '}
            <code className="cmd text-frost">/api/github/setup</code>
          </p>
          <Link href="/docs/github-app" className="text-frost underline decoration-ember/70 underline-offset-4">
            GitHub App (when ready)
          </Link>
        </section>
      ) : null}
    </div>
  )
}
