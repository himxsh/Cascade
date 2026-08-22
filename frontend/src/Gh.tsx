import type { ReactNode } from 'react'

function FileIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="#8b949e">
      <path d="M2 1.75C2 .784 2.784 0 3.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0 1 13.25 16h-9.5A1.75 1.75 0 0 1 2 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 0 0 .25-.25V6h-2.75A1.75 1.75 0 0 1 9 4.25V1.5Zm6.906 1.442L10.5 1.646V4.25c0 .138.112.25.25.25h2.604Z" />
    </svg>
  )
}

function PrIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">
      <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.338.958a.25.25 0 0 1 .354 0l.165.165a.25.25 0 0 1 0 .354l-2.066 2.009a.25.25 0 0 1-.177.074H7.25v4.256a2.251 2.251 0 1 1-1.5 0V4.25h-.073a.25.25 0 0 1-.177-.074ZM12.75 9a.75.75 0 0 1 .75.75v2.378a2.251 2.251 0 1 1-1.5 0V9.75A.75.75 0 0 1 12.75 9Zm-8.5-4.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 8.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm8.5 0a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Z" />
    </svg>
  )
}

function GhShell({
  children,
  label,
}: {
  children: ReactNode
  label: string
}) {
  return (
    <figure className="gh mt-5">
      <figcaption className="sr-only">{label}</figcaption>
      {children}
    </figure>
  )
}

function DiffRow({
  oldNo,
  newNo,
  kind,
  children,
}: {
  oldNo?: number
  newNo?: number
  kind: 'del' | 'add'
  children: string
}) {
  const del = kind === 'del'
  return (
    <div className={['flex', del ? 'bg-[#f851491a]' : 'bg-[#3fb95026]'].join(' ')}>
      <span className="w-10 shrink-0 select-none border-r border-[#30363d] pr-2 text-right text-[#8b949e]">
        {oldNo ?? ''}
      </span>
      <span className="w-10 shrink-0 select-none border-r border-[#30363d] pr-2 text-right text-[#8b949e]">
        {newNo ?? ''}
      </span>
      <span
        className={[
          'w-4 shrink-0 select-none text-center',
          del ? 'text-[#f85149]' : 'text-[#3fb950]',
        ].join(' ')}
      >
        {del ? '-' : '+'}
      </span>
      <span className="min-w-0 px-2 py-0.5 text-[#e6edf3]">{children}</span>
    </div>
  )
}

function FileBar({ file }: { file: string }) {
  return (
    <div className="flex items-center gap-2 border-b border-[#30363d] bg-[#161b22] px-3 py-2 text-[13px]">
      <FileIcon />
      <span className="text-[#e6edf3]">{file}</span>
    </div>
  )
}

function Hunk({ text }: { text: string }) {
  return <div className="bg-[#161b22] px-3 py-1 text-[#8b949e]">{text}</div>
}

export function GhDiff({
  file,
  fromLine,
  toLine,
}: {
  file: string
  fromLine: string
  toLine: string
}) {
  return (
    <GhShell label={`GitHub file diff for ${file}`}>
      <FileBar file={file} />
      <div className="gh-mono overflow-x-auto">
        <Hunk text="@@ -14,2 +14,2 @@" />
        <DiffRow oldNo={14} kind="del">
          {fromLine}
        </DiffRow>
        <DiffRow newNo={14} kind="add">
          {toLine}
        </DiffRow>
      </div>
    </GhShell>
  )
}

