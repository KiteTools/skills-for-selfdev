#!/usr/bin/env python3
"""Build an allowlisted skill archive; never include private inputs or Git history."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = Path('skills/cross-device-day-review')
MANIFEST = Path('releases/cross-device-day-review-files.json')
PATTERNS = [r'/(?:Users|home)/[A-Za-z0-9_.-]+/', r'gh[pousr]_[A-Za-z0-9]{30,}',
            r'sk-(?:proj-)?[A-Za-z0-9_-]{32,}', r'\b\d{8,12}:[A-Za-z0-9_-]{30,}\b',
            r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']


def build(root, output):
    root, output = Path(root), Path(output)
    manifest = json.loads((root/MANIFEST).read_text())
    allowed = manifest['files']
    if len(set(allowed)) != len(allowed) or 'LICENSE' not in allowed:
        raise ValueError('Invalid release allowlist')
    actual = {'LICENSE'}
    for p in (root/SKILL).rglob('*'):
        if '__pycache__' in p.parts:
            continue
        if p.is_symlink():
            raise ValueError('Release source contains a symlink')
        if p.is_file():
            actual.add(p.relative_to(root).as_posix())
    if actual != set(allowed):
        raise ValueError('Skill files differ from reviewed allowlist')
    payload = {}
    for name in allowed:
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts or (name != 'LICENSE' and SKILL not in rel.parents):
            raise ValueError('Release path outside skill')
        p = root/rel
        if p.is_symlink() or any(parent.is_symlink() for parent in p.parents if parent != root and root in parent.parents):
            raise ValueError('Symlink release source')
        raw = p.read_bytes()
        if len(raw) > 2*1024*1024 or (name != 'LICENSE' and p.suffix not in {'.md','.json','.py'}):
            raise ValueError('Unexpected release file type or size')
        text = raw.decode('utf-8')
        if any(re.search(pattern, text) for pattern in PATTERNS):
            raise ValueError('Release content needs privacy review')
        dest = 'cross-device-day-review/' + ('LICENSE' if name == 'LICENSE' else rel.relative_to(SKILL).as_posix())
        payload[dest] = raw
    checksums = {k:hashlib.sha256(v).hexdigest() for k,v in sorted(payload.items())}
    payload['cross-device-day-review/SHA256SUMS.json'] = (json.dumps(checksums,indent=2)+'\n').encode()
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(payload.items()):
            info=zipfile.ZipInfo(name, date_time=(2026,10,2,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            archive.writestr(info,raw)
    # Read back the exact archive instead of trusting successful file creation.
    with zipfile.ZipFile(output) as archive:
        if set(archive.namelist()) != set(payload) or any(archive.read(k)!=v for k,v in payload.items()):
            raise ValueError('Archive verification failed')
    return {'files':len(payload),'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        print(json.dumps(build(ROOT,args.output)))
    except (ValueError,OSError,KeyError,UnicodeError,zipfile.BadZipFile):
        print('Package build refused: check allowlist, source privacy and a new output path.',file=sys.stderr)
        return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
