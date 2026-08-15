import { useEffect, useState } from 'react'
import { Chrome } from './Chrome'
import { Docs, DOC_IDS } from './Docs'
import { Home } from './Home'
import { Changelog, NotFound, Security } from './Meta'
import { pathOf } from './site'

type Page = 'home' | 'docs' | 'changelog' | 'security' | 'notfound'

function pageFor(path: string): Page {
  if (path === '/') return 'home'
  if (path === '/changelog') return 'changelog'
  if (path === '/security') return 'security'
  if (path === '/docs' || path.startsWith('/docs/')) {
    const slug = path.replace(/^\/docs\/?/, '')
    if (slug && !(DOC_IDS as readonly string[]).includes(slug)) return 'notfound'
    return 'docs'
  }
  return 'notfound'
}

function Screen({ path }: { path: string }) {
  const page = pageFor(path)
  switch (page) {
    case 'home':
      return <Home />
    case 'docs':
      return <Docs path={path} />
    case 'changelog':
      return <Changelog />
    case 'security':
      return <Security />
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

  useEffect(() => {
    const onPop = () => setPath(pathOf())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  useEffect(() => {
    const titles: Record<Page, string> = {
      home: 'Cascade',
      docs: 'Cascade · Docs',
      changelog: 'Cascade · Changelog',
      security: 'Cascade · Security',
      notfound: 'Cascade · Not found',
    }
    document.title = titles[pageFor(path)]
  }, [path])

  return (
    <Chrome path={path}>
      <Screen path={path} />
    </Chrome>
  )
}
