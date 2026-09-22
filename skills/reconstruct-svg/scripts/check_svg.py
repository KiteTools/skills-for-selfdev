#!/usr/bin/env python3
"""Check a deliberately small, portable SVG profile; not a fidelity assessment."""
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ALLOWED = {
    'svg', 'g', 'defs', 'title', 'desc', 'path', 'rect', 'circle', 'ellipse',
    'line', 'polyline', 'polygon', 'text', 'tspan', 'textPath', 'marker',
    'linearGradient', 'radialGradient', 'stop', 'clipPath', 'mask', 'use',
}


def validate_svg(path):
    raw = Path(path).read_text(encoding='utf-8')
    if re.search(r'<!DOCTYPE|<!ENTITY', raw, re.I):
        raise ValueError('DTD and entity declarations are outside this portable profile')
    root = ET.fromstring(raw)
    if root.tag != '{http://www.w3.org/2000/svg}svg':
        raise ValueError('Expected an SVG root in the SVG namespace')
    try:
        box = [float(x) for x in re.split(r'[\s,]+', root.attrib['viewBox'].strip())]
    except (KeyError, ValueError):
        raise ValueError('A numeric viewBox is required') from None
    import math
    if len(box) != 4 or not all(math.isfinite(x) for x in box) or box[2] <= 0 or box[3] <= 0:
        raise ValueError('viewBox must have four finite values and positive dimensions')
    if not any(e.tag == '{http://www.w3.org/2000/svg}title' and (e.text or '').strip() for e in root):
        raise ValueError('A descriptive title is required')
    for node in root.iter():
        name = node.tag.rsplit('}', 1)[-1]
        if not node.tag.startswith('{http://www.w3.org/2000/svg}') or name not in ALLOWED:
            raise ValueError(f'Unsupported element: {name}')
        for key, value in node.attrib.items():
            attr = key.rsplit('}', 1)[-1].lower()
            if attr.startswith('on') or attr == 'style':
                raise ValueError('Event handlers and inline CSS are not supported; use presentation attributes')
            if attr == 'href' and not re.fullmatch(r'#[A-Za-z_][\w.:-]*', value):
                raise ValueError('Only local fragment references are allowed')
            if re.search(r'url\s*\(', value, re.I) and not re.fullmatch(r'url\(#[A-Za-z_][\w.:-]*\)', value):
                raise ValueError('Only local fragment paint/marker references are allowed')
            if re.search(r'https?:|data:|javascript:|@import|\\', value, re.I):
                raise ValueError('External, encoded, or executable attribute values are unsupported')
    return True


def main():
    if len(sys.argv) < 2:
        print('usage: check_svg.py FIGURE.svg [...]', file=sys.stderr)
        return 2
    try:
        for arg in sys.argv[1:]:
            validate_svg(arg)
            print(f'PASS {arg}: portable vector structure; visual fidelity not assessed')
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
