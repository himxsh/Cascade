type Props = {
  apply: Record<string, unknown> | null
}

function asPretty(value: unknown): string {
  if (typeof value === 'string') {
    try {
      return JSON.stringify(JSON.parse(value), null, 2)
    } catch {
      return value
    }
  }
  return JSON.stringify(value, null, 2)
}

export function WritebackPanel({ apply }: Props) {
  if (!apply) {
    return (
      <div className="border border-line bg-panel p-3 font-mono text-xs text-muted">
        Write-back payloads appear after a successful dry-run apply.
      </div>
    )
  }

  const sections: { title: string; key: string }[] = [
    { title: 'DataHub tags / docs', key: 'datahub_writeback.json' },
    { title: 'ML retrain-suggested', key: 'ml_writeback.json' },
    { title: 'Migrated lifecycle', key: 'migrated.json' },
  ]

  return (
    <div className="space-y-2">
      {sections.map(({ title, key }) => {
        const raw = apply[key] ?? apply[key.replace('.json', '')]
        if (raw == null) return null
        return (
          <details key={key} className="border border-line bg-panel open:bg-raised">
            <summary className="cursor-pointer px-3 py-2 font-mono text-[11px] uppercase tracking-wider text-muted">
              {title}
            </summary>
            <pre className="max-h-48 overflow-auto border-t border-line px-3 py-2 font-mono text-[11px] leading-relaxed text-fg/90">
              {asPretty(raw)}
            </pre>
          </details>
        )
      })}
    </div>
  )
}
