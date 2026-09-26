import { useEffect, useState } from 'react'
import { GhComment, GhDiff, GhPull } from './Gh'
import { InstallPanel } from './InstallPanel'
import { Link } from './Link'
import { Mark } from './Mark'
import { copyText, PIP } from './site'

const COMPAT = ['Python 3.11+', 'GitHub Actions', 'DataHub', 'SQL or dbt']

export function Home() {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const id = window.setTimeout(() => setCopied(false), 1600)
    return () => window.clearTimeout(id)
  }, [copied])

  const onCopy = async () => {
    const ok = await copyText(PIP)
    if (ok) setCopied(true)
  }

  return (
    <>
      <section className="mx-auto grid max-w-[1120px] grid-cols-1 items-start gap-10 px-5 pb-14 pt-12 sm:px-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.88fr)] lg:gap-x-16 lg:pb-16 lg:pt-16">
        <div className="hero-copy lg:pt-1">
          <h1 className="display max-w-[18ch] text-[clamp(2.35rem,4.8vw,3.6rem)] leading-[1.12]">
            Keep downstream SQL aligned with the schema.
          </h1>
          <p className="mt-6 max-w-[40ch] text-[1.125rem] leading-[1.7] text-frost/70">
            On a schema PR, Cascade uses DataHub to find models still on the old
            schema and comments what is affected. A stacked PR is opt-in. No
            warehouse connection.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="btn btn-ember"
              onClick={() => void onCopy()}
            >
              {copied ? 'Copied' : 'Copy install command'}
            </button>
            <Link href="/docs" className="btn btn-ghost">
              Read the docs
            </Link>
          </div>
        </div>
        <div className="hero-slab lg:pt-1">
          <div className="mb-6 flex justify-start">
            <Mark className="h-auto w-[min(100%,148px)]" animate />
          </div>
          <InstallPanel copied={copied} onCopy={() => void onCopy()} />
        </div>
      </section>

      <section className="border-y border-line bg-ink">
        <div className="reveal mx-auto flex max-w-[1120px] flex-wrap items-center gap-x-8 gap-y-3 px-5 py-5 sm:px-6">
          {COMPAT.map((item) => (
            <p key={item} className="cmd text-[0.7rem] tracking-wide text-mute">
              {item}
            </p>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-[1120px] px-5 py-24 sm:px-6 sm:py-28">
        <h2 className="reveal display max-w-[18ch] text-[clamp(1.85rem,4vw,2.75rem)]">
          From the schema PR to the stacked PR.
        </h2>
        <div className="reveal-list mt-14 space-y-6 md:space-y-8">
          <article className="reveal md:max-w-[88%]">
            <h3 className="text-lg font-semibold tracking-tight">
              Schema PR
            </h3>
            <p className="mt-2 max-w-[62ch] text-mute">
              A pull request renames user_id to customer_id on the orders
              model. That diff is the source of truth.
            </p>
            <GhDiff
              file="models/raw_orders.sql"
              fromLine="user_id"
              toLine="customer_id"
            />
          </article>

          <article className="reveal md:ml-auto md:max-w-[88%]">
            <h3 className="text-lg font-semibold tracking-tight">
              Downstream impact
            </h3>
            <p className="mt-2 max-w-[62ch] text-mute">
              Cascade reads the DataHub catalog for models that still depend on
              that table. It does not connect to Snowflake, Postgres, or
              BigQuery.
            </p>
            <GhComment />
          </article>

          <article className="reveal md:max-w-[92%]">
            <h3 className="text-lg font-semibold tracking-tight">
              Stacked PR
            </h3>
            <p className="mt-2 max-w-[62ch] text-mute">
              Comment /cascade stack to open a PR with this branch&apos;s
              commits plus the downstream rewrites. Merge stays with you.
            </p>
            <GhPull />
          </article>
        </div>
      </section>

      <section className="reveal-list mx-auto max-w-[1120px] px-5 py-24 sm:px-6">
        <h2 className="reveal display max-w-[16ch] text-[clamp(1.85rem,4vw,2.75rem)]">
          Keep the schema and the models in the same review.
        </h2>
        <p className="reveal mt-5 max-w-[62ch] text-mute">
          Add the Action to a repo. Cascade comments on the source PR. Comment
          /cascade stack when you want the rewritten SQL as a stacked PR.
        </p>
        <div className="reveal mt-10">
          <Link href="/docs" className="btn btn-ember">
            Read the docs
          </Link>
        </div>
      </section>
    </>
  )
}
