# Analyze an expert interview

![Skills for Selfdev: source-grounded learning, readable transcripts, editable diagrams, and interview review](../../assets/learn.png)

**See the argument inside the conversation.**

You may know a subject well and still lose a thread while explaining it. This skill gives a guest speaker a source-linked map of the interview: topics, detours, unfinished arguments, strong explanations, and concrete revisions.

| | What to expect |
| --- | --- |
| Input | One transcript with explicit HOST / GUEST roles, in TXT, SRT, or VTT |
| Output | Offline HTML report, normalized source, metrics, evidence files, and review status |
| Useful for | Reviewing your own interview, improving an educational conversation, studying how an expert argues |
| Requirements | Python 3.10+; an AI assistant; independent contexts for semantic review; browser for visual QA |
| Status | Working parser, metrics, renderer, and provenance validators with regression tests; semantic analysis still requires an assistant |

## Try it

> Use analyze-expert-interview on this HOST/GUEST transcript. Analyze the guest's structure and reasoning, support findings with exact quotes, and create an offline HTML report. Clearly state any independent or visual review you cannot perform.

[Open the fictional input example](../../examples/analyze-expert-interview/) · [Read the skill](../../skills/analyze-expert-interview/SKILL.md)

## Two lenses, one source

The structure pass tracks where the discussion goes. The logic pass asks how a claim follows from its premises and examples. Separate passes reduce the chance that one early interpretation dictates the whole review.

The report presents a topic map, structural observations, reasoning gaps, strong moments, and five supported revisions. A very short source that cannot support five revisions gets a limited analysis rather than invented criticisms.

## What the checks establish

The bundled Python tools normalize speaker roles, calculate timing metrics, validate quotations and provenance, and render a self-contained English HTML report. They do not decide whether a criticism is wise or externally fact-check every claim. No speaking-speed, filler-word, audience-manipulation, or personality score is included.

A stricter, optional review protocol records three independent reviewers and browser evidence. Its numeric thresholds are a review convention, not a percentage guarantee of correctness. The normal workflow reports its actual review status without requiring that protocol.

## Run the deterministic part

From the repository root:

```sh
python3 skills/analyze-expert-interview/scripts/parse_transcript.py \
  examples/analyze-expert-interview/interview.vtt /tmp/selfdev-normalized.json \
  --title "Fictional interview: choosing a weekly practice"
python3 skills/analyze-expert-interview/scripts/compute_metrics.py \
  /tmp/selfdev-normalized.json /tmp/selfdev-metrics.json
python3 -m unittest discover -s skills/analyze-expert-interview/tests -v
```

Use a new output path if those temporary files already exist. The remaining semantic passes need the assistant to read the transcript; running these two commands alone does not produce a reviewed analysis.

[Back to Skills for Selfdev](../../README.md)
