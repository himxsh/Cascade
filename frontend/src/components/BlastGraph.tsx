import { useMemo } from 'react'
import type { GraphEdge, GraphNode } from '../types'

type Props = {
  nodes: GraphNode[]
  edges: GraphEdge[]
  selectedId: string | null
  onSelect: (id: string) => void
  severity: string
}

type LaidOut = GraphNode & { x: number; y: number }

function layout(nodes: GraphNode[], edges: GraphEdge[]): LaidOut[] {
  const indeg = new Map<string, number>()
  const children = new Map<string, string[]>()
  for (const n of nodes) {
    indeg.set(n.id, 0)
    children.set(n.id, [])
  }
  for (const e of edges) {
    if (!indeg.has(e.from) || !indeg.has(e.to)) continue
    indeg.set(e.to, (indeg.get(e.to) || 0) + 1)
    children.get(e.from)!.push(e.to)
  }

  const layers: string[][] = []
  const placed = new Set<string>()
  let frontier = nodes.filter((n) => (indeg.get(n.id) || 0) === 0).map((n) => n.id)
  if (frontier.length === 0 && nodes.length) frontier = [nodes[0].id]

  while (frontier.length) {
    layers.push(frontier)
    frontier.forEach((id) => placed.add(id))
    const next: string[] = []
    for (const id of frontier) {
      for (const c of children.get(id) || []) {
        if (placed.has(c) || next.includes(c)) continue
        const parentsReady = edges
          .filter((e) => e.to === c)
          .every((e) => placed.has(e.from) || !indeg.has(e.from))
        if (parentsReady) next.push(c)
      }
    }
    frontier = next
  }
  for (const n of nodes) {
    if (!placed.has(n.id)) {
      layers.push([n.id])
      placed.add(n.id)
    }
  }

  const width = 560
  const height = 220
  const padX = 48
  const padY = 36
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const out: LaidOut[] = []

  layers.forEach((layer, li) => {
    const y =
      layers.length === 1
        ? height / 2
        : padY + (li * (height - padY * 2)) / Math.max(layers.length - 1, 1)
    layer.forEach((id, xi) => {
      const x =
        layer.length === 1
          ? width / 2
          : padX + (xi * (width - padX * 2)) / Math.max(layer.length - 1, 1)
      const n = byId.get(id)
      if (n) out.push({ ...n, x, y })
    })
  })
  return out
}

function severityStroke(severity: string): string {
  const s = severity.toLowerCase()
  if (s === 'critical') return 'var(--color-critical)'
  if (s === 'high') return 'var(--color-high)'
  if (s === 'medium') return 'var(--color-medium)'
  return 'var(--color-low)'
}

export function BlastGraph({ nodes, edges, selectedId, onSelect, severity }: Props) {
  const laid = useMemo(() => layout(nodes, edges), [nodes, edges])
  const pos = useMemo(() => new Map(laid.map((n) => [n.id, n])), [laid])

  if (!nodes.length) {
    return (
      <div className="flex h-[220px] items-center justify-center border border-line bg-panel font-mono text-xs text-muted">
        No blast-radius nodes
      </div>
    )
  }

  return (
    <svg
      viewBox="0 0 560 220"
      className="h-auto w-full border border-line bg-panel"
      role="img"
      aria-label="Lineage blast-radius graph"
    >
      <defs>
        <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="var(--color-line)" />
        </marker>
      </defs>
      {edges.map((e) => {
        const a = pos.get(e.from)
        const b = pos.get(e.to)
        if (!a || !b) return null
        return (
          <line
            key={`${e.from}->${e.to}`}
            x1={a.x}
            y1={a.y + 14}
            x2={b.x}
            y2={b.y - 14}
            stroke="var(--color-line)"
            strokeWidth={1}
            markerEnd="url(#arrow)"
          />
        )
      })}
      {laid.map((n) => {
        const selected = n.id === selectedId
        const isSource = n.kind === 'source'
        const isMl = n.kind === 'mlModel'
        return (
          <g
            key={n.id}
            transform={`translate(${n.x}, ${n.y})`}
            className="cursor-pointer"
            onClick={() => onSelect(n.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(ev) => {
              if (ev.key === 'Enter' || ev.key === ' ') {
                ev.preventDefault()
                onSelect(n.id)
              }
            }}
          >
            <rect
              x={-52}
              y={-16}
              width={104}
              height={32}
              rx={2}
              fill={selected ? 'var(--color-raised)' : 'var(--color-ink)'}
              stroke={selected ? severityStroke(severity) : 'var(--color-line)'}
              strokeWidth={selected ? 1.5 : 1}
              className="transition-[stroke,fill] duration-200"
            />
            <text
              textAnchor="middle"
              y={-2}
              fill="var(--color-fg)"
              fontSize={10}
              fontFamily="var(--font-mono)"
            >
              {n.label}
            </text>
            <text
              textAnchor="middle"
              y={10}
              fill="var(--color-muted)"
              fontSize={8}
              fontFamily="var(--font-mono)"
            >
              {isSource ? 'source' : isMl ? 'mlModel' : n.strategy || n.kind}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
