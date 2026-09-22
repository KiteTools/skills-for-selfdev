# Fictional example: finish a small prototype

**English** · [Русский](example.ru.md)

All values and dialogue below are invented for this example. This is illustrative output, not a claim that a real user completed a task or reported a rating. Never preload it into a personal journal.

## Context chosen by the fictional user

```json
{
  "schema_version": 1,
  "enabled": true,
  "timezone": "Etc/UTC",
  "l1": "Make useful things with room for curiosity",
  "l2": [{ "id": "craft", "text": "Finish small tools and learn from using them" }],
  "period_focus": { "text": "One working note-filter prototype", "l2_id": "craft", "review_on": null },
  "tasks": [{
    "id": "sample-01",
    "title": "Add a tag filter to the local notes prototype",
    "l2_id": "craft",
    "acceptance": "Selecting a tag shows matching notes; clearing it restores all notes; relevant checks pass",
    "status": "open",
    "completed_on": null,
    "completion_evidence": []
  }],
  "vitality": { "enabled": true, "journal_enabled": true }
}
```

The user has explicitly enabled journaling in a private workspace. The shipped blank template leaves it disabled.

## Opening and completion boundary

User: “Complete sample-01. Keep it local.”

Assistant: “Make useful things with room for curiosity → finish small tools → one working prototype → a checked tag filter.”

The assistant implements and verifies the filter. In this fictional scenario, an automated check confirms selecting a tag narrows the result and clearing it restores all notes. Only then does the existing task become `completed`, with those concrete checks recorded as evidence. Nothing is described as deployed.

If the filter had only been discussed, or a check had failed, the task would remain unfinished and no vitality question would follow.

Assistant: “The local tag filter is implemented; filtering and clearing checks pass. Vitality after the work: −− / − / = / + / ++? What happened? Was there anything between you and the living process? ‘Nothing’ is a valid answer.”

User: “+ I enjoyed making the first version work. I kept worrying it should look more polished.”

## One illustrative journal record

```json
{"id":"00000000-0000-4000-8000-000000000001","recorded_at":"2026-01-12T16:30:00+00:00","type":"vitality_response","task_id":"sample-01","result":"Local tag filter implemented; filtering and clearing checks passed","rating":"+","text":"+ I enjoyed making the first version work. I kept worrying it should look more polished.","supersedes":null}
```

The timestamp and UUID are synthetic. A real run obtains the current time and generates its own event ID. The response records the user's experience; it does not diagnose perfectionism, prove a lasting change or alter their goal. A later correction would append a new record referencing this one.

[Skill overview](../../docs/skills/personal-codex-assistant.md) · [System map](../../docs/system-map.md)
