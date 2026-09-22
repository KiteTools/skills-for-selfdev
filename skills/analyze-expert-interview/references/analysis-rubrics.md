# Analysis rubrics

Use these rubrics in both isolated passes and in synthesis. The unit of analysis is GUEST speech. A host question can define the answer target or transition only; it is never evidence for guest quality.

## Evidence threshold and uncertainty

Every reported observation needs a verbatim guest quote of at least four normalized words and a timestamp inside the source guest segment. A count needs distinct, timestamped instances; do not promote a single example into a recurring pattern. If a boundary, implied premise, referent, or attribution cannot be established from the transcript, label the finding **uncertainty** and state why. Do not infer a defect from style alone, and do not treat ASR noise as a logical defect without a stable, intelligible quote.

Deduplicate before scoring: merge descriptions of the same passage, claim, loop, or reasoning break across passes; do not count the same event twice under synonyms. Keep one primary category and cross-reference it where needed.

## Machine-readable pass handoffs

The two isolated passes emit the UTF-8 JSON objects below. They are source-agnostic: IDs describe only the supplied normalized transcript, not a person, show, language, or domain. Every listed `required` key must be present; `additionalProperties` is false so synthesis can map deterministically. Evidence is always GUEST evidence and uses the normalized segment identifier. `quote` must satisfy the evidence threshold above. Each pass copies `normalized.metadata` exactly into `input.normalized_metadata`; it does not invent a transcript identifier.

