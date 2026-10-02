# How the skills form a personal system

**Using Claude Code?** [Build your daily assistant: copyable prompt and component map](guides/daily-assistant-claude-code.md).

**English** · [Русский](system-map.ru.md) · [Catalog](catalog.md)

**Start with one useful result. Connect practices when you want to continue.**

![Skills for Selfdev: material, understanding, choice and review, supported by private context and an optional daily rhythm](../assets/system-map.png)

## Follow one concrete example

After a meeting, a note says: “I interrupted a colleague and defended my proposal before clarifying the question.” This is a fictional example.

1. **Keep the material.** Transcript Cleanup makes the record readable while retaining the speaker's words and uncertainties.
2. **Explore it.** Reaction Reflection helps examine the episode. Disco offers another entry through recurring reactions and the metaphor of inner voices. If a consultation already took place, Session Reflection works from its transcript. You do not need all three.
3. **Separate understanding from a guess.** “I treat every question as rejection” may be a hypothesis. Personal context records an understanding as accepted only when the person recognizes and chooses it.
4. **Choose an action.** The person accepts: “I will clarify the question first; a question does not itself mean rejection,” and chooses to ask before answering at the next meeting. Evening Ten may suggest a move; the choice belongs to the person.
5. **Review what happened.** A later journal entry records the actual experience. Weekly Review compares it with the intention. One episode does not establish lasting change.

[Read the full fictional walkthrough →](../examples/system-walkthrough/example.md)

## Two ways in, with an optional daily layer

| What you need | Where to start | What you set up |
| --- | --- | --- |
| One result from your material | [An individual practice](catalog.md) | One skill; work in the current conversation |
| Continuity around your focus and results | [Personal Codex Assistant](skills/personal-codex-assistant.md) | Empty personal-context templates and agreed rules in a selected private workspace |
| Daily messages and a journal | [Personal Daily Assistant](skills/personal-daily-assistant.md) | A separate OpenClaw/Telegram runtime with your accounts and explicit schedule setup |

Manual notes are enough. Computer History, Telegram, Personal Cabinet and other services are separate optional connections.

## What each part contributes

| Stage | Tools | What moves forward |
| --- | --- | --- |
| Preserve source material | [Transcript Cleanup](skills/clean-transcript.md), [Life Events](skills/life-events.md), [Building Your Life Function](integrations/soov.md) | Reviewed text or an event with source and uncertainties |
| Learn and understand | [Learning Notes](skills/learning-notes.md), [Expert Interview](skills/analyze-expert-interview.md), [Session Reflection](skills/reflect-on-session.md), [GoR](skills/reflect-on-reaction.md), [Disco](skills/disco-mirror.md) | An explanation, provisional interpretation or explicitly accepted understanding |
| Keep a chosen focus | [Personal Codex Assistant](skills/personal-codex-assistant.md) | Personal context, accepted understanding and chosen outcome |
| Notice further possibilities | [Evening Ten](skills/evening-ten.md) | Suggestions; interest does not create a task |
| Record experience and reconsider | [Daily Assistant](skills/personal-daily-assistant.md), [Weekly Review](skills/weekly-review.md) | Explicit self-reports, evidence of results and corrections |
| Make material usable | [SVG Reconstruction](skills/reconstruct-svg.md), [Personal Cabinet](integrations/lk-sendpulse.md), [Longevity](skills/longevity-intake.md) | An editable diagram, a working interface or input for a separate conditional model |

These are possible connections, not a mandatory pipeline. A lecture can end with useful notes. An insight need not become a task; a journal entry need not trigger analysis.

## Hand off a small, reviewed context

Carry source and date, event, claim status, accepted understanding, chosen action and known outcome. Link the source instead of copying an entire private history. A [fictional JSON example](../examples/system-walkthrough/handoff.json) illustrates this reading convention; it is **not a Daily Assistant import API**.

- Observation, self-report and model interpretation remain distinct.
- Suggestion → interest → choice → attempt → outcome are different states, with no automatic advancement.
- Update context only within an authorized setup or requested save. A model's reply does not become the person's belief.
- Missing records remain gaps. Computer activity does not reconstruct someone's offline life.

Skills do not automatically synchronize their files. The person or an authorized agent carries the selected context. Daily Assistant data uses its own validated commands.

## What is available now

The collection has 14 skills. Personal Codex Assistant, Evening Ten, Weekly Review and GoR work on demand. Personal Daily Assistant includes a separate local runtime; its [guide](skills/personal-daily-assistant.md) identifies supported scenarios and activation steps. Conversational skills do not automatically become Telegram workflows.

Personal Cabinet and SOOV have separate repositories. This collection does not provide shared login, a common database or automatic synchronization across all apps. Prism remains an external tool.

[Cross-device day review](skills/cross-device-day-review.md) supplies evidence for this cycle: selected day records → shared understanding → reflection and chosen focus. The offline CLI merges normalized intervals and preserves gaps; collectors and daily-runtime synchronization are not installed.

[Install](getting-started.md) · [Privacy](../PRIVACY.md) · [Home](../README.md)
