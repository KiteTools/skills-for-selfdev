---
name: analyze-expert-interview
description: Analyze the structure and reasoning of an expert guest in a HOST/GUEST transcript and produce a source-linked offline HTML report. Use for interview or talk review, not speech delivery scoring or medical/personality assessment.
---

# Analyze expert interview

Help a speaker see where their explanation holds together, loses a thread, or needs a better premise. The report analyzes the guest; host questions supply context. It does not measure charisma, delivery, listener psychology, or factual truth beyond the supplied evidence.

## Requirements and honest status

Use one clearly labelled HOST + GUEST transcript in TXT, SRT, or WebVTT. The included tools need Python 3.10+ and its standard library. Independent semantic passes require separate agent contexts; complete visual QA requires a browser or equivalent renderer. Keep the user's source private and create outputs in a fresh directory.

If roles or timing are ambiguous, ask for a corrected source. Do not guess speaker attribution. TXT may have start-only timestamps: its final duration remains unknown. A YouTube URL is optional and does not grant permission to upload the transcript anywhere.

The semantic pipeline requires independent structure and logic passes. If independent contexts are unavailable, deliver normalization and metrics plus an explicitly unreviewed draft; do not claim independent review. Record available evidence, missing checks, and the result status in `review-status.md`.

## Run

Resolve `SKILL_DIR` to the directory containing this file. Work in a fresh local `OUTPUT` directory without replacing a prior report.

```sh
mkdir OUTPUT
python3 SKILL_DIR/scripts/parse_transcript.py INPUT.vtt OUTPUT/normalized.json --title "Interview title"
python3 SKILL_DIR/scripts/compute_metrics.py OUTPUT/normalized.json OUTPUT/metrics.json
```

1. Read [analysis-rubrics.md](references/analysis-rubrics.md) and [report-contract.md](references/report-contract.md). Give the complete normalized transcript separately to two independent contexts. The structure pass must not see the logic pass; the logic pass must not see the structure pass.
2. Write `structure-analysis.json` and `logic-analysis.json` using their reference schemas. The structure pass maps topics, transitions, returns, digressions, loops, abandoned threads, and answer directness. The logic pass extracts defended theses, evidence and examples, conclusions, unsupported steps, contradictions, undefined terms, and strong complete arguments. Preserve uncertainty and source segment IDs.
3. Validate both pass files before synthesis. Synthesis receives both passes, normalized source, and computed metrics, checks every quotation, resolves disagreements through evidence, and emits `synthesis.json`. Do not recompute deterministic metrics in prose.
4. The current report format selects five distinct evidence-backed revision candidates. If the source cannot support five, stop at a limited source analysis and explain this format limitation rather than inventing defects or padded advice.

```sh
python3 SKILL_DIR/scripts/validate_passes.py OUTPUT/normalized.json OUTPUT/structure-analysis.json OUTPUT/logic-analysis.json
# After creating synthesis.json:
python3 SKILL_DIR/scripts/validate_passes.py OUTPUT/normalized.json OUTPUT/structure-analysis.json OUTPUT/logic-analysis.json OUTPUT/synthesis.json
python3 SKILL_DIR/scripts/validate_report.py OUTPUT/normalized.json OUTPUT/synthesis.json
python3 SKILL_DIR/scripts/render_report.py OUTPUT/synthesis.json OUTPUT/report.html --normalized OUTPUT/normalized.json
python3 SKILL_DIR/scripts/validate_report.py OUTPUT/normalized.json OUTPUT/synthesis.json OUTPUT/report.html
```

Check the parser/validator `--help` when needed. Stop on a failed gate; preserve diagnostic files and do not present an invalid HTML report as complete.

## Review and handoff

Read [visual-system.md](references/visual-system.md). Inspect the HTML at 1440×1000 and 390×844: readable headings and tables, no page overflow, accessible SVG labels, keyboard access, and functioning native disclosures. The report must have no runtime network requests. YouTube timestamp links are optional user navigation, not background requests. Save screenshots when supported.

Deliver the source normalization, metrics, both semantic passes, synthesis, HTML, and `review-status.md`; state what was actually reviewed. Quote validation proves text traceability, not the correctness of an interpretation. Scores are rubric-based judgments with explicit direction, not measures of personal worth or scientifically validated accuracy.

An **optional strict review protocol** is preserved in the rubrics and `validate_evaluation.py`. Use it only when explicitly requested and three independent reviewers and browser captures are available. Its 85/95 thresholds are conventions for those reviewer ratings, not a promise of 95% accuracy. Never manufacture reviewers, screenshots, or scores to meet the gate. A failed strict review remains a failed strict review even if the basic report validates.