### `structure-analysis.json` schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "pass", "input", "structural_chaos", "topics", "observations", "recommendation_candidates", "uncertainties"],
  "properties": {
    "schema_version": {"const": "1.0"},
    "pass": {"const": "structure"},
    "input": {
      "type": "object", "additionalProperties": false,
      "required": ["normalized_metadata", "guest_label"],
      "properties": {
        "normalized_metadata": {
          "type": "object", "additionalProperties": false,
          "required": ["title", "source_url", "duration_ms", "source_format"],
          "properties": {
            "title": {"type": "string", "minLength": 1},
            "source_url": {"type": ["string", "null"]},
            "duration_ms": {"type": ["integer", "null"], "minimum": 1},
            "source_format": {"enum": ["txt", "srt", "vtt"]}
          }
        },
        "guest_label": {"const": "GUEST"}
      }
    },
    "structural_chaos": {
      "type": "object", "additionalProperties": false,
      "required": ["score", "rationale", "evidence"],
      "properties": {
        "score": {"type": "number", "minimum": 0, "maximum": 10},
        "rationale": {"type": "string", "minLength": 1},
        "evidence": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/evidence"}}
      }
    },
    "topics": {
      "type": "array", "minItems": 1, "items": {
        "type": "object", "additionalProperties": false,
        "required": ["id", "label", "color", "spans"],
        "properties": {
          "id": {"type": "string", "minLength": 1},
          "label": {"type": "string", "minLength": 1},
          "color": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
          "spans": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/topic_span"}}
        }
      }
    },
    "observations": {
      "type": "array", "items": {
        "type": "object", "additionalProperties": false,
        "required": ["id", "kind", "topic_ids", "analysis", "evidence"],
        "properties": {
          "id": {"type": "string", "minLength": 1},
          "kind": {"enum": ["transition", "return", "digression", "nested_digression", "loop", "abandoned_thread", "answer_directness"]},
          "topic_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
          "analysis": {"type": "string", "minLength": 1},
          "evidence": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/evidence"}}
        }
      }
    },
    "recommendation_candidates": {"type": "array", "minItems": 3, "items": {"$ref": "#/$defs/recommendation_candidate"}},
    "uncertainties": {"type": "array", "items": {"$ref": "#/$defs/uncertainty"}}
  },
  "$defs": {
    "evidence": {
      "type": "object", "additionalProperties": false,
      "required": ["quote", "start_ms", "segment_id"],
      "properties": {
        "quote": {"type": "string", "minLength": 1},
        "start_ms": {"type": "integer", "minimum": 0},
        "segment_id": {"type": "string", "minLength": 1}
      }
    },
    "topic_span": {
      "type": "object", "additionalProperties": false,
      "required": ["start_ms", "end_ms", "weight", "note"],
      "properties": {
        "start_ms": {"type": "integer", "minimum": 0},
        "end_ms": {"type": "integer", "minimum": 0},
        "weight": {"enum": ["dominant", "touched"]},
        "note": {"type": "string", "minLength": 1}
      }
    },
    "uncertainty": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "target_ids", "reason", "impact"],
      "properties": {
        "id": {"type": "string", "minLength": 1},
        "target_ids": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string", "minLength": 1},
        "impact": {"enum": ["low", "medium", "high"]}
      }
    },
    "recommendation_candidate": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "title", "body", "source_ids", "evidence"],
      "properties": {
        "id": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_-]*$"},
        "title": {"type": "string", "minLength": 1},
        "body": {"type": "string", "minLength": 1},
        "source_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "evidence": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/evidence"}}
      }
    }
  }
}
```

### `logic-analysis.json` schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "pass", "input", "logical_soundness", "observations", "theses", "defects", "strong_moments", "recommendation_candidates", "uncertainties"],
  "properties": {
    "schema_version": {"const": "1.0"},
    "pass": {"const": "logic"},
    "input": {
      "type": "object", "additionalProperties": false,
      "required": ["normalized_metadata", "guest_label"],
      "properties": {
        "normalized_metadata": {
          "type": "object", "additionalProperties": false,
          "required": ["title", "source_url", "duration_ms", "source_format"],
          "properties": {
            "title": {"type": "string", "minLength": 1},
            "source_url": {"type": ["string", "null"]},
            "duration_ms": {"type": ["integer", "null"], "minimum": 1},
            "source_format": {"enum": ["txt", "srt", "vtt"]}
          }
        },
        "guest_label": {"const": "GUEST"}
      }
    },
    "logical_soundness": {
      "type": "object", "additionalProperties": false,
      "required": ["score", "rationale", "evidence"],
      "properties": {
        "score": {"type": "number", "minimum": 0, "maximum": 10},
        "rationale": {"type": "string", "minLength": 1},
        "evidence": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/evidence"}}
      }
    },
    "observations": {"type": "array", "items": {"$ref": "#/$defs/observation"}},
    "theses": {
      "type": "array", "items": {
        "type": "object", "additionalProperties": false,
        "required": ["id", "claim", "status", "premises", "evidence", "conclusion", "observation_ids"],
        "properties": {
          "id": {"type": "string", "minLength": 1},
          "claim": {"type": "string", "minLength": 1},
          "status": {"enum": ["supported", "partially_supported", "unsupported"]},
          "premises": {"type": "array", "items": {"type": "string", "minLength": 1}},
          "evidence": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/evidence"}},
          "conclusion": {"type": "string", "minLength": 1},
          "observation_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}}
        },
        "allOf": [
          {"if": {"properties": {"status": {"const": "supported"}}}, "then": {"properties": {"premises": {"minItems": 1}}}},
          {"if": {"properties": {"status": {"const": "partially_supported"}}}, "then": {"properties": {"evidence": {"minItems": 1}}}}
        ]
      }
    },
    "defects": {
      "type": "array", "items": {
        "type": "object", "additionalProperties": false,
        "required": ["id", "category", "analysis", "evidence", "observation_ids"],
        "properties": {
          "id": {"type": "string", "minLength": 1},
          "category": {"enum": ["unsupported_claim", "contradiction", "non_sequitur", "undefined_term", "overgeneralisation", "missing_qualification", "abandoned_reasoning"]},
          "analysis": {"type": "string", "minLength": 1},
          "evidence": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/evidence"}},
          "observation_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}}
        }
      }
    },
    "strong_moments": {
      "type": "array", "items": {
        "type": "object", "additionalProperties": false,
        "required": ["id", "title", "analysis", "evidence", "observation_ids"],
        "properties": {
          "id": {"type": "string", "minLength": 1},
          "title": {"type": "string", "minLength": 1},
          "analysis": {"type": "string", "minLength": 1},
          "evidence": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/evidence"}},
          "observation_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}}
        }
      }
    },
    "recommendation_candidates": {"type": "array", "minItems": 3, "items": {"$ref": "#/$defs/recommendation_candidate"}},
    "uncertainties": {"type": "array", "items": {"$ref": "#/$defs/uncertainty"}}
  },
  "$defs": {
    "evidence": {
      "type": "object", "additionalProperties": false,
      "required": ["quote", "start_ms", "segment_id"],
      "properties": {
        "quote": {"type": "string", "minLength": 1},
        "start_ms": {"type": "integer", "minimum": 0},
        "segment_id": {"type": "string", "minLength": 1}
      }
    },
    "observation": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "kind", "analysis", "evidence"],
      "properties": {
        "id": {"type": "string", "minLength": 1},
        "kind": {"enum": ["claim_chain", "reasoning_gap", "qualification", "term_definition", "counterexample", "conclusion"]},
        "analysis": {"type": "string", "minLength": 1},
        "evidence": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/evidence"}}
      }
    },
    "uncertainty": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "target_ids", "reason", "impact"],
      "properties": {
        "id": {"type": "string", "minLength": 1},
        "target_ids": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string", "minLength": 1},
        "impact": {"enum": ["low", "medium", "high"]}
      }
    },
    "recommendation_candidate": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "title", "body", "source_ids", "evidence"],
      "properties": {
        "id": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_-]*$"},
        "title": {"type": "string", "minLength": 1},
        "body": {"type": "string", "minLength": 1},
        "source_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "evidence": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/evidence"}}
      }
    }
  }
}
```

