import { useEffect, useState } from 'react'
import { copyText, PIP } from './site'

function CopyGlyph() {
  return (
    <svg
      viewBox="0 0 16 16"
      width="14"
      height="14"
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
      width="14"
      height="14"
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

const PROMPT_PATH = '/install.md'

function useCopied() {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const id = window.setTimeout(() => setCopied(false), 1600)
    return () => window.clearTimeout(id)
  }, [copied])
  return [copied, setCopied] as const
}

function CopyState({ copied }: { copied: boolean }) {
  return (
    <span
      className={[
        'flex shrink-0 items-center gap-1.5 text-[0.68rem] tracking-wide',
        copied
          ? 'text-ember'
          : 'text-mute/80 transition-colors group-hover:text-frost',
      ].join(' ')}
      aria-live="polite"
    >
      {copied ? <CheckGlyph /> : <CopyGlyph />}
      {copied ? 'Copied' : 'Copy'}
    </span>
  )
}

const ROW =
  'group flex w-full items-center gap-3 rounded-lg border border-frost/[0.1] bg-ink px-3.5 py-2.5 text-left transition-colors hover:border-frost/20 hover:bg-void'

export function InstallPanel() {
  const [pipCopied, setPipCopied] = useCopied()
  const [promptCopied, setPromptCopied] = useCopied()
  const [prompt, setPrompt] = useState<string | null>(null)

  // Fetched up front so the copy runs inside the click (Safari drops
  // clipboard writes that happen after an await on the network).
  useEffect(() => {
    let live = true
    fetch(PROMPT_PATH)
      .then((r) => (r.ok ? r.text() : null))
      .then((t) => live && setPrompt(t))
      .catch(() => {})
    return () => {
      live = false
    }
  }, [])

  const onCopyPip = async () => {
    if (await copyText(PIP)) setPipCopied(true)
  }

  const onCopyPrompt = async () => {
    const text =
      prompt ??
      `Install Cascade in this repository by following ${window.location.origin}${PROMPT_PATH}`
    if (await copyText(text)) setPromptCopied(true)
  }

  return (
    <div className="mx-auto w-full max-w-[22.5rem] space-y-2.5">
      <button
        type="button"
        className={ROW}
        onClick={() => void onCopyPip()}
        aria-label={pipCopied ? 'Copied install command' : 'Copy install command'}
      >
        <span className="cmd select-none text-ember/80" aria-hidden="true">
          $
        </span>
        <code className="cmd min-w-0 flex-1 whitespace-pre-wrap break-all text-[0.8125rem] leading-relaxed text-frost">
          {PIP}
        </code>
        <CopyState copied={pipCopied} />
      </button>

      <button
        type="button"
        className={ROW}
        onClick={() => void onCopyPrompt()}
        aria-label={
          promptCopied ? 'Copied AI agent install prompt' : 'Copy AI agent install prompt'
        }
      >
        <span className="cmd select-none text-ember/80" aria-hidden="true">
          &gt;
        </span>
        <span className="min-w-0 flex-1 text-[0.8125rem] leading-relaxed text-frost">
          Install with an AI agent
        </span>
        <CopyState copied={promptCopied} />
      </button>

      <p className="px-1 text-center text-[0.72rem] leading-relaxed text-mute/80">
        Paste the prompt into Claude Code, Cursor, or Codex in your repo.{' '}
        <a
          href={PROMPT_PATH}
          target="_blank"
          rel="noreferrer"
          className="text-frost/80 underline decoration-ember/60 underline-offset-4 hover:text-frost"
        >
          Read it first
        </a>
      </p>
    </div>
  )
}
