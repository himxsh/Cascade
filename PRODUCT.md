# Product

## Register

brand

## Platform

web

## Users

Staff data engineers and analytics engineers who already keep SQL or dbt in GitHub and already have those tables in DataHub. They open the site while a breaking schema PR is in flight, or while wiring the Action into a repo. They want an install path, not a hosted account.

## Product Purpose

Cascade is a Python CLI and GitHub Action. A breaking schema PR becomes a blast-radius report, rewritten downstream SQL, and a remediation PR. Success is a stranger installing it in their own repo, with secrets staying in their `.env` and Actions.

## Positioning

A library you install, not a SaaS you join. It reads DataHub lineage and rewrites SQL in git. It never connects to the warehouse.

## Conversion & proof

- Primary CTA: copy the install command (`npx`, `pip`, or the GitHub Action workflow).
- Secondary CTA: open the GitHub repository / download `cascade.yml`.
- The line a visitor remembers after 10 seconds: a breaking schema PR becomes a coordinated migration.
- Belief ladder: this is an installable CLI and Action; DataHub lineage is the catalog; Cascade does not need warehouse passwords; dry-run is the default; a human still merges.
- Proof on hand: the in-repo `user_id` → `customer_id` loop, the consumer workflow at `examples/github-action/cascade.yml`, and the product mark at `frontend/public/Cascade Logo.png`.

## Brand Personality

Surgical, stacked, honest. Night-shift GitHub energy. Plain words for what the person sees: a pull request, a file, a column. No launch-week theatrics.

## Anti-references

Not a paste-diff playground as the front door. Not a signup or billing funnel. Not a hosted DataHub. Not a terminal-green hacker skin. Not three identical feature cards. Not autonomous merge.

## Design Principles

- The install is the product. The hero must ship a command, a download, and a GitHub path.
- Show the loop, do not decorate it: diff, blast radius, remediation PR.
- Stay honest about the warehouse: DataHub is required; Cascade does not ingest it.
- One accent from the mark. The inner chevron is the only heat.
- Dry-run and human merge are features, not disclaimers buried in a footer.

## Accessibility & Inclusion

WCAG AA contrast on body, placeholders, and ember buttons. Visible keyboard focus. `prefers-reduced-motion` collapses stroke and reveal motion to a crossfade or instant. Touch targets at least 44px on primary controls.
