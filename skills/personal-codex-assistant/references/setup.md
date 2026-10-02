# Scoped setup and safe merge

## Host selection

Use `AGENTS.md` and `assets/templates/agents-block.md` for Codex; use `CLAUDE.md` and `assets/templates/claude-block.md` for Claude Code. In the procedure below, “AGENTS file” means that selected host instruction file. Do not create both by default. Claude Code skills go in the selected project’s `.claude/skills/`; install only the selected folders with the root installer’s explicit `--dest`. The root plugin manifests and `agents/openai.yaml` are not Claude plugin configuration.

Keep the existing `.personal-codex` storage name: it is a schema compatibility name, not a dependency on Codex. Both agents use the same context/journal contract when intentionally connected to one workspace. Designate a single writer; never enable competing writers or two parallel sources of truth. An existing OpenClaw context uses a different schema and cannot be replaced by this blank template.

Claude Code loads `CLAUDE.md` as project instructions; there is no assumption that it automatically loads `AGENTS.md`. Scope rules to the selected private workspace, preserving existing imports and content. See the official [skills](https://code.claude.com/docs/en/skills) and [memory](https://code.claude.com/docs/en/memory) documentation.

## Merge procedure

1. Inspect the selected workspace's applicable AGENTS instructions and any context paths the user has designated. Do not scan the whole home directory. If an existing context system already serves the purpose, use it or propose a narrow adapter instead of creating a competing source of truth.
2. Choose one instruction scope with the user: normally a named private workspace or its specific subdirectory. The default proposed files inside that scope are `.personal-codex/context.json` and `.personal-codex/journal.jsonl`. Resolve paths relative to the AGENTS file containing the block, not an arbitrary current working directory. Use another user-selected private directory when appropriate; substitute the two paths consistently in the block. Do not modify an ancestor/global AGENTS file to reach more projects.
3. Prepare a diff showing the exact block, paths and context fields. Copy the blank JSON only when the target does not exist. Existing context is input, not a template to replace. Fill goals only from the user's statements. Confirm the person's timezone if dates or journaling need one; keep it null until known. A future review date is not a schedule.
4. Before storing personal values, ensure the target is private and excluded from publishing. If the selected workspace uses Git, inspect whether the data paths are already tracked. Adding an ignore rule does not untrack a file or remove history: if tracked, choose a new private location and report the finding, without rewriting Git history. An authorized local setup may append a narrowly scoped ignore entry for its new data directory. On POSIX systems create new private directories with mode 0700 and data files with 0600; never recursively change existing permissions. If comparable protection is unavailable, report the limitation before storing sensitive content.
5. Read the entire current AGENTS file. The block uses these literal markers:

   `<!-- personal-codex-assistant:start -->`

   `<!-- personal-codex-assistant:end -->`

   With no markers, append the prepared block, preserving all existing content. With exactly one complete pair, compare its current content with the proposed change and update only that span, retaining user customizations. Multiple, reversed or incomplete markers require resolving the ambiguity before editing; never guess which instructions to discard. When existing instructions conflict, describe the specific conflict and leave that rule unchanged until the user selects the intended behavior. Do not insert a second alignment/journal system beside an equivalent existing one.
6. Re-read immediately before applying the minimal patch; if content changed, recompute the diff. Do not replace the whole AGENTS file. Verify afterward that text outside the owned markers is unchanged, the JSON parses, paths resolve to the intended location, and no personal data entered the public repository. A private backup is optional; it must have the same privacy boundary as the original.
7. Explain what was written, what remains unset, and how to disable it: remove only the marked block or set `enabled` to false in context. `vitality.enabled` disables only the question; `vitality.journal_enabled` controls local recording. Disabling rules does not delete a journal. Remove data only on a separate explicit deletion request.

## Context contract

`context.json` is canonical for this standalone package. The blank template contains no personal values. `schema_version` is 1; `enabled` activates the scoped rules. `timezone` is an IANA name supplied by the user or null. `l1` is a user-authored string or null. Each `l2` item has a stable `id` and `text`. `period_focus` has `text`, optional `l2_id`, and optional ISO `review_on`. Missing context stays null; never fabricate dates or priorities.

Each optional catalog task has `id`, `title`, optional `l2_id`, an explicit `acceptance` condition, `status` (`open`, `in_progress`, `blocked`, `completed`), `completed_on` (ISO local date or null), and `completion_evidence` (an array of short evidence descriptions). Preserve existing unknown fields. A completion date requires a known timezone or an explicit date from the user. Keep the verified evidence even if that date remains unknown. The journal records experience; the context records task status. They are different sources of truth for different facts.
