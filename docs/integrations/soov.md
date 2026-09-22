# SOOV / СООВ: where life-event capture started

[English](soov.md) · [Русский](soov.ru.md)

SOOV preceded Longevity. Its starting screen supported two ways to collect life events: enter them manually, or extract them from a transcript. That simple entry point remains useful before a deeper reflection or a model-based exploration.

This repository provides [life-events](../skills/life-events.md), a portable text workflow for those two tasks. It keeps sources, approximate times and the person's own assessment attached to each event.

**Status:** companion skill, not the original SOOV app. The original application's exact public source, deployment and authentication requirements have not been established for this release. No SOOV backend, account or import compatibility is implied.

For a maintained public application with a documented intake contract, see [Longevity](../skills/longevity-intake.md). Its conditional calculations and WebMCP interface are separate from a plain event timeline.

## A portable SOOV

The proposed first release is a small browser app: add an event manually, import a reviewed draft extracted from a transcript, edit the timeline, and export a backup. Store data on the device and make cloud accounts optional. Local browser storage needs explicit export and restore; clearing it must not be mistaken for a backup strategy.

Transcript extraction can initially use the existing life-events skill in the person's chosen AI assistant. A direct AI API connector and sync can follow as separate, explicit options. “Local event storage” does not mean a cloud assistant processes the transcript locally.

**This is a proposal, not a released app.** The [portability plan](portable-apps.md#soov) defines the data contract, authentication boundary and acceptance checks. It also explains why the first step is locating and reviewing the original SOOV source before choosing extraction or a small rebuild.

[Catalog](../catalog.md) · [Skills for Selfdev](../../README.md)
