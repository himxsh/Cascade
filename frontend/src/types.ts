export type SourceMode = 'fixture' | 'live' | 'auto'

export type Change = {
  type: string
  from?: string | null
  to?: string | null
  detected_by?: string
}

export type DownstreamNode = {
  urn: string
  type: string
  owners: string[]
}

export type Remediation = {
  urn?: string
  path?: string
  strategy: string
  rationale: string
  rewritten_sql?: string
}

export type MlImpact = {
  model_urn: string
  via_feature: string
  action: string
}

export type ImpactReport = {
  source_urn: string
  changes: Change[]
  downstream: DownstreamNode[]
  ml_impact: MlImpact[]
  severity: string
  remediations: Remediation[]
}

export type GraphNode = {
  id: string
  label: string
  kind: string
  owners: string[]
  strategy?: string | null
  rationale?: string | null
  path?: string | null
}

export type GraphEdge = { from: string; to: string }

export type DiffFile = {
  path: string
  before: string
  after: string
}

export type RunResult = {
  steps: string[]
  catalog_source: string
  report: ImpactReport
  graph: { nodes: GraphNode[]; edges: GraphEdge[] }
  files: DiffFile[]
  apply: Record<string, unknown>
}

export type DemoDiff = {
  urn: string
  source: SourceMode
  diff: string
  path: string
}
