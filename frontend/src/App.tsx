import { useEffect, useState } from 'react'
import { fetchMe, type Me } from './api'
import { Chrome } from './Chrome'
import { Dashboard } from './Dashboard'
import { Docs, DOC_IDS } from './Docs'
import { Home } from './Home'
import { Changelog, NotFound, Security } from './Meta'
import { SignIn } from './SignIn'
import { go, pathOf } from './site'

type Page = 'home' | 'docs' | 'changelog' | 'security' | 'app' | 'signin' | 'notfound'

function pageFor(path: string): Page {
  if (path === '/') return 'home'
  if (path === '/changelog') return 'changelog'
  if (path === '/security') return 'security'
  if (path === '/signin' || path === '/login') return 'signin'
  if (
    path === '/app' ||
    path.startsWith('/app/') ||
    path === '/dashboard' ||
    path.startsWith('/dashboard/')
  ) {
    return 'app'
  }
  if (path === '/docs' || path.startsWith('/docs/')) {
    const slug = path.replace(/^\/docs\/?/, '')
    if (slug && !(DOC_IDS as readonly string[]).includes(slug)) return 'notfound'
    return 'docs'
  }
  return 'notfound'
}

function Screen({
  path,
  page,
  me,
  authReady,
}: {
  path: string
  page: Page
  me: Me | null
  authReady: boolean
}) {
  switch (page) {
    case 'home':
      return <Home />
    case 'docs':
      return <Docs path={path} />
    case 'changelog':
      return <Changelog />
    case 'security':
      return <Security />
    case 'signin':
      return <SignIn />
    case 'app':
      return me ? (
        <Dashboard me={me} />
      ) : (
        <p className="mx-auto max-w-[65ch] px-5 py-24 text-mute">
          {authReady ? 'Redirecting to sign in…' : 'Loading…'}
        </p>
      )
    case 'notfound':
      return <NotFound />
    default: {
      const _never: never = page
      return _never
    }
  }
}

export default function App() {
  const [path, setPath] = useState(pathOf)
  const [me, setMe] = useState<Me | null>(null)
  const [authReady, setAuthReady] = useState(false)

  useEffect(() => {
    const onPop = () => setPath(pathOf())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  useEffect(() => {
    let cancelled = false
    void fetchMe()
      .then((user) => {
        if (!cancelled) setMe(user)
      })
      .catch(() => {
        if (!cancelled) setMe(null)
      })
      .finally(() => {
        if (!cancelled) setAuthReady(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const page = pageFor(path)

  useEffect(() => {
    if (!authReady) return
    if (page === 'app' && !me) {
      const next = encodeURIComponent(path + window.location.search)
      go(`/signin?next=${next}`)
      return
    }
    if (page === 'signin' && me) {
      const params = new URLSearchParams(window.location.search)
      const next = params.get('next')
      if (next && next.startsWith('/') && !next.startsWith('//')) {
        if (next.startsWith('/api/') || next.startsWith('/auth/')) {
          window.location.assign(next)
          return
        }
        go(next)
        return
      }
      go('/app')
    }
  }, [authReady, page, me])

  useEffect(() => {
    const titles: Record<Page, string> = {
      home: 'Cascade',
      docs: 'Cascade · Docs',
      changelog: 'Cascade · Changelog',
      security: 'Cascade · Security',
      app: 'Cascade · App',
      signin: 'Cascade · Sign in',
      notfound: 'Cascade · Not found',
    }
    document.title = titles[pageFor(path)]
  }, [path])

  return (
    <Chrome path={path} me={me} authReady={authReady}>
      <Screen path={path} page={page} me={me} authReady={authReady} />
    </Chrome>
  )
}
