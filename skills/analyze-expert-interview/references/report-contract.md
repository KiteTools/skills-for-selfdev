# Synthesis report contract

The synthesis stage emits one UTF-8 JSON object. `scripts/validate_report.py`
validates it against the normalized transcript and, optionally, its rendered HTML.
The validator returns silently on success and raises `ValueError` on failure.

## Exact JSON shape

All nine top-level keys shown below are required. Additional analytical fields are
allowed unless they create an excluded dedicated module.

```json
{
  "metadata": {
    "title": "Broadcast analysis"
  },
  "metrics": {
    "duration_ms": 8000,
    "guest_speaking_ms": 6000,
    "guest_speaking_share": 0.75,
    "guest_turn_count": 1,
    "guest_turn_median_ms": 6000,
    "longest_guest_turn_ms": 6000,
    "host_to_guest_transitions": 1,
    "duration_metrics_partial": false,
    "unknown_duration_segment_count": 0,
    "guest_turn_duration_count": 1
  },
  "scores": {
    "structural_chaos": 4,
    "logical_soundness": 8.5
  },
  "diagnosis": {
    "title": "A clear progression",
    "paragraphs": [
      "The guest moves from observation to a decision."
    ],
    "anchor_evidence": {
      "quote": "First I noticed the difficult pattern",
      "start_ms": 1000
    }
  },
  "topics": [
    {
      "id": "change",
      "label": "Change",
      "color": "#3355aa",
      "spans": [
        {
          "start_ms": 1000,
          "end_ms": 7000,
          "weight": "dominant",
          "note": "The guest describes a change in direction."
        }
      ]
    }
  ],
  "structure": {
    "counts": [
      {"label": "guest turns", "value": 1}
    ],
    "events": [
      {
        "kind": "turning_point",
        "quote": "First I noticed the difficult pattern",
        "start_ms": 1000,
        "analysis": "The observation becomes an explicit choice."
      }
    ]
  },
  "logic": {
    "defects": [
      {
        "category": "qualification",
        "count": 1,
        "example": {
          "quote": "First I noticed the difficult pattern",
          "start_ms": 1000,
          "analysis": "The premise remains somewhat broad."
        }
      }
    ],
    "theses": [
      {
        "thesis": "Recognition enables a clearer choice.",
        "status": "supported",
        "support": "The guest states the sequence directly.",
        "quote": "First I noticed the difficult pattern",
        "start_ms": 1000
      }
    ],
    "strong_moments": [
      {
        "title": "Choice follows recognition",
        "quote": "First I noticed the difficult pattern",
        "start_ms": 1000,
        "analysis": "A compact causal progression."
      }
    ]
  },
  "recommendations": [
    {"title": "Recommendation 1", "body": "A concrete revision.", "candidate_id": "structure:recommendation-1", "source_ids": ["structure:event-1"], "basis": {"quote": "First I noticed the difficult pattern", "start_ms": 1000, "analysis": "The recommendation follows from the cited passage."}},
    {"title": "Recommendation 2", "body": "A concrete revision.", "candidate_id": "structure:recommendation-2", "source_ids": ["structure:event-1"], "basis": {"quote": "First I noticed the difficult pattern", "start_ms": 1000, "analysis": "The recommendation follows from the cited passage."}},
    {"title": "Recommendation 3", "body": "A concrete revision.", "candidate_id": "structure:recommendation-3", "source_ids": ["structure:event-1"], "basis": {"quote": "First I noticed the difficult pattern", "start_ms": 1000, "analysis": "The recommendation follows from the cited passage."}},
    {"title": "Recommendation 4", "body": "A concrete revision.", "candidate_id": "structure:recommendation-4", "source_ids": ["structure:event-1"], "basis": {"quote": "First I noticed the difficult pattern", "start_ms": 1000, "analysis": "The recommendation follows from the cited passage."}},
    {"title": "Recommendation 5", "body": "A concrete revision.", "candidate_id": "structure:recommendation-5", "source_ids": ["structure:event-1"], "basis": {"quote": "First I noticed the difficult pattern", "start_ms": 1000, "analysis": "The recommendation follows from the cited passage."}}
  ],
  "method": "Scores and findings are derived from the normalized transcript."
}
```

Schema rules:

- `metadata` is an object. `method` is a non-empty string.
- `scores.structural_chaos` and `scores.logical_soundness` are JSON numbers from
  0 through 10 inclusive; booleans are not numbers here.
- Score polarity is intentional: higher `structural_chaos` is worse, while
  higher `logical_soundness` is better.
- `diagnosis.title` is non-empty, `paragraphs` is a non-empty list of non-empty
  strings, and `anchor_evidence` is an evidence item.
- `topics` is non-empty. Every topic has non-empty `id`, `label`, and `color`,
  plus a non-empty `spans` list. Every span has integer millisecond bounds with
  `0 <= start_ms < end_ms`, a `weight` of `dominant` or `touched`, and a
  non-empty `note`. When the transcript duration is known, `end_ms` must not
  exceed it; an open-ended final transcript cue leaves that upper bound unknown.
- `structure.counts` and `structure.events` are required lists. Count items have
  `label` and numeric `value`; event items have `kind`, `quote`, `start_ms`, and
  `analysis`.
