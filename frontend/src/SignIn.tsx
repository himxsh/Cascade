import { useEffect, useState } from 'react'
import { fetchAuthConfig, type AuthConfig } from './api'
import { GitHubMark } from './Link'

export function SignIn() {
  const [config, setConfig] = useState<AuthConfig | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [nextPath, setNextPath] = useState('/app')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const reason = params.get('reason')
    const next = params.get('next')
    if (next && next.startsWith('/') && !next.startsWith('//')) {
      setNextPath(next)
    }
    if (reason) setError(reason.replaceAll('_', ' '))
    void fetchAuthConfig()
      .then(setConfig)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Could not load sign-in options')
      })
  }, [])

  const nextQuery = `?next=${encodeURIComponent(nextPath)}`

  return (
    <article className="mx-auto max-w-[36rem] px-5 py-16 sm:px-6">
      <h1 className="display text-[clamp(2rem,4vw,2.75rem)]">Sign in</h1>
      <p className="mt-4 text-mute">
        Cascade uses GitHub to know who is enabling repositories. The GitHub App
        (comments as Cascade) is separate and can be installed after you sign in.
      </p>

      {error ? (
        <p className="slab mt-6 px-4 py-3 text-sm text-frost" role="alert">
          {error}
        </p>
      ) : null}

      <div className="mt-8 flex flex-col gap-3">
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
        {config && !config.oauth_configured && !config.dev_login ? (
          <p className="slab px-4 py-3 text-sm text-mute">
            Sign-in is not configured. Set GITHUB_OAUTH_CLIENT_ID and
            GITHUB_OAUTH_CLIENT_SECRET, or CASCADE_DEV_LOGIN=1 for local
            development. See .env.example.
          </p>
        ) : null}
      </div>

      {config?.dev_login && !config.oauth_configured ? (
        <p className="mt-6 text-sm text-mute">
          OAuth client secrets are not set. The local test login creates an
          HTTP-only session for user “dev” so the dashboard and repo toggles
          can be exercised without a GitHub App.
        </p>
      ) : null}
    </article>
  )
}
