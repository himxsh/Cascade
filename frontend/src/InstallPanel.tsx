import { PIP } from './site'

export function InstallPanel({
  copied,
  onCopy,
}: {
  copied: boolean
  onCopy: () => void
}) {
  return (
    <div className="slab">
      <div className="p-5 sm:p-6">
        <p className="mb-3 text-[0.95rem] leading-relaxed text-frost/70">
          Install the cascade CLI. Python 3.11+.
        </p>
        <button
          type="button"
          className="flex w-full items-start gap-3 rounded-[10px] bg-void px-4 py-3.5 text-left transition-colors hover:bg-black"
          onClick={onCopy}
          aria-label={copied ? 'Copied install command' : 'Copy install command'}
        >
          <pre className="cmd min-w-0 flex-1 whitespace-pre-wrap break-all text-[0.8125rem] leading-relaxed text-frost">
            <span className="select-none text-mute">$ </span>
            <code>{PIP}</code>
          </pre>
          <span className="shrink-0 pt-0.5 text-sm font-semibold text-mute">
            {copied ? 'Copied' : 'Copy'}
          </span>
        </button>
      </div>
    </div>
  )
}
