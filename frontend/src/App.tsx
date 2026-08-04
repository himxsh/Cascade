import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchDemoDiff, runPipeline } from './api'
import { BlastGraph } from './components/BlastGraph'
import { DiffViewer } from './components/DiffViewer'
import { NodeDetail } from './components/NodeDetail'
import { Timeline } from './components/Timeline'
import { WritebackPanel } from './components/WritebackPanel'
import type { RunResult, SourceMode } from './types'

const DEFAULT_URN =
  'urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)'
const GITHUB_REPO = 'https://github.com/himxsh/Cascade'

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      width="16"
      height="16"
      aria-hidden="true"
      fill="currentColor"
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  )
}

function severityClass(severity: string): string {
  const s = severity.toLowerCase()
  if (s === 'critical') return 'text-critical border-critical'
  if (s === 'high') return 'text-high border-high'
  if (s === 'medium') return 'text-medium border-medium'
  return 'text-low border-low'
}

function downloadText(filename: string, text: string) {
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function App() {
  const [diff, setDiff] = useState('')
  const [urn, setUrn] = useState(DEFAULT_URN)
  const [source, setSource] = useState<SourceMode>('fixture')
  const [running, setRunning] = useState(false)
  const [stepIndex, setStepIndex] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<RunResult | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [diffRevealed, setDiffRevealed] = useState(false)

  const selectedNode = useMemo(() => {
    if (!result || !selectedId) return null
    return result.graph.nodes.find((n) => n.id === selectedId) ?? null
  }, [result, selectedId])

  const selectedPath = selectedNode?.path ?? null

  const loadDemo = useCallback(async () => {
    setError(null)
    try {
      const demo = await fetchDemoDiff()
      setDiff(demo.diff)
      setUrn(demo.urn)
      setSource(demo.source)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    void loadDemo()
  }, [loadDemo])

  useEffect(() => {
    if (!running) return
    setStepIndex(0)
    const id = window.setInterval(() => {
      setStepIndex((i) => Math.min(i + 1, 4))
    }, 420)
    return () => window.clearInterval(id)
  }, [running])

  const onRun = async () => {
    setError(null)
    setResult(null)
    setSelectedId(null)
    setDiffRevealed(false)
    setRunning(true)
    try {
      const out = await runPipeline({ diff, urn, source })
      setResult(out)
      setStepIndex(4)
      const firstDownstream = out.graph.nodes.find((n) => n.kind !== 'source')
      setSelectedId(firstDownstream?.id ?? out.graph.nodes[0]?.id ?? null)
      window.setTimeout(() => setDiffRevealed(true), 120)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  const changeSummary = result?.report.changes
    .map((c) => {
      if (c.type === 'FIELD_RENAMED') return `${c.type} ${c.from} → ${c.to}`
      return `${c.type} ${c.from ?? ''}`
    })
    .join(', ')

  return (
    <div className="min-h-full bg-ink text-fg">
      <div className="mx-auto max-w-[1280px] px-4 py-5 md:px-6 md:py-6">
        <header className="relative mb-5 border-b border-line pb-4 pr-24 sm:pr-28">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="font-sans text-2xl font-semibold tracking-tight text-fg md:text-3xl">
                Cascade
              </h1>
              <p className="mt-1 text-sm text-muted">
                Schema change → coordinated migration
              </p>
            </div>
            <Timeline activeIndex={stepIndex} done={!!result && !running} running={running} />
          </div>
          <a
            href={GITHUB_REPO}
            target="_blank"
            rel="noopener noreferrer"
            className="absolute right-0 top-0 inline-flex items-center gap-1.5 border border-line bg-raised px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-wide text-fg hover:border-muted"
          >
            <GitHubIcon />
            GitHub
          </a>
        </header>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
          <section className="space-y-3" aria-label="Run controls">
            <label className="block">
              <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted">
                Schema diff
              </span>
              <textarea
                value={diff}
                onChange={(e) => setDiff(e.target.value)}
                spellCheck={false}
                rows={12}
                className="w-full resize-y border border-line bg-panel p-2.5 font-mono text-[11px] leading-relaxed text-fg placeholder:text-muted/60 focus:border-accent"
                placeholder='Paste JSON changes or a unified SQL/dbt diff…'
              />
            </label>

            <label className="block">
              <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted">
                Seed dataset URN
              </span>
              <input
                value={urn}
                onChange={(e) => setUrn(e.target.value)}
                spellCheck={false}
                className="w-full border border-line bg-panel px-2.5 py-1.5 font-mono text-[11px] text-fg focus:border-accent"
              />
            </label>

            <label className="block">
              <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted">
                Source
              </span>
              <select
                value={source}
                onChange={(e) => setSource(e.target.value as SourceMode)}
                className="w-full border border-line bg-panel px-2.5 py-1.5 font-mono text-[11px] text-fg focus:border-accent"
              >
                <option value="fixture">fixture (offline)</option>
                <option value="live">live (DataHub GMS)</option>
                <option value="auto">auto</option>
              </select>
            </label>

            <div className="flex flex-wrap gap-2 pt-1">
              <button
                type="button"
                onClick={() => void loadDemo()}
                className="border border-line bg-raised px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-fg hover:border-muted"
              >
                Load demo diff
              </button>
              <button
                type="button"
                onClick={() => void onRun()}
                disabled={running || !diff.trim()}
                className="border border-fg bg-fg px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-ink disabled:opacity-40"
              >
                {running ? 'Running…' : 'Run Cascade'}
              </button>
            </div>

            {error && (
              <div
                role="alert"
                className="border border-critical/60 bg-critical/10 px-3 py-2 font-mono text-xs text-critical"
              >
                {error}
              </div>
            )}
          </section>

          <section className="min-w-0 space-y-3" aria-label="Impact results">
            {!result && !running && !error && (
              <div className="flex min-h-[320px] items-center justify-center border border-dashed border-line bg-panel px-6 text-center">
                <p className="max-w-md text-sm text-muted">
                  Paste a breaking schema change (or load the demo), then run.
                  Cascade returns blast radius, per-node strategy, rewritten SQL, and dry-run
                  DataHub write-backs — fixture path works offline.
                </p>
              </div>
            )}

            {running && !result && (
              <div className="flex min-h-[320px] items-center justify-center border border-line bg-panel">
                <p className="font-mono text-xs text-accent">
                  Agent loop in progress…
                </p>
              </div>
            )}

            {result && (
              <>
                <div className="flex flex-wrap items-center gap-3 border border-line bg-panel px-3 py-2">
                  <span
                    className={[
                      'border px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider',
                      severityClass(result.report.severity),
                    ].join(' ')}
                  >
                    {result.report.severity}
                  </span>
                  <span className="font-mono text-[11px] text-muted">
                    {changeSummary}
                  </span>
                  <span className="ml-auto font-mono text-[10px] text-muted">
                    source={result.catalog_source} ·{' '}
                    {result.report.downstream.length} downstream ·{' '}
                    {result.report.ml_impact.length} ml
                  </span>
                </div>

                <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
                  <BlastGraph
                    nodes={result.graph.nodes}
                    edges={result.graph.edges}
                    selectedId={selectedId}
                    onSelect={setSelectedId}
                    severity={result.report.severity}
                  />
                  <NodeDetail node={selectedNode} report={result.report} />
                </div>

                <DiffViewer
                  files={result.files}
                  selectedPath={selectedPath}
                  revealed={diffRevealed}
                />

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="border border-line px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-fg hover:border-muted"
                    onClick={() =>
                      downloadText(
                        'impact_report.json',
                        JSON.stringify(result.report, null, 2) + '\n',
                      )
                    }
                  >
                    Download report JSON
                  </button>
                  {typeof result.apply['downstream_pr.diff'] === 'string' && (
                    <button
                      type="button"
                      className="border border-line px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-fg hover:border-muted"
                      onClick={() =>
                        downloadText(
                          'downstream_pr.diff',
                          result.apply['downstream_pr.diff'] as string,
                        )
                      }
                    >
                      Download patch
                    </button>
                  )}
                  {result.files.map((f) => (
                    <button
                      key={f.path}
                      type="button"
                      className="border border-line px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-muted hover:border-muted hover:text-fg"
                      onClick={() =>
                        downloadText(f.path.split('/').pop() || 'rewritten.sql', f.after)
                      }
                    >
                      Download {f.path.split('/').pop()}
                    </button>
                  ))}
                </div>

                <WritebackPanel apply={result.apply} />
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
