import { useMemo, useState } from 'react'
import type { DiffFile } from '../types'

type Props = {
  files: DiffFile[]
  selectedPath?: string | null
  revealed: boolean
}

type Line = { kind: 'ctx' | 'add' | 'del'; text: string }

function unifiedLines(before: string, after: string): Line[] {
  const a = before.split('\n')
  const b = after.split('\n')
  // ponytail: O(n²) LCS fine for demo SQL files; upgrade to Myers if patches grow
  const n = a.length
  const m = b.length
  const dp: number[][] = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const out: Line[] = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push({ kind: 'ctx', text: a[i] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ kind: 'del', text: a[i++] })
    } else {
      out.push({ kind: 'add', text: b[j++] })
    }
  }
  while (i < n) out.push({ kind: 'del', text: a[i++] })
  while (j < m) out.push({ kind: 'add', text: b[j++] })
  return out
}

export function DiffViewer({ files, selectedPath, revealed }: Props) {
  const [mode, setMode] = useState<'split' | 'unified'>('split')
  const [idx, setIdx] = useState(0)

  const activeIndex = useMemo(() => {
    if (selectedPath) {
      const i = files.findIndex((f) => f.path === selectedPath || f.path.endsWith(selectedPath))
      if (i >= 0) return i
    }
    return Math.min(idx, Math.max(files.length - 1, 0))
  }, [files, selectedPath, idx])

  const file = files[activeIndex]

  if (!files.length) {
    return (
      <div className="border border-line bg-panel p-3 font-mono text-xs text-muted">
        No rewritten SQL files in this run.
      </div>
    )
  }

  if (!file) return null

  const lines = unifiedLines(file.before, file.after)

  return (
    <div
      className={[
        'border border-line bg-panel transition-opacity duration-300',
        revealed ? 'opacity-100' : 'opacity-40',
      ].join(' ')}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
        <div className="flex flex-wrap gap-1">
          {files.map((f, i) => (
            <button
              key={f.path}
              type="button"
              onClick={() => setIdx(i)}
              className={[
                'font-mono text-[11px] px-2 py-0.5 border transition-colors',
                i === activeIndex
                  ? 'border-accent text-fg bg-raised'
                  : 'border-line text-muted hover:text-fg',
              ].join(' ')}
            >
              {f.path.split('/').pop()}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {(['split', 'unified'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={[
                'font-mono text-[10px] uppercase tracking-wide px-2 py-0.5 border',
                mode === m ? 'border-fg text-fg' : 'border-line text-muted',
              ].join(' ')}
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      <div className="px-3 py-1 font-mono text-[10px] text-muted break-all">{file.path}</div>
      {mode === 'split' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 border-t border-line">
          <pre className="overflow-auto max-h-64 p-3 font-mono text-[11px] leading-relaxed border-b md:border-b-0 md:border-r border-line text-muted">
            <div className="mb-2 text-[10px] uppercase tracking-wider">before</div>
            {file.before}
          </pre>
          <pre className="overflow-auto max-h-64 p-3 font-mono text-[11px] leading-relaxed text-fg">
            <div className="mb-2 text-[10px] uppercase tracking-wider text-muted">after</div>
            {file.after}
          </pre>
        </div>
      ) : (
        <pre className="overflow-auto max-h-64 border-t border-line p-0 font-mono text-[11px] leading-relaxed">
          {lines.map((l, i) => (
            <div
              key={i}
              className={[
                'px-3 whitespace-pre',
                l.kind === 'add' ? 'bg-low/15 text-fg' : '',
                l.kind === 'del' ? 'bg-critical/15 text-fg' : 'text-muted',
              ].join(' ')}
            >
              <span className="mr-2 inline-block w-3 text-muted">
                {l.kind === 'add' ? '+' : l.kind === 'del' ? '-' : ' '}
              </span>
              {l.text}
            </div>
          ))}
        </pre>
      )}
    </div>
  )
}
