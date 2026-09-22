---
name: longevity-intake
description: Help a person complete the Longevity Life Function interview from known facts and a few focused questions, then explain the app's conditional Androphysics scenarios. Use with the public Longevity app; it does not provide medical prognosis or predict a date of death.
---

# Longevity Intake

Use the public [Longevity app](https://app.imt.dev/longevity-mcp/) to build a structured Life Function and compare scenarios under the app's stated assumptions. Do not recreate its formula from memory. The app is maintained separately at [KiteTools/longevity-webmcp](https://github.com/KiteTools/longevity-webmcp).

## Choose an available route

Discover whether the current host exposes the page's WebMCP tools. They are page-scoped capabilities, not automatically available just because this skill is installed. If unavailable, open the app with an available browser tool or give the link and guide the user through the visible form. Prepare a small reviewable fact sheet and ask the user to transfer it manually if needed. Do not claim a submission or calculation occurred without page/tool readback.

Read [references/app-contract.md](references/app-contract.md) when using the integration. The live manifest and registered schemas take precedence over this reference.

## Interview with WebMCP

1. Call `get_intake_manifest`. Explain its `privacyNoticeForClient` before submitting any facts. Do not set `privacyNoticeDelivered` until the notice has actually been delivered. No account is required by the current app; conversation retention is controlled separately by the agent platform.
2. Use only relevant facts available in the authorized task context. Extract the smallest structured subset; never send raw chats, transcripts or audio. Preserve approximate values and unknowns. Obtain any specific consent required by the host immediately before sending the affected fact; omit declined facts.
3. Submit permitted known facts with `submit_known_facts`. Use stable IDs for people/events and a shared `episodeId` for multiple criteria from the same episode, so retries and one life period do not become duplicate records.
4. Follow `get_next_interview_step` or `nextInterviewStep` returned by the submission. Ask exactly one question per message. Accept an approximate answer or “I don't know”; clarify at most once. Record `acknowledgedUnknowns` only for explicitly unknown supported fields, not for every missing field.
5. Submit the structured answer with `submit_interview_answers` and inspect the result. Stop required collection at `phase=preliminary_ready`. Call `get_scenario_comparison` once the core is ready; optional refinement comes after the first result.

Do not invent event scores, causes, influence coefficients or missing family history. Distinguish client report from agent inference. Show assumptions and incomplete information alongside any comparison.

## Result

Explain what inputs were used, which assumptions the app supplied, what differs between scenarios, and one practical question the person wants to explore next. The output is a conditional Androphysics model, not medical advice, a biological forecast or a death-date prediction. Do not present a numerical scenario as a measured biological fact.

Keep the open-tab lifetime visible: the current app stores personal facts in JavaScript memory; reload, closing the tab or Clear removes them. If the user wants to retain a result, help save a private copy in a location they choose using available export or file capabilities. Never imply that a skill installation provides cloud storage or authentication.
