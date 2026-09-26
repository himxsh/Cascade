import { useEffect, useState } from 'react'
import { copyText, PIP } from './site'

function CopyGlyph() {
  return (
    <svg
      viewBox="0 0 16 16"
      width="13"
      height="13"
      fill="none"
      aria-hidden="true"
    >
      <rect
        x="5.25"
        y="5.25"
        width="7.5"
        height="7.5"
        rx="1.25"
        stroke="currentColor"
        strokeWidth="1.2"
      />
      <path
        d="M10.5 5.25V3.75A1.25 1.25 0 0 0 9.25 2.5H3.75A1.25 1.25 0 0 0 2.5 3.75v5.5A1.25 1.25 0 0 0 3.75 10.5h1.5"
        stroke="currentColor"
        strokeWidth="1.2"
      />
    </svg>
  )
}

function CheckGlyph() {
  return (
    <svg
      viewBox="0 0 16 16"
      width="13"
      height="13"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M3.25 8.25 6.5 11.5 12.75 4.5"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

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
    <div className="flex justify-center">
      <button
        type="button"
        className="group inline-flex h-10 max-w-full items-center gap-2 rounded-lg border border-frost/[0.12] bg-void pl-3 pr-1.5 text-left transition-colors hover:border-frost/25"
        onClick={() => void onCopy()}
        aria-label={copied ? 'Copied install command' : 'Copy install command'}
      >
        <span className="install-cmd select-none text-ember/75" aria-hidden="true">
          $
        </span>
        <code className="install-cmd whitespace-nowrap text-frost">{PIP}</code>
        <span
          className={[
            'inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md',
            copied
              ? 'text-ember'
              : 'text-mute/80 transition-colors group-hover:bg-frost/[0.06] group-hover:text-frost',
          ].join(' ')}
          aria-live="polite"
        >
          {copied ? <CheckGlyph /> : <CopyGlyph />}
          <span className="sr-only">{copied ? 'Copied' : 'Copy'}</span>
        </span>
      </button>
    </div>
  )
}
