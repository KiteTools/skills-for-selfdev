---
name: clean-transcript
description: Make an ASR transcript readable while preserving the speaker's words, meaning, sequence, and available timestamps. Use to remove transcription noise and correct terms with a supplied glossary, not to summarize a talk.
---

# Clean transcript

Produce readable speech, preserving how the explanation unfolds. Keep the raw transcript unchanged. Ask for the transcript if only a recording title is supplied; transcription of audio requires a separately available tool.

## Editing rules

- Correct punctuation, paragraph breaks, and unmistakable recognition errors. A glossary supports a correction only when nearby context identifies the term. Similar sound alone is insufficient. Preserve meaningful homonyms, qualifications, negations, and the order of named concepts.
- Retain explanations, concrete examples, analogies, complete stories, and substantive questions followed by an answer. Preserve attribution. Do not turn a participant's claim into the instructor's claim.
- Remove technical chatter, greetings, empty filler, and exact repetitions only when they contribute no meaning. In a lecture, omit routine check-in answers only if the instructor adds no substantive response. For interviews or consultation records, preserve all substantive speaker turns by default; the user may need interaction detail.
- Repeated dictation of one definition may be consolidated into one faithful wording. Keep materially different versions and qualifications. A later reference definition must not silently replace the wording of an earlier talk.
- Preserve the speaker's first-person voice. Do not convert speech into an essay, a summary, a diagnosis, or a set of stronger claims.
- Keep uncertain words as `[unclear: original wording]` or list them for review. Never invent a missing sentence. If timestamps are sparse, multiple headings may share the same documented interval. Do not estimate more precise timing.

## Workflow and output

Read the entire source, apply a supplied glossary if available, and identify meaningful blocks longer than a sentence. Write `readable-transcript.md` with a source filename, an editing note, block headings, and source time intervals or paragraph IDs. Keep actual speaker labels where they matter.

Write `transcript-review.md` for uncertain terms, substantive alternatives, and material omissions with source locations. A list of every comma change is unnecessary. If there are no unresolved items, say so after checking.

Before handing off, compare beginning, end, every definition, negation, number, and edited term with the source; check block coverage across the full recording. Describe the result as an editorially cleaned transcript, not a verbatim certified transcript. No external account or upload is needed for this text workflow.
