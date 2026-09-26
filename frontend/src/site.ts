import Lenis from 'lenis'

export const GITHUB = 'https://github.com/himxsh/Cascade'
export const LICENSE = 'https://github.com/himxsh/Cascade/blob/main/LICENSE'

export const PIP = 'pip install cascade-bot'

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
  const search = url.search
  const dest = next + search + hash
  const same = pathOf() === next && window.location.search === search
  if (!same) {
    history.pushState(null, '', dest)
    window.dispatchEvent(new PopStateEvent('popstate'))
  } else if (hash) {
    history.pushState(null, '', dest)
  }
  if (hash) lenis.scrollTo(hash)
  else lenis.scrollTo(0, { immediate: true })
}
