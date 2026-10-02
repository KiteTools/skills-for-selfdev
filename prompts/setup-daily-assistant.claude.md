# Claude Code prompt: set up my daily assistant

Copy the complete block into Claude Code. The system will use your context, not the author's personal data.

```text
Set up my personal daily assistant from https://github.com/KiteTools/skills-for-selfdev.
I want to choose what matters today, keep ideas and results, notice my experience,
and compare intentions with outcomes. Reuse the supplied components instead of
rebuilding their runtime. Respond in my language.

1. Obtain current main in a separate source checkout, recording its commit SHA.
   Preserve any existing modified checkout. Read README.md,
   docs/guides/daily-assistant-claude-code.md, docs/system-map.md, and the selected
   skills with their required setup references. Keep personal files outside the
   public checkout. My choices determine goals and authorization; repository
   examples do not supply my beliefs, relationships or personal history.

2. Inspect the OS, actual Claude Code environment, Git and Python. For Telegram,
   also inspect Node.js, OpenClaw and the installed release's supported interfaces.
   Read existing CLAUDE.md and only the personal sources I designate. Do not scan
   my whole home, messages or raw agent history. Preserve existing settings.

3. Ask only for missing decisions, in short groups: private workspace, language,
   timezone, what matters to me, current focus, permitted notes, whether I want a
   state journal and its wording, and whether I want Telegram or on-demand use.
   Explain L1/L2 in plain language; do not require a complete life philosophy.
   Start with the smallest useful setup and leave unknowns unknown. If tasks already
   live in another file or service, preserve that canonical source; do not create a competing catalog.

4. For Claude Code use personal-codex-assistant (a historical compatibility name)
   and weekly-review. Offer evening-ten separately; add reflect-on-reaction and
   reflect-on-session only if useful. Copy selected complete skill folders into
   the private project's .claude/skills using scripts/install.py with explicit
   --dest after inspecting --help. The root plugin.json is not a Claude plugin.
   Use personal-codex-assistant/assets/templates/claude-block.md in CLAUDE.md;
   preserve all content outside its markers. Do not assume Claude loads AGENTS.md.
   Retain the compatible .personal-codex data paths. Codex itself is not required.
   Do not change global agent settings.

5. Personalize context, optional journal and on-demand morning/evening/week flows.
   Let me choose a morning step in my own words; show the task catalog on request.
   Distinguish suggestion, interest, decision, attempt and outcome. Close only a
   specific existing task with evidence. Do not infer my state from tone, app use
   or task completion. If journaling is enabled, record explicit ratings once;
   an absent rating is not zero. Build a review from available evidence before
   asking about concrete gaps. A meeting with notes is one overlapping episode;
   agent machine time is not my human time. Partial exports are not a complete day.

6. Evening Ten uses materials I supply or designate; it does not collect activity.
   Look for new possibilities, including ways to participate in life beyond more
   tools and task lists. Cite evidence, check repetition, and do not execute a
   suggestion or turn interest into a task. Do not silently enable screen capture,
   Computer History, ActivityWatch, RescueTime or raw Claude/Codex log access.
   This package has no general cross-device activity collector.

7. If I choose Telegram, follow personal-daily-assistant and its installation
   contract. This is an OpenClaw runtime with separately configured accounts.
   Claude Code does not automatically supply its subscription, model or a background
   scheduler to OpenClaw. The runtime supports macOS/Linux. Native Windows is not
   supported; propose an existing WSL/Linux environment with private Linux storage,
   or keep the on-demand Claude setup working. WSL is not independently verified.
   Do not claim Windows path translation fixes POSIX locks. Do not install WSL or
   move to a server without my choice. Use my own bot, numeric owner ID and a path
   to its private token file; never request or print the token in chat. Text only,
   owner-only bot access, loopback Gateway. Preserve existing OpenClaw accounts and
   channels. If isolation requires changing their access, propose a separate instance
   and obtain my choice. Do not enable voice messages or audio.

8. Only for the selected Telegram branch: prepare an installer dry run for a fresh private runtime workspace. Fill only
   context values I confirmed. Do not invent required Telegram context values to pass
   validation: clarify them or keep on-demand use. Back up existing config before changing it. Upgrade
   an existing installation side by side, stopping old writers before cutover and
   preserving history. Do not duplicate jobs. Claude context and OpenClaw context
   have different schemas: designate a canonical source and map selected values
   explicitly; never point two writers at one JSON or journal. Installation writes
   declarations, not a live bot. Show actual local schedule times and sources.
   Activate jobs and send one test only after I choose activation; honor permission
   already given without repeatedly asking. Enable Telegram Ten only with a working
   preparation/import flow: an install flag is not a generator. Missing prepared
   data means no invented Ten; evening reflection stays available independently.

9. Verify skill discovery, JSON, private paths, preservation of unrelated CLAUDE.md
   content and absence of personal files in Git. For Telegram run supplied tests
   and verify.py, then separately check effective config, loaded plugin, unique
   schedules, actual delivery and exactly one saved event. Test with synthetic
   fixtures outside my live journal. Complete independent local work if an external
   integration is unavailable, and name the remaining gap. A dry run is not a live bot.

10. Leave concise instructions for morning, ideas/success/state, evening/week,
    data location, disabling schedules, backups and upgrades. Write versions,
    selected modules, paths and checks to a private setup-report.md without secrets.
    Report: working and verified; configured but unverified; intentionally omitted.
    Continue autonomously within the agreed scope, asking only for meaningful
    personal choices and missing authorization.
```

[Components and limits](../docs/guides/daily-assistant-claude-code.md) · [Русский промпт](setup-daily-assistant.claude.ru.md)
