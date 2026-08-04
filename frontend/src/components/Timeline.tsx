const STEPS = ['classify', 'impact', 'reason', 'rewrite', 'write-back'] as const

type Props = {
  activeIndex: number
  done: boolean
  running: boolean
}

export function Timeline({ activeIndex, done, running }: Props) {
  return (
    <ol className="flex flex-wrap items-center gap-x-1 gap-y-2 font-mono text-[11px] tracking-wide uppercase text-muted">
      {STEPS.map((step, i) => {
        const isDone = done || i < activeIndex
        const isCurrent = running && i === activeIndex && !done
        return (
          <li key={step} className="flex items-center gap-1">
            {i > 0 && <span className="mx-1 text-line" aria-hidden="true">→</span>}
            <span
              className={[
                'transition-colors duration-300',
                isDone ? 'text-fg' : '',
                isCurrent ? 'text-accent' : '',
              ].join(' ')}
            >
              <span
                className={[
                  'mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle transition-colors duration-300',
                  isDone ? 'bg-low' : isCurrent ? 'bg-accent animate-pulse' : 'bg-line',
                ].join(' ')}
              />
              {step}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