export function GhComment() {
  return (
    <GhShell label="GitHub comment from Cascade on pull request 184">
      <div className="flex gap-3 p-3 sm:p-4">
        <img
          src="/logo.png"
          alt=""
          width={40}
          height={40}
          className="size-10 shrink-0 rounded-full"
        />
        <div className="min-w-0 flex-1 overflow-hidden rounded-md border border-[#30363d]">
          <div className="flex flex-wrap items-center gap-x-1.5 border-b border-[#30363d] bg-[#161b22] px-3 py-2 text-[13px]">
            <span className="font-semibold text-[#e6edf3]">cascade-bot</span>
            <span className="rounded-full border border-[#30363d] px-1.5 text-[11px] leading-5 text-[#8b949e]">
              Bot
            </span>
            <span className="text-[#8b949e]">commented 2 hours ago</span>
            <span className="text-[#8b949e]">on</span>
            <span className="text-[#2f81f7]">#184</span>
          </div>
          <div className="space-y-3 px-3 py-3 text-[14px] leading-relaxed text-[#e6edf3]">
            <p>
              This pull request renames <code className="gh-code">user_id</code> to{' '}
              <code className="gh-code">customer_id</code> on{' '}
              <code className="gh-code">raw_orders</code>. 3 downstream models
              still depend on it.
            </p>
            <p className="text-[#8b949e]">Comment /cascade stack to open a stacked PR.</p>
          </div>
        </div>
      </div>
    </GhShell>
  )
}

export function GhPull() {
  return (
    <GhShell label="GitHub pull request 185 with the file edits">
      <div className="border-b border-[#30363d] px-4 py-4">
        <div className="flex flex-wrap items-start gap-2">
          <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-[#238636] px-2.5 py-0.5 text-[12px] font-semibold text-white">
            <PrIcon />
            Open
          </span>
          <p className="text-[20px] font-semibold leading-snug text-[#e6edf3]">
            Update queries after user_id rename{' '}
            <span className="font-normal text-[#8b949e]">#185</span>
          </p>
        </div>
        <p className="mt-2 text-[13px] text-[#8b949e]">
          <span className="font-semibold text-[#e6edf3]">cascade-bot</span>
          {' wants to merge 1 commit into '}
          <span className="rounded-full border border-[#30363d] bg-[#161b22] px-2 py-0.5 text-[#e6edf3]">
            main
          </span>
          {' from '}
          <span className="rounded-full border border-[#30363d] bg-[#161b22] px-2 py-0.5 text-[#e6edf3]">
            cascade/remediation/184
          </span>
        </p>
      </div>
      <div className="flex gap-4 overflow-x-auto border-b border-[#30363d] px-4 text-[13px]">
        <span className="py-2 text-[#8b949e]">Conversation</span>
        <span className="py-2 text-[#8b949e]">Commits</span>
        <span className="border-b-2 border-[#f78166] py-2 text-[#e6edf3]">
          Files changed
        </span>
        <span className="py-2 text-[#8b949e]">
          <span className="text-[#3fb950]">+1</span>{' '}
          <span className="text-[#f85149]">−1</span>
        </span>
      </div>
      <FileBar file="models/fct_orders.sql" />
      <div className="gh-mono overflow-x-auto">
        <Hunk text="@@ -8,2 +8,2 @@" />
        <DiffRow oldNo={8} kind="del">
          select user_id
        </DiffRow>
        <DiffRow newNo={8} kind="add">
          select customer_id
        </DiffRow>
      </div>
    </GhShell>
  )
}

export function GhCode({
  file,
  children,
}: {
  file?: string
  children: string
}) {
  const lines = children.replace(/\n$/, '').split('\n')
  const numbered = file != null && file !== 'terminal'

  return (
    <div className="gh mt-5">
      {file ? (
        <div className="flex items-center gap-2 border-b border-[#30363d] bg-[#161b22] px-3 py-2 text-[12px] text-[#e6edf3]">
          {numbered ? <FileIcon /> : null}
          <span>{file}</span>
        </div>
      ) : null}
      <pre className="gh-mono overflow-x-auto py-2 text-[#e6edf3]">
        <code>
          {numbered
            ? lines.map((line, i) => (
                <span key={i} className="flex">
                  <span className="w-10 shrink-0 select-none pr-3 text-right text-[#8b949e]">
                    {i + 1}
                  </span>
                  <span className="min-w-0 px-3">{line || ' '}</span>
                </span>
              ))
            : children}
        </code>
      </pre>
    </div>
  )
}
