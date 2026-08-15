import { Link } from './Link'

export function Changelog() {
  return (
    <article className="mx-auto max-w-[65ch] px-5 py-14 sm:px-6">
      <h1 className="display text-[clamp(2rem,4vw,2.75rem)]">Changelog</h1>
      <p className="mt-4 text-mute">
        Versions look like v0.1.0. The homepage install uses the latest stable
        release. Pin a version in GitHub Actions.
      </p>
      <section className="mt-12">
        <h2 className="text-xl font-semibold">0.1.0</h2>
        <ul className="mt-4 space-y-2 text-mute">
          <li>Commands: impact, generate, apply, policy, init, doctor, demo.</li>
          <li>GitHub Action workflow you can copy into your repo.</li>
          <li>Install from git with pip.</li>
          <li>By default it only writes local files. It will not open a GitHub pull request until you ask.</li>
        </ul>
      </section>
    </article>
  )
}

export function Security() {
  return (
    <article className="mx-auto max-w-[65ch] px-5 py-14 sm:px-6">
      <h1 className="display text-[clamp(2rem,4vw,2.75rem)]">Security</h1>
      <p className="mt-4 text-mute">
        Report a bug privately with GitHub Security Advisories on himxsh/Cascade.
        Do not file a public issue with the details.
      </p>
      <h2 className="mt-10 text-xl font-semibold">What the Action can do</h2>
      <p className="mt-3 text-mute">
        It can comment on a pull request and open a follow-up branch. It cannot
        merge. It uses the default GitHub token, not a stored personal token.
      </p>
      <h2 className="mt-10 text-xl font-semibold">Secrets</h2>
      <p className="mt-3 text-mute">
        DataHub and AI keys stay in your GitHub secrets and local .env. cascade
        init only writes an example file. AI edits cannot invent column names.
      </p>
      <h2 className="mt-10 text-xl font-semibold">What we do not do</h2>
      <p className="mt-3 text-mute">
        No database passwords. No merge without you. No hosted DataHub.
      </p>
    </article>
  )
}

export function NotFound() {
  return (
    <article className="mx-auto max-w-[65ch] px-5 py-24 sm:px-6">
      <h1 className="display text-[clamp(2rem,4vw,2.75rem)]">Page not found</h1>
      <p className="mt-4 text-mute">
        That URL is not a Cascade page.{' '}
        <Link href="/" className="text-frost underline decoration-ember/70 underline-offset-4">
          Home
        </Link>
        {' or '}
        <Link href="/docs" className="text-frost underline decoration-ember/70 underline-offset-4">
          docs
        </Link>
        .
      </p>
    </article>
  )
}
