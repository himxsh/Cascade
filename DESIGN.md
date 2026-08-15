# Design

## Product

Cascade. Library, PyPI package, and GitHub Action for coordinated schema migrations.

## Theme

Dark, locked. The mark sits on true black. Engineers meet this site beside GitHub at night. Light mode would fight the logo.

Color strategy: committed. Void field, cool steel type from the outer chevron, vermillion from the inner chevron on actions and the mark only.

## Palette

| Token | Hex | Role |
| --- | --- | --- |
| void | `#050506` | Page |
| ink | `#0a0a0b` | Raised chrome |
| panel | `#141210` | Slabs, code |
| frost | `#e4e8f0` | Type, outer chevron |
| mute | `#b7bec9` | Secondary type (AA on void) |
| line | `#2c2826` | Hairlines |
| ember | `#fc3010` | Inner chevron, primary action |
| ember-ink | `#140804` | Text on ember |

Neutrals carry a trace of ember hue. No second accent.

## Typography

- Display: Instrument Serif 400 / italic. Letter-spacing ≥ `-0.03em`. User-mandated face.
- Body / UI: Schibsted Grotesk 400–700.
- Commands: Azeret Mono 400–500.
- Display scale: `clamp(2.25rem, 5.2vw, 3.75rem)` for the home h1 (long line, two-line cap).
- Body: 1.0625rem, line-height 1.6 on dark.

## Layout

Asymmetric split hero. Install slab is the object on the right. How-it-works is a staggered stack, not a card grid. Compatibility is a strip. Proof is one GitHub artifact. Radius 12px on slabs, full pill on buttons and the nav island.

## Motion

Signature: chevron strokes draw on first paint. Install tab changes are 160ms ease-out. Below-fold layers use view-timeline clip reveals when supported; content stays visible if they do not run. No bounce. Reduced motion: static mark, no translation.

## Components

- Nav: floating solid island, 56px, no blur.
- Install slab: three tabs, copy, download.
- Mark: two rounded chevrons, frost over ember.
- Footer: Docs, Changelog, GitHub, License, Security.

## Do not

Gradient text, glass cards, side-stripe accents, 32px radii, Inter, cream paper, identical icon cards, em dashes in UI copy.