## Semantic invariants before synthesis

Validate these conditions after each pass and before either output reaches synthesis:

- `input.normalized_metadata` must equal `normalized.metadata` exactly, including
  `source_url`; both passes must carry the same metadata and `guest_label` is
  exactly `GUEST`.
- All IDs are unique within a pass. All references resolve within that pass;
  every evidence `segment_id` resolves to a GUEST segment, and the evidence
  timestamp lies inside that segment.
- `topic_ids` has at least one item and every id resolves to a structure topic.
  Each topic span has `start_ms < end_ms` and lies within
  `normalized_metadata.duration_ms` when that duration is known.
- Observation evidence has at least one item. In logic, relevant
  `observation_ids` have at least one item and resolve to logic observations.
  Defect and strong-moment `observation_ids` also resolve; a structure
  candidate `source_ids` resolves only to structure observations, while a logic
  candidate `source_ids` resolves to logic observations, theses, defects, or
  strong moments.
- Supported and partially_supported theses have at least one evidence item;
  supported theses have at least one premise. Every thesis, defect, and strong
  moment used as a recommendation source keeps its source evidence.
- Score evidence thresholds apply before a score is accepted: structural chaos
  above 4 has two distinct structural observations and 7 or above has three;
  logical soundness below 7 has a distinct example for each defect category,
  while above 7 has two strong complete moments. When a short transcript cannot
  meet a threshold, reduce certainty instead of fabricating support.
- Each pass emits at least three recommendation candidates, yielding at least
  six pooled candidates for a five-recommendation report. Candidate IDs are
  unique, `source_ids` resolve as above, and their evidence is retained.

## Deterministic synthesis mapping

Synthesis verifies exact equality to normalized.metadata before combining the
passes. Structure `structural_chaos.score` maps to `scores.structural_chaos`;
`topics` maps to `topics`; and each structure observation maps once to
`structure.events`. Logic `logical_soundness.score` maps to
`scores.logical_soundness`; logic theses, defects, and strong moments map to
the same-named report collections. Verify every referenced `segment_id`, quote,
and timestamp against `normalized.json` before producing `synthesis.json`.

Pool both `recommendation_candidates` collections, qualify their local IDs with
their pass (`structure:` or `logic:`), then choose exactly five distinct,
deduplicated candidates across passes. Each final recommendation retains its
qualified `candidate_id` and qualified source IDs. Synthesis selects one
representative evidence into the singular basis; other candidate evidence
remains preserved in the pass artifacts, not all copied into the final report.
Do not create a sixth recommendation or merge two candidates merely to conceal
duplicate evidence.

### Final recommendation shape

