# Reflect on a Session

![Abstract visual for turning a conversation into a clear reflection](../../assets/reflect.png)

**Turn a meaningful consultation into something you can revisit and use.**

A transcript captures everything that was said. This selfdev skill helps separate the request, the ideas discussed, what you actually accepted, and the actions that fit that understanding. It keeps unresolved questions visible instead of smoothing them into a tidy story.

## What you get

- A source-linked session reflection, including useful distinctions and mechanisms behind examples.
- One or two practice chains connecting a situation, understanding, personal choice, and corresponding action.
- Draft reminders, a morning question, an evening question, and exact quotations to revisit.
- A clear separation between ideas discussed today and applications you reported from before the session.
- Optional accumulated context across sessions, three distinct visual posters, and up to five interpretation diagrams plus two practice diagrams.

It works especially well for IMT consultation material while preserving the participant's agency. “The consultant proposed this” and “I accepted this” remain different statements. An attractive summary is not evidence that a cause has been established or lasting change has occurred.

## Try it

```text
Use $reflect-on-session with this transcript.
Create a reflection with source references, proposed versus accepted understandings,
and one or two practice chains. Keep uncertain interpretations in a backlog.
Then make editable diagrams for the chains supported by the session.
```

**Input:** a complete transcript with identifiable speakers; optional prior summaries and context. **Output:** Markdown reflection; optional context records, SVG diagrams, and generated posters. The skill does not retrieve recordings or transcribe audio itself.

## Requirements and privacy

Text processing needs only an assistant that can read the supplied transcript. SVG output requires file-writing support; visual verification needs an SVG renderer. Posters require an image-generation tool, which may have a separate cost. Without it, the skill provides clearly labeled image prompts.

Use only transcripts you are entitled to process. The skill does not upload them, message participants, or sync a CRM by default. Personal details should be removed from prompts sent to an external image service unless their disclosure was explicitly authorized.

**Release status:** portable workflow and original output guides. The public adaptation preserves source attribution, client choice, accumulated context, and the optional visual sequence. No recording connector, image generator, or external synchronization is bundled. End-to-end output depends on the chosen assistant and tools.

[Open the skill](../../skills/reflect-on-session/SKILL.md) · [Fictional worked example](../../examples/reflect-on-session/example.md) · [Back to the collection](../../README.md)

**По-русски:** из своей консультации — проверяемое саммари, новые понимания с отметкой принятия, связки с действиями и, по желанию, визуальные напоминания. Гипотеза, выбор и результат не смешиваются.