- `logic.defects`, `logic.theses`, and `logic.strong_moments` are required
  lists. A defect has `category`, numeric nonnegative `count`, and an `example`
  evidence object containing `quote`, `start_ms`, and `analysis`. A thesis has
  `thesis`, `status`, `support`, `quote`, and `start_ms`. A strong moment has
  `title`, `quote`, `start_ms`, and `analysis`.
- `recommendations` contains exactly five items. Each item has exactly
  `{title, body, candidate_id, source_ids, basis}`: `title` and `body` are
  non-empty strings. `candidate_id` matches
  `^(structure|logic):[A-Za-z0-9._-]+$`; `source_ids` is a non-empty list of
  unique strings matching the same expression and using the same `structure` or
  `logic` pass prefix as `candidate_id`. `basis` has
  exactly `{quote, start_ms, analysis}`, with a non-empty analysis and the same
  guest-evidence rules as every other quote. The synthesis stage, not this
  validator, checks that each `source_id` refers to the intended semantic source.

## Metrics

`metrics` is not authored by the model. It must equal
`compute_metrics(normalized)` exactly: no missing keys, extra keys, or different
values. JSON integers and floats compare numerically (`1 == 1.0`), but a boolean
cannot stand in for a numeric metric. This check covers every key emitted by the
current metrics implementation, so the report cannot preserve stale metrics when
that implementation changes.

## Evidence provenance

Every object containing a `quote` is an evidence item, including objects in
allowed extension fields; it must include `start_ms` and trace to `GUEST` speech. The
validator normalizes only case, whitespace, and equivalent Unicode punctuation
(for example curly/straight quotes and dash variants). It performs literal
substring matching after that normalization: there is no stemming, semantic
match, edit distance, or fuzzy fallback.

A quote may cross adjacent, time-contiguous `GUEST` segments. It may not cross a
host segment or a gap. Its `start_ms` must lie inside the `GUEST` segment where
the matching occurrence begins; equality with that segment's `start_ms` is
valid, while equality with its finite `end_ms` is not. When the same quote occurs
more than once, any occurrence whose starting segment contains `start_ms` is
accepted. Empty quotes and quotes with fewer than four normalized words fail to
avoid ambiguous evidence. A quote found only in `HOST` speech fails.

## Excluded dedicated modules

The report must not add a dedicated section key or title-like heading explicitly
named any of the following (case, `_`, and `-` variants are normalized):

- `speech` / `речь`;
- `listener`, `audience` / `слушатель`, `аудитория`;
- `host evaluation` / `ведущий`;
- `montage`, `editing sheet` / `монтажный лист`.

This is a structural exclusion, not a word blacklist. Ordinary analytical prose
may mention a host question, speech, a listener, or editing.

## Optional HTML gate

When an HTML path is supplied, it must be one well-ordered document: an optional
HTML doctype comes first; exactly one `html` root contains one closed `head`
followed by one closed `body`; the root closes last; and no non-whitespace
content occurs outside it. At least one inline `style` element is required.

The document must not contain `base`, `link`, `iframe`, `object`, `embed`,
`video`, `audio`, `source`, `track`, any `script`,
HTML event-handler attributes, meta refresh, duplicate attribute names, or
`srcset`. Explicit self-closing syntax is accepted only for `meta`, `br`, `hr`,
and an `img` without a URL. URL-bearing attributes on every tag are conservative:
only an `<a href>` with HTTPS host `www.youtube.com`, `youtube.com`, or
`youtu.be` is allowed. HTTP(S), `data:`,
protocol-relative, `javascript:`, and `vbscript:` values are rejected in every
attribute, even one not normally treated as a URL. CSS `@import` and all
`url(...)` are forbidden after decoding simple and hexadecimal CSS escapes, as
are `image-set()`, `-webkit-image-set()`, `cross-fade()`, and `@font-face`.
CSS comments are removed before escape decoding and resource-token detection;
an unterminated comment fails validation.
Attribute-level `url(...)` is limited to a safe same-document `url(#id)`.
Any non-empty `xml:base` is forbidden so it cannot externalize that fragment.
SVG SMIL elements `set`, `animate`, `animateMotion`, `animateTransform`, and
`mpath` are forbidden because their indirect `to`, `values`, and path behavior
can introduce runtime resources.
Ordinary rules such as `@media` remain valid. H1-H3 headings use the same
dedicated-module exclusions as the JSON report.

## Failure behavior and CLI

Python callers use:

```python
validate_report(report, normalized, html_text=None)
```

The function returns `None` when valid and raises `ValueError` at the first
contract violation. The CLI is:

```text
validate_report.py NORMALIZED_JSON REPORT_JSON [HTML]
```

It exits `0` on success. Read, JSON, type, schema, provenance, metrics, and HTML
failures produce one concise `error: ...` message on stderr and exit `2`.
Arbitrary extension fields are traversed iteratively and fail with `ValueError`
when they exceed 256 nesting levels or 100,000 nodes.

## Pass-and-bundle validation

Before rendering, validate both isolated passes and, when present, their
synthesis together with:

```text
validate_passes.py NORMALIZED_JSON STRUCTURE_JSON LOGIC_JSON [REPORT_JSON]
```

It exits `0` silently on success and emits one concise `error: ...` message to
stderr with exit code `2` on a schema, provenance, reference, or synthesis
mapping failure.
