import Lenis from 'lenis'

export const GITHUB = 'https://github.com/himxsh/Cascade'
export const ACTION_FILE =
  'https://github.com/himxsh/Cascade/blob/main/examples/github-action/cascade.yml'
export const LICENSE = 'https://github.com/himxsh/Cascade/blob/main/LICENSE'

export const NPX = 'npx create-cascade@latest'
export const PIP =
  'pip install "cascade-agent @ git+https://github.com/himxsh/Cascade.git"'
export const GH_CURL =
  'mkdir -p .github/workflows && curl -fsSL https://raw.githubusercontent.com/himxsh/Cascade/main/examples/github-action/cascade.yml -o .github/workflows/cascade.yml'

export const WORKFLOW_HREF = '/cascade.yml'

export type InstallTab = 'npx' | 'pip' | 'github'

export function installCopy(tab: InstallTab): string {
  switch (tab) {
    case 'npx':
      return NPX
    case 'pip':
      return PIP
    case 'github':
      return GH_CURL
    default: {
      const _never: never = tab
      return _never
    }
  }
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    const el = document.createElement('textarea')
    el.value = text
    el.setAttribute('readonly', '')
    el.style.position = 'fixed'
    el.style.left = '-9999px'
    document.body.appendChild(el)
    el.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(el)
    return ok
  }
}

export function pathOf(): string {
  return window.location.pathname.replace(/\/+$/, '') || '/'
}

const lenis = new Lenis({
  autoRaf: true,
  anchors: true,
  allowNestedScroll: true,
  stopInertiaOnNavigate: true,
})

if (import.meta.hot) import.meta.hot.dispose(() => lenis.destroy())

export function go(href: string): void {
  const url = new URL(href, window.location.origin)
  const next = url.pathname.replace(/\/+$/, '') || '/'
  const hash = url.hash
  if (pathOf() !== next) {
    history.pushState(null, '', next + hash)
    window.dispatchEvent(new PopStateEvent('popstate'))
  } else if (hash) {
    history.pushState(null, '', next + hash)
  }
  if (hash) lenis.scrollTo(hash)
  else lenis.scrollTo(0, { immediate: true })
}
