# Building Your Life Function

[English](soov.md) · [Русский](soov.ru.md)

See your life as a whole: when you developed, which turning points changed its direction, and which periods repeat. A visual chart helps connect individual events, notice patterns, and better understand what supports your development. From this picture, it becomes easier to see what you want to continue and what you want to change.

![Life Function charts: parents’ histories and the person’s history alongside a calculated curve](../../assets/life-function.png)

Without an outside perspective, it can be difficult to see how far you have come. What have you created? When did new possibilities emerge? Which encounters, decisions, and changes started a period of growth? Where did a familiar story repeat?

The Life Function brings this path together in a visual chart. It reveals rises, declines, long periods of stability, and turning points. Each part of the chart is grounded in concrete events and results: family, relationships, work, learning, creativity, and your contribution to other people’s lives.

You reconstruct your history manually or from a conversation transcript. You compare periods and explore possible connections between events and changes in your life. If you choose, you can add your parents’ histories to see similarities and differences: what repeats, and where you are already making your own path.

The most useful part of this work is continuing the chart. What new understanding could help you change the usual course of events? Which decisions and actions follow from it? What do you want to create in the next period of your life?

The past gives you material for understanding. The future remains open — you gradually fill it with your decisions and results.

[Detailed page and chart (Russian)](https://app.imt.dev/artifacts/life-function/)

The idea emerged while completing the homework for seminar AF2.8. The former name was SOOV / СООВ. The image shows the original prototype; chart building has not yet been ported to the separate public application.

## Current public version

SOOV preceded Longevity. Its original screen supported manual life-event entry and extraction from a transcript. That screen was identified in [Longevity's source](https://github.com/KiteTools/longevity-webmcp); it belongs to the project's earlier event workspace, before the later model mode.

The separate [KiteTools/soov application](https://github.com/KiteTools/soov) now implements a deliberately smaller task: events, sources, human review, local storage, and transfer. It was written afresh. It does not include the legacy model, scores, family coefficients, calculations, or AI server. Old SOOV/Longevity files are not directly compatible with its new schema.

## What the application does

- Add, edit, delete, and search events with a precise or partial date, an age range, or unknown timing.
- Keep the person's own assessment separate from the event description and preserve source notes and quotes.
- Review imported JSON and save only explicitly selected events.
- Store records in the browser's IndexedDB; export JSON backups and CSV for spreadsheet viewing.
- Restore a backup by merging or explicitly replacing records. Repeated identical imports do not create duplicates; conflicting IDs stop a merge without partial writes.

No account, AI API, or server database is required for this local workflow. Run the application with the commands in its [README](https://github.com/KiteTools/soov#run-locally), or serve its `dist/` directory on your own static host. The interface is in Russian; operator documentation is available in both languages.

## From a transcript

Use the [life-events skill](../skills/life-events.md) to prepare a source-bound draft in your chosen AI assistant. For application import, use SOOV's included prompt and [versioned schema](https://github.com/KiteTools/soov/blob/main/schema.json). Review the returned records before saving. Arbitrary JSON or a legacy case file is not automatically a valid import.

SOOV itself does not upload or process the transcript. If you give a transcript to a cloud assistant, that is a separate data transfer governed by your chosen service. Direct in-app AI extraction and cloud synchronization are not implemented.

## Storage and limits

Keep the same browser profile and application origin to access stored records. Clearing site data, changing origin, or private browsing can remove or hide them. Browser storage is not a backup; export JSON regularly and test restoration. CSV is a viewing format, not a restore format. The application does not encrypt stored records or exports.

The application's tests exercise data validation, review, persistence, conflicting changes, and restoration with an emulated browser environment. They do not certify every browser or device. Optional WebMCP actions use the same read/import-review boundary; a working live browser registration is not assumed.

For conditional calculations and a different intake contract, see [Longevity](../skills/longevity-intake.md). For the broader design and current delivery boundary, see the [portability plan](portable-apps.md#soov).

[Catalog](../catalog.md) · [Skills for Selfdev](../../README.md)
