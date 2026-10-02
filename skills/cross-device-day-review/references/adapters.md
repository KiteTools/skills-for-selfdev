# Source preparation and adapter boundaries

Version 0.3.1 ships **one executable adapter: the normalized JSON contract**. The following are preparation instructions, not connectors installed by this package. No credentials, API calls, screen recording or live log collection are configured.

| Source | Prepare privately | Do not infer |
| --- | --- | --- |
| ActivityWatch desktop | Export selected source data. Retain actual not-AFK intervals. For foreground activities, intersect their intervals with the matching active-device intervals before normalization; then review episode labels | Foreground app alone is not human attention; different computers must have distinct source aliases |
| ActivityWatch phone / imported app-focus data | Use only intervals whose meaning and source you verified; preserve gaps and date offsets | An imported focus stream is not automatically Apple Screen Time or complete phone coverage |
| RescueTime aggregate export | Retain the original aggregate and its resolution in a private note. This CLI accepts exact intervals only; use untimed episode entries if reliable bounds are absent | A five-minute bin with 120 seconds is not a known continuous two-minute interval. Do not guess a host from gaps in another tracker |
| Computer History summary | Extract reviewed activities and genuinely evidenced bounds. Retain its coverage window as provenance, not elapsed activity | A six-hour summary is not six hours of one activity; a window title does not prove attendance |
| Codex / Claude / other agents | Prepare only completed job ID/start/end metadata in a machine source; strip prompt bodies, working paths, tokens and session text | A job's runtime is not the owner's time; open or unfinished turns are not completed jobs |
| Calendar | Use attendance evidence or an explicit report before adding an interval | A scheduled meeting alone is a plan |
| Personal notes | Use explicit self-reported bounds or unknown activities; apply corrections to the normalized records first | Memory estimates without bounds are not exact intervals; a stated decision is not a completed action |

No third-party collector code is bundled. Installing this skill neither licenses nor installs another service. Consult the selected tool's current export instructions separately. If normalization requires an unavailable connector, process the supplied material and retain the missing source; do not enlarge access automatically.

For a meeting with background notes, assign one episode ID only after reviewing the evidence. For corrected attendance, replace superseded bounds as specified in [input.md](input.md); this CLI has no automatic precedence mechanism.
