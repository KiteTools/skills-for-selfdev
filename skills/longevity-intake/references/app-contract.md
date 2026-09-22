# Longevity integration contract

Source checked on 2026-09-22: [README](https://github.com/KiteTools/longevity-webmcp/blob/main/README.md) and [WebMCP registration/schema](https://github.com/KiteTools/longevity-webmcp/blob/main/src/webmcp.ts). Always retrieve the live contract before writes.

| Tool | Role |
| --- | --- |
| `get_intake_manifest` | Current schema guidance, privacy notice, supported event criteria and interview policy |
| `submit_known_facts` | Initial structured facts and next interview step |
| `get_intake_status` | Completeness, assumptions and remaining gaps |
| `get_next_interview_step` | One question or a preliminary-ready stop signal |
| `submit_interview_answers` | Structured facts extracted from one answer |
| `get_scenario_comparison` | Conditional comparison after the core is ready |
| `get_missing_questions` | Compatibility view; do not turn it into a long questionnaire |

Submission fields include `privacyNoticeDelivered: true`, optional `profile`, `coefficients`, `ancestors`, `events` and `acknowledgedUnknowns`. Exact requirements come from the current schema. The three coefficients, when submitted, are `father`, `mother`, and `environment`. Do not assign them from a guess.

Event fields include stable `id`, optional `episodeId`, `person` (`father`, `mother`, `client`), a supported `criterion`, `score`, ages, note, layer and source metadata. `sourceKind` distinguishes agent context, agent inference, user text and user voice; labeling an inference does not make it a confirmed fact. Avoid submitting unsupported inference simply to complete a form.

The EN/RU switch replaces tool registrations with a matching language contract. Rediscover tools after changing language. Tools run in the open tab; this is not a remote MCP server URL to add to an agent configuration.

The app's current privacy design has no account, database, analytics, cookies or server intake endpoint. The published app uses `connect-src 'none'`. These app properties do not describe the agent platform, its transcript retention or a different deployed fork. Verify a changed destination before sending personal information.
