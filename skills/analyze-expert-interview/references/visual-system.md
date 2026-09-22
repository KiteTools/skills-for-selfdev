# Visual system

Reproduce a calm magazine-analysis grammar, not a generic dashboard. The artifact is static HTML with inline CSS and inline SVG: no JavaScript, no external assets, no external fonts, no CDN, and no runtime requests. Use a system font stack so it stays offline.

## Layout and hierarchy

- Centre a `1040px` maximum-width `.wrap` on warm off-white paper #fcfcfb with soft #f3f2ee surfaces; use restrained near-black/gray text and blue timestamp links. These audited reference values are authoritative for the template variables `--paper` and `--tile`.
- Establish editorial whitespace: compact masthead and lede, then materially larger gaps before numbered diagnosis, logic, and revision sections.
- Use soft, low-contrast KPI tiles, two compact score meters, dense evidence tables, and gray `.callout` blocks with a semantic left border.
- State score polarity next to each meter: structural chaos rises with disorder; logical soundness rises with rigor.
- Use blue monospace-like timestamps. If no source URL exists, render the timestamp as visible text, never a fabricated link.

## Required topology

1. Masthead: kicker, title, lede, recording link, duration, roles, provenance.
2. KPI tiles and the two score meters.
3. `1. Diagnosis` with evidence callout.
4. `Topic trajectory` as inline SVG.
5. Guest-only structural account and representative moments.
6. `2. Logic`: defects, defended theses, strongest moments.
7. `3. Five revisions`.
8. Native `<details>` appendix and method disclosure.

The trajectory uses coloured horizontal spans: dominant spans higher opacity than touched spans. Each SVG group has native <title> text and the SVG uses `role="img"` plus an informative `aria-label`. Keep tables semantic (`th`, `scope`) and inside a `.scroll` wrapper.

## Responsive constraints

At a `760px` breakpoint reduce the heading scale, stack grids, and preserve readable padding. Provide horizontal table scrolling rather than squeezing dense evidence. Require no page horizontal overflow at desktop and mobile widths. Keep focus states visible and all information available without hover; hover titles enrich rather than replace labels.

## Browser-QA evidence

Record normal-run checks in `review-status.md`. The `evaluation.json` mechanics below apply only to the optional strict review protocol; do not fabricate evaluation records for an ordinary run.

Capture the rendered static report at 1440×1000 desktop and 390×844 mobile.
For each viewport, record `no_overflow: true` only after inspecting the page.
The `evaluation.json` gate records those dimensions plus non-empty paths to
the screenshots, normalized.json and synthesis.json. Its static checks must
find zero `<script>` elements, zero external resource elements or CSS resource
tokens, and browser-recorded counts for native `<details>` disclosures and
`.tc` timestamps. It also independently reruns the primary report validator
against normalized.json, synthesis.json, and report.html; `validator_pass` is
required but cannot substitute for that call. This preserves the reference
grammar while keeping the artifact offline and auditable.
