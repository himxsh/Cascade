import { useEffect, useState } from 'react'
import { fetchAuthConfig, type AuthConfig } from './api'
import { Link, GitHubMark } from './Link'
import { GITHUB } from './site'

export function SignIn() {
  const [config, setConfig] = useState<AuthConfig | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [configFailed, setConfigFailed] = useState(false)
  const [nextPath, setNextPath] = useState('/app')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const reason = params.get('reason')
    const next = params.get('next')
    if (next && next.startsWith('/') && !next.startsWith('//')) {
      setNextPath(next)
    }
    if (reason && reason !== 'oauth_unconfigured') {
      setError(reason.replaceAll('_', ' '))
    }
    void fetchAuthConfig()
      .then((cfg) => {
        setConfig(cfg)
        setConfigFailed(false)
      })
      .catch(() => {
        setConfig(null)
        setConfigFailed(true)
      })
  }, [])

  const nextQuery = `?next=${encodeURIComponent(nextPath)}`
  const signInReady = Boolean(config?.oauth_configured || config?.dev_login)

  return (
    <article className="mx-auto max-w-[36rem] px-5 py-16 sm:px-6">
      <h1 className="display text-[clamp(2rem,4vw,2.75rem)]">Sign in</h1>

      {error ? (
        <p className="slab mt-6 px-4 py-3 text-sm text-frost" role="alert">
          {error}
        </p>
      ) : null}

      {configFailed ? (
        <p className="mt-8 text-mute" role="alert">
          Could not check whether sign-in is available. Refresh the page to try
          again.
        </p>
      ) : null}

      {config && !signInReady ? (
        <div className="mt-8">
          <p className="text-lg text-frost">Sign-in isn't available yet</p>
          <p className="mt-3 text-mute">
            Coming soon. You can install Cascade and use the GitHub Action
            without an account.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/docs" className="btn btn-ember">
              Docs
            </Link>
            <Link href={GITHUB} className="btn btn-ghost">
              <GitHubMark />
              GitHub
            </Link>
          </div>
        </div>
      ) : null}

      {signInReady ? (
        <div className="mt-8 flex flex-col gap-3">
          <p className="text-mute">
            Cascade uses GitHub to know who is enabling repositories.
          </p>
          {config?.oauth_configured ? (
            <a href={`/auth/github${nextQuery}`} className="btn btn-ember">
              <GitHubMark />
              Sign in with GitHub
            </a>
          ) : null}
          {config?.dev_login ? (
            <a href={`/auth/dev-login${nextQuery}`} className="btn btn-ghost">
              Continue with local test login
            </a>
          ) : null}
        </div>
      ) : null}
    </article>
  )
}
