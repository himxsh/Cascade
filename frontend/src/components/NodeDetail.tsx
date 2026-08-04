import type { GraphNode, ImpactReport } from '../types'

type Props = {
  node: GraphNode | null
  report: ImpactReport | null
}

function ownerShort(urn: string): string {
  const i = urn.lastIndexOf(':')
  return i >= 0 ? urn.slice(i + 1) : urn
}

export function NodeDetail({ node, report }: Props) {
  if (!node) {
    return (
      <div className="border border-line bg-panel p-3 font-mono text-xs text-muted">
        Select a node to inspect strategy, owners, and rationale.
      </div>
    )
  }

  const ml = report?.ml_impact?.find((m) => m.model_urn === node.id)

  return (
    <div className="border border-line bg-panel p-3 transition-opacity duration-200">
      <div className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted">
        Node detail
      </div>
      <div className="mb-3 break-all font-mono text-[11px] text-fg">{node.id}</div>
      <dl className="grid grid-cols-[7rem_1fr] gap-x-2 gap-y-1.5 text-xs">
        <dt className="text-muted">kind</dt>
        <dd className="font-mono">{node.kind}</dd>
        <dt className="text-muted">strategy</dt>
        <dd className="font-mono text-accent">{node.strategy || '—'}</dd>
        <dt className="text-muted">owners</dt>
        <dd className="font-mono">
          {node.owners.length
            ? node.owners.map(ownerShort).join(', ')
            : '—'}
        </dd>
        {node.path && (
          <>
            <dt className="text-muted">path</dt>
            <dd className="break-all font-mono">{node.path}</dd>
          </>
        )}
        {ml && (
          <>
            <dt className="text-muted">ml action</dt>
            <dd className="font-mono">{ml.action} via {ml.via_feature}</dd>
          </>
        )}
        <dt className="text-muted">rationale</dt>
        <dd className="leading-snug text-fg/90">{node.rationale || '—'}</dd>
      </dl>
    </div>
  )
}
