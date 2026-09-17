import { useEffect, useState } from 'react'
import { copyText, PIP } from './site'

export function InstallPanel() {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const id = window.setTimeout(() => setCopied(false), 1600)
    return () => window.clearTimeout(id)
  }, [copied])

  const onCopy = async () => {
    const ok = await copyText(PIP)
    if (ok) setCopied(true)
  }

  return (
    <div className="slab overflow-hidden">
      <div className="p-5 sm:p-7">
        <p className="mb-3 text-sm leading-relaxed text-mute">
          Installs the cascade CLI. Python 3.11+.
        </p>
        <div className="flex items-stretch gap-2">
          <pre className="cmd min-w-0 flex-1 overflow-x-auto rounded-[10px] bg-void px-4 py-4 text-[0.875rem] text-frost">
            <code>{PIP}</code>
          </pre>
          <button
            type="button"
            className="btn btn-ember shrink-0 self-stretch px-4"
            onClick={() => void onCopy()}
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      </div>
    </div>
  )
}
