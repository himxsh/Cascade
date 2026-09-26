import type { ReactNode } from 'react'
import type { Me } from './api'
import { Link, GitHubMark } from './Link'
import { GITHUB, LICENSE } from './site'

export function Chrome({
  path,
  children,
  me,
  authReady,
}: {
  path: string
  children: ReactNode
  me: Me | null
  authReady: boolean
}) {
  const docsOn = path === '/docs' || path.startsWith('/docs/')
  const appOn = path === '/app' || path.startsWith('/app/') || path === '/dashboard' || path.startsWith('/dashboard/')

  return (
    <div className="min-h-[100dvh] bg-void text-frost">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <div className="sticky top-3 z-[var(--z-sticky)] px-3">
        <header className="nav-island mx-auto flex h-14 max-w-[1120px] items-center gap-3 px-3 sm:px-4">
          <Link href="/" className="flex items-center pr-1">
            <span className="display text-[1.35rem] leading-none tracking-[-0.03em]">
              Cascade
            </span>
          </Link>
          <nav className="ml-auto flex items-center gap-0.5 text-sm font-medium sm:gap-1">
            <Link
              href="/docs"
              className={[
                'rounded-full px-2 py-2 sm:px-3',
                docsOn ? 'text-frost' : 'text-mute hover:text-frost',
              ].join(' ')}
            >
              Docs
            </Link>
            <Link
              href="/changelog"
              className={[
                'rounded-full px-2 py-2 sm:px-3',
                path === '/changelog' ? 'text-frost' : 'text-mute hover:text-frost',
              ].join(' ')}
            >
              Changelog
            </Link>
            {authReady && me ? (
              <Link
                href="/app"
                className={[
                  'rounded-full px-3 py-2',
                  appOn ? 'text-frost' : 'text-mute hover:text-frost',
                ].join(' ')}
              >
                App
              </Link>
            ) : null}
            <Link
              href={GITHUB}
              className="btn btn-ghost ml-1 h-9 min-h-0 gap-1.5 px-2 py-0 text-sm sm:px-3"
            >
              <GitHubMark />
              <span className="sr-only sm:not-sr-only sm:inline">GitHub</span>
            </Link>
            {authReady && me ? (
              <>
                {me.avatar_url ? (
                  <img
                    src={me.avatar_url}
                    alt=""
                    className="ml-1 h-8 w-8 rounded-full"
                  />
                ) : (
                  <span className="ml-1 flex h-8 w-8 items-center justify-center rounded-full bg-panel text-xs font-semibold">
                    {me.login.slice(0, 1).toUpperCase()}
                  </span>
                )}
                <a href="/auth/logout" className="rounded-full px-3 py-2 text-mute hover:text-frost">
                  Sign out
                </a>
              </>
            ) : null}
            {authReady && !me ? (
              <Link
                href="/signin"
                className="rounded-full px-2 py-2 text-mute hover:text-frost sm:px-3"
              >
                Sign in
              </Link>
            ) : null}
          </nav>
        </header>
      </div>

      <div id="main">{children}</div>

      <footer className="reveal mx-auto mt-8 max-w-[1120px] px-5 pb-12 pt-10 sm:px-6">
        <div className="hairline mb-8 h-px" />
        <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="display text-2xl tracking-[-0.03em]">Cascade</p>
            <p className="mt-2 max-w-[36ch] text-sm text-mute">
              A GitHub Action that rewrites SQL after schema changes.
            </p>
          </div>
          <ul className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-mute">
            <li>
              <Link href="/docs" className="hover:text-frost">
                Docs
              </Link>
            </li>
            <li>
              <Link href="/app" className="hover:text-frost">
                App
              </Link>
            </li>
            <li>
              <Link href="/changelog" className="hover:text-frost">
                Changelog
              </Link>
            </li>
            <li>
              <Link href={GITHUB} className="hover:text-frost">
                GitHub
              </Link>
            </li>
            <li>
              <Link href={LICENSE} className="hover:text-frost">
                Apache-2.0
              </Link>
            </li>
            <li>
              <Link href="/security" className="hover:text-frost">
                Security
              </Link>
            </li>
          </ul>
        </div>
      </footer>
    </div>
  )
}
