# Fictional example

Input: “Around age 24, I moved to another city for a course. It was exciting, but I missed my friends. I finished the course about a year later.”

| When | Event | Reported impact | Source | Status |
| --- | --- | --- | --- | --- |
| Around age 24 | Moved to another city for a course | Excitement and missing friends | note-001, sentence 1–2 | extracted |
| Around age 25 | Finished the course | Not stated | note-001, sentence 3 | extracted |

The second age is an approximation calculated from the supplied account. Keep that derivation visible; do not turn it into an exact date.

```json
{
  "schema_version": 1,
  "events": [
    {
      "id": "event-001",
      "subject": "self",
      "title": "Moved for a course",
      "time_as_stated": "Around age 24",
      "start_age": 24,
      "end_age": null,
      "precision": "approximate",
      "description": "Moved to another city to attend a course.",
      "reported_impact": "Exciting; missed friends.",
      "sources": [{"id": "note-001", "location": "sentences 1–2"}],
      "status": "extracted",
      "open_questions": []
    }
  ]
}
```

This is a local interchange example, not a validated import format for another application. Unknown ages and dates remain `null`; omit identifying details that the destination does not need.
