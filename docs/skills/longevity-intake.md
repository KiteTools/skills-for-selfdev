# Longevity intake: explore a conditional Life Function

**English** · [Русский](longevity-intake.ru.md)

![Illustration of the explore workflow](../../assets/explore.png)

Bring the facts you already know about your family and life events. The assistant helps fill the meaningful gaps one question at a time, then explains the scenarios returned by the Longevity app.

**Try it:**

> Use longevity-intake with my life-event notes. Explain where the data goes, reuse what is already known, and ask one question at a time. Show the assumptions with the first scenario comparison.

## What you receive

A structured intake, a view of missing or approximate information, and an explanation of the app's conditional scenarios. Optional refinement follows the first result rather than delaying it indefinitely.

Longevity uses an **Androphysics model under stated assumptions**. It is not medical advice, a biological forecast or a prediction of when someone will die. Treat comparisons as model outputs for reflection.

## Start here

1. Open the [live app](https://app.imt.dev/longevity-mcp/).
2. Load the [skill](../../skills/longevity-intake/SKILL.md) in your agent and select English or Russian in the app.
3. If your host exposes the page's WebMCP tools, the agent can update the form with structured facts. Otherwise, use the visible form and let the agent help prepare the entries. Installing this skill does not add WebMCP support to a host.

## Accounts and privacy

The current public app requires **no account**. Personal facts stay in the open tab's JavaScript memory; reload, closing the tab or Clear deletes them. It accepts structured facts, not raw conversations, transcripts or audio. Your AI platform's conversation retention is separate.

The agent shows the app's privacy notice before submitting anything and uses only the information relevant to this intake. Keep any saved copy in your own private location.

## Requirements and status

**Bundled:** the intake skill and integration reference. **External:** the live application and its calculator. A browser is required for the app; page-tool access is optional. No calculator, backend or login service is installed by this repository.

Source verified on 2026-09-22 against the app's [README](https://github.com/KiteTools/longevity-webmcp/blob/main/README.md) and [WebMCP schema](https://github.com/KiteTools/longevity-webmcp/blob/main/src/webmcp.ts). The skill reads the live contract before submissions so it can follow future schema changes.

[Open the skill](../../skills/longevity-intake/SKILL.md) · [Application source](https://github.com/KiteTools/longevity-webmcp) · [Prepare a life timeline](life-events.md)

[Back to Skills for Selfdev](../../README.md)
