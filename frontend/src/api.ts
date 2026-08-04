import type { DemoDiff, RunResult, SourceMode } from './types'

async function readError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: string }
    return data.detail || res.statusText
  } catch {
    return res.statusText || `HTTP ${res.status}`
  }
}

export async function fetchDemoDiff(): Promise<DemoDiff> {
  const res = await fetch('/api/demo-diff')
  if (!res.ok) throw new Error(await readError(res))
  return res.json() as Promise<DemoDiff>
}

export async function runPipeline(input: {
  diff: string
  urn: string
  source: SourceMode
}): Promise<RunResult> {
  const res = await fetch('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  if (!res.ok) throw new Error(await readError(res))
  return res.json() as Promise<RunResult>
}
