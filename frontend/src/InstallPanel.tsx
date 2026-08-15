import { useEffect, useId, useState } from 'react'
import { Link } from './Link'
import {
  ACTION_FILE,
  copyText,
  installCopy,
  type InstallTab,
  WORKFLOW_HREF,
} from './site'

const TABS: { id: InstallTab; label: string }[] = [
  { id: 'npx', label: 'npx' },
  { id: 'pip', label: 'pip' },
  { id: 'github', label: 'GitHub' },
]

function hint(tab: InstallTab): string {
  switch (tab) {
    case 'npx':
      return 'Scaffolds config and the Action. Python 3.11+.'
    case 'pip':
      return 'Installs the cascade CLI.'
    case 'github':
      return 'Runs on pull requests that touch SQL.'
    default: {
      const _never: never = tab
      return _never
    }
  }
}

export function InstallPanel() {
  const [tab, setTab] = useState<InstallTab>('npx')
  const [copied, setCopied] = useState(false)
  const tabId = useId()
  const command = installCopy(tab)

  useEffect(() => {
    if (!copied) return
    const id = window.setTimeout(() => setCopied(false), 1600)
    return () => window.clearTimeout(id)
  }, [copied])

  const onCopy = async () => {
    const ok = await copyText(command)
    if (ok) setCopied(true)
  }

  return (
    <div className="slab overflow-hidden">
      <div className="flex border-b border-line" role="tablist" aria-label="Install method">
        {TABS.map((t) => {
          const selected = t.id === tab
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              id={`${tabId}-${t.id}`}
              aria-selected={selected}
              aria-controls={`${tabId}-panel`}
              className={[
                'flex-1 px-3 py-3 text-sm font-semibold transition-colors duration-150',
                selected
                  ? 'bg-void text-frost'
                  : 'text-mute hover:text-frost',
              ].join(' ')}
              style={{ transitionTimingFunction: 'var(--ease-out)' }}
              onClick={() => {
                setTab(t.id)
                setCopied(false)
              }}
            >
              <span
                className={[
                  'inline-block border-b-2 pb-0.5',
                  selected ? 'border-ember' : 'border-transparent',
                ].join(' ')}
              >
                {t.label}
              </span>
            </button>
          )
        })}
      </div>

      <div
        id={`${tabId}-panel`}
        role="tabpanel"
        aria-labelledby={`${tabId}-${tab}`}
        className="p-4 sm:p-5"
      >
        <p className="mb-3 text-sm leading-relaxed text-mute">{hint(tab)}</p>
        <div className="flex items-stretch gap-2">
          <pre className="cmd min-w-0 flex-1 overflow-x-auto rounded-[10px] bg-void px-3 py-3 text-frost">
            <code>{command}</code>
          </pre>
          <button
            type="button"
            className={['btn shrink-0 self-stretch px-4', tab === 'github' ? 'btn-ghost' : 'btn-ember'].join(' ')}
            onClick={() => void onCopy()}
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>

        {tab === 'github' ? (
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              href={WORKFLOW_HREF}
              download="cascade.yml"
              className="btn btn-ember"
            >
              Download workflow
            </Link>
            <Link href={ACTION_FILE} className="btn btn-ghost">
              View on GitHub
            </Link>
          </div>
        ) : null}
      </div>
    </div>
  )
}