The intended final report recommendation shape is the JSON Schema below. Its
`basis` is grounded evidence rather than generic coaching, and `source_ids`
retain the qualified candidate sources.

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["title", "body", "candidate_id", "source_ids", "basis"],
  "properties": {
    "title": {"type": "string", "minLength": 1},
    "body": {"type": "string", "minLength": 1},
    "candidate_id": {"type": "string", "pattern": "^(structure|logic):[A-Za-z0-9._-]+$"},
    "source_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "pattern": "^(structure|logic):[A-Za-z0-9._-]+$"}},
    "basis": {
      "type": "object",
      "additionalProperties": false,
      "required": ["quote", "start_ms", "analysis"],
      "properties": {
        "quote": {"type": "string", "minLength": 1},
        "start_ms": {"type": "integer", "minimum": 0},
        "analysis": {"type": "string", "minLength": 1}
      }
    }
  }
}
```

Every final `source_ids` item uses the same pass prefix as `candidate_id`.

The bundled validators require this recommendation shape. `validate_passes.py` also checks that each recommendation resolves to its candidate and preserves the candidate's source IDs and evidence.

## Structural chaos (0–10; 10 is worse)

Score organisation of the guest's reasoning through topics, returns, and answer progression—not articulation, charisma, pace, filler words, pauses, restarts, listener effects, or host performance.

| Band | Calibration |
|---|---|
| 0–2 | Clear topic progression; answers close opened threads; returns are purposeful and signposted; almost no unclosed detours. |
| 3–4 | Mostly coherent; a small number of recoverable detours or delayed closures; transitions are normally legible. |
| 5–6 | Several un-signposted returns, loops, or weakly connected branches; central progression remains recoverable. |
| 7–8 | Recurrent topic cycling, nested digressions, or abandoned threads make the trajectory difficult to reconstruct. |
| 9–10 | Persistent fragmentation prevents a stable topic trajectory or leaves most consequential threads unresolved. |

For a score above 4, cite at least two distinct structural events. For 7 or above, cite at least three distinct events across the transcript, unless the transcript itself is too short; then reduce certainty rather than inflate the score.

## Logical soundness (0–10; 10 is better)

Score whether the guest's own conclusions follow from stated premises, evidence, examples, and qualifications. Do not grade agreement with a worldview or outside factual truth that the transcript does not establish.

| Band | Calibration |
|---|---|
| 0–2 | Core conclusions repeatedly lack premises, conflict materially, or jump without a connective argument. |
| 3–4 | Some defensible claims, but central reasoning often relies on unsupported assertions, undefined terms, or non sequiturs. |
| 5–6 | Mixed: central claims have partial support, with meaningful gaps, overgeneralisation, or unfinished chains. |
| 7–8 | Most central conclusions are qualified and connected to evidence/examples; limited, local gaps remain. |
| 9–10 | Repeatedly explicit, coherent claim → evidence/example → conclusion chains; qualifications resolve plausible alternatives. |

For a score below 7, substantiate each defect category with a distinct guest quote. For a score above 7, cite at least two logically complete moments and do not erase counterevidence or acknowledged uncertainty.

## Defect taxonomy

Use the narrowest defensible label: `unsupported_claim`, `contradiction`, `non_sequitur`, `undefined_term`, `overgeneralisation`, `missing_qualification`, or `abandoned_reasoning`. A category count represents distinct guest instances only. A host challenge does not become a defect unless the guest's reply establishes one.

## Recommendations

Produce exactly five actionable guest-side revisions. Tie each to an evidenced structural or logical need: signpost a return, close an opened thread, separate claims, define a term, add a premise/example, qualify a scope, or state a conclusion. Do not prescribe delivery coaching, audience manipulation, host interventions, editing, or montage.

## Optional strict evaluation protocol

When the user requests the strict review protocol, after rendering and browser QA write one source-agnostic `evaluation.json` in
the same output directory as `report.html`. It records the review evidence; it
does not add a speech, listener, host-performance, or montage module. The
object has exactly these keys and no others:

```json
{
  "rubric_version": "1.0",
  "artifacts": {
    "normalized_json": "normalized.json",
    "structure_analysis_json": "structure-analysis.json",
    "logic_analysis_json": "logic-analysis.json",
    "synthesis_json": "synthesis.json",
    "report_html": "report.html",
    "screenshots": {
      "desktop": "screenshots/desktop-1440x1000.png",
      "mobile": "screenshots/mobile-390x844.png"
    }
  },
  "browser_checks": {
    "desktop": {"width": 1440, "height": 1000, "no_overflow": true},
    "mobile": {"width": 390, "height": 844, "no_overflow": true},
    "scripts": 0,
    "external_resources": 0,
    "details_count": 2,
    "timestamp_count": 24,
    "validator_pass": true
  },
  "judges": [
    {
      "id": "blind-structure-01",
      "scores": {"S": 96, "E": 97, "V": 95, "T": 98},
      "notes": "Independent source-grounded assessment."
    },
    {
      "id": "blind-evidence-02",
      "scores": {"S": 95, "E": 96, "V": 96, "T": 97},
      "notes": "Independent source-grounded assessment."
    },
    {
      "id": "blind-reuse-03",
      "scores": {"S": 97, "E": 96, "V": 95, "T": 96},
      "notes": "Independent source-grounded assessment."
    }
  ],
  "aggregation": {
    "category_medians": {"S": 96, "E": 96, "V": 95, "T": 97},
    "weighted": 95.85
  },
  "passed": true
}
```

`rubric_version` is exactly `1.0`. `artifacts.normalized_json`,
`artifacts.structure_analysis_json`, `artifacts.logic_analysis_json`,
`artifacts.synthesis_json`, `artifacts.report_html`, and both screenshot paths
are non-empty relative paths that must resolve inside the directory
containing `evaluation.json`, and each target must be a non-empty file. This
makes the evaluation portable and prevents it from silently validating another
run's output.

The gate independently calls `validate_bundle(normalized, structure, logic,
synthesis)` before it validates the rendered report, so missing, stale, or
invalid semantic pass artifacts fail the final gate. Screenshots must be
recognized image files with exact dimensions: desktop `1440×1000`, mobile
`390×844`.

`browser_checks.desktop` is exactly `{width: 1440, height: 1000,
no_overflow: true}` and `browser_checks.mobile` is exactly `{width: 390,
height: 844, no_overflow: true}`. Record browser-observed overflow state there.
`scripts` and `external_resources` must both be zero; `details_count` and
`timestamp_count` are non-negative integers and must equal the static
`<details>` and `.tc` timestamp elements in `report.html`. Set
`validator_pass: true` only after `validate_report.py` succeeded for the
normalized transcript, synthesis report, and rendered HTML. The evaluation
gate independently calls `validate_report` again on
`artifacts.normalized_json`, `artifacts.synthesis_json`, and
`artifacts.report_html`; the Boolean alone is not proof of validity.

The validator can mechanically verify formats, dimensions, static report
content, pass bundles, and score math. `no_overflow` is a browser attestation,
and the judge records are trusted external-agent attestations; neither claim
is treated as a cryptographic proof of browser execution or judge identity.

### What the strict reviewers rate

These four categories assess the **report**, not the guest. They are the
public package's review convention, separate from its guest structure and
logic scores. Every reviewer must read the transcript and report, inspect the
rendered captures, and give concrete findings in `notes` before assigning:

| Key | Category | Inspect |
| --- | --- | --- |
| S | Semantic quality | Correct reconstruction of the guest's argument, relevant distinctions, counterevidence, calibrated uncertainty, and useful source-supported recommendations |
| E | Evidence integrity | Accurate quotations, speaker attribution, timestamps, claim-to-source links, and agreement between findings and supplied evidence |
| V | Visual usability | Readable hierarchy, chart labels and legends, contrast, meaningful colors, desktop/mobile layout, and navigable evidence |
| T | Technical integrity | Valid bundle and HTML, correct deterministic metrics, offline behavior, working timestamps when provided, and absence of broken resources |

Use the same rating anchors in every category: **0–49** means missing or
fundamentally unreliable; **50–69** means major corrections required;
**70–84** means useful but material issues remain; **85–94** means sound with
limited improvements; **95–100** means no material issue found in that
review, with only minor polish remaining. A fabricated quotation or unsupported
central conclusion is a material issue, not polish. Do not assign a score for
an unavailable review dimension; mark the strict review incomplete instead.

The `judges` array has at least three records with unique non-empty `id` values,
non-empty `notes`, and exactly the numeric scores `S`, `E`, `V`, and `T` from 0
through 100. Normalize every score to decimal arithmetic before sorting and
computing category medians (the arithmetic midpoint for an even number of
judges) exactly from those records. Then compute weighted = .55S + .20E + .20V + .05T from the category medians. Do not round or author either aggregate independently.

`passed` must equal the recomputed result. These scores are subjective reviewer ratings, not percentages of accuracy or a universal quality guarantee. The optional strict gate passes only when every median category is at least 85 and the weighted score is at least 95. The validator rejects an under-threshold evaluation even when `passed` truthfully records `false`; it is an evidence artifact for iteration, not a successful handoff. Run it with:

```bash
python3 "<SKILL_DIR>/scripts/validate_evaluation.py" "$OUT_DIR/evaluation.json"
```
