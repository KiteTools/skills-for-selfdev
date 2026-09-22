---
name: reconstruct-svg
description: Rebuild a diagram from a supplied image or PDF page as editable SVG, preserving labels, relationships, direction, and meaning. Use for faithful vector reconstruction rather than a redesign or image generation.
---

# Reconstruct SVG

Make a source figure editable and legible at any scale. The visible source is authoritative. This skill does not provide PDF authoring, a scientific model, or an external document workspace.

## Inspect first

Open the actual image or render the requested PDF page with an available PDF renderer. Record both physical PDF page index and printed page number when they differ. Crop for inspection without overwriting the original. If the image cannot be inspected, do not claim a faithful reconstruction.

Inventory axes, labels, arrows and their directions, relative positions, curve shapes, boundaries, intersections, line styles, and meaningful color. Distinguish a qualitative sketch from measured data: do not infer numeric coordinates, a fitted function, or physical equations from a schematic. Mark an illegible label as unresolved rather than guessing.

## Build

Create standalone SVG with a `viewBox`, editable vector shapes and text, a descriptive `title` and `desc`, readable labels, and explicit arrow markers. Preserve the source's notation and caption. Reconstruct curves with paths; do not embed the original raster, a base64 bitmap, scripts, remote images, or external fonts. Avoid `foreignObject` for portable rendering.

Use paths or text rather than relying on a browser LaTeX runtime. If converting mathematical labels to outlined paths, explain that those labels are visually preserved but no longer editable as text. Small spacing adjustments are allowed for clarity; do not change topology, direction, or the conceptual relationships.

## Compare and verify

Render the SVG with an available browser or vector renderer. Compare source and output side by side, optionally with an overlay. Inspect curve geometry, arrow direction, endpoints and intersections, labels, relative positioning, clipping, contrast, and small-screen legibility. Pixel difference is not a primary fidelity measure for a scanned source reconstructed as vectors.

Run the bundled structural checker:

```sh
python3 SKILL_DIR/scripts/check_svg.py OUTPUT.svg
```

Replace `SKILL_DIR` with this skill's directory. The checker validates portable XML/vector structure, not semantic fidelity. Report structural and visual verification separately. If no renderer is available, deliver a draft with visual review pending.

## Deliverable

Save `figure.svg` and `figure-review.md` beside the requested output, preserving the source. The review records the source/page, reconstruction decisions, unresolved labels, visual review performed, and status: `faithful`, `acceptable with listed differences`, or `needs correction`. If the user asks for a document, use relative image links and confirm they resolve.
