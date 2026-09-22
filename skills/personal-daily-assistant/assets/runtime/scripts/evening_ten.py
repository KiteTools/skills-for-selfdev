#!/usr/bin/env python3
"""Import reviewed Evening Ten records; keep delivery and explicit feedback separate.

No activity collection, model calls, task creation, or access to the daily journal.
Requires POSIX file locks (macOS/Linux/WSL), not native Windows.
"""
from __future__ import annotations
import argparse
import base64
from contextlib import contextmanager
from datetime import date, datetime, timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from zoneinfo import ZoneInfo

ACTIONS = {'интерес': 'interested', 'выбран': 'chosen', 'попробовал': 'attempted', 'результат': 'reported_outcome', 'выполнено': 'completed', 'неподходит': 'did_not_fit'}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def text(value, label, limit=240):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit, f'{label}: nonempty text <= {limit} required')
    return value

def ids(values, label):
    require(isinstance(values, list) and all(isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,80}', v) for v in values), f'{label}: stable IDs required')
    require(len(set(values)) == len(values), f'{label}: duplicate IDs')
    return set(values)

def validate_prepared(value):
    fields = {'schema_version', 'date', 'timezone', 'source_manifest', 'day_threads', 'day_summary', 'alignment', 'candidates', 'selected', 'checks'}
    require(isinstance(value, dict) and set(value) == fields, 'Prepared Ten fields must match the portable contract; no raw sources')
    require(value['schema_version'] == 1, 'Unsupported schema')
    require(date.fromisoformat(value['date']).isoformat() == value['date'], 'Invalid date')
    ZoneInfo(value['timezone'])
    manifest = value['source_manifest']
    require(isinstance(manifest, dict) and set(manifest) == {'evidence_ids', 'goal_ids'}, 'Only evidence and goal IDs belong in source_manifest')
    evidence = ids(manifest['evidence_ids'], 'evidence_ids')
    goals = ids(manifest['goal_ids'], 'goal_ids')
    require(evidence or goals, 'No evidence or stated goals')
    text(value['day_summary'], 'day_summary', 650)
    if value['alignment'] is not None: text(value['alignment'], 'alignment', 450)
    threads = value['day_threads']
    require(isinstance(threads, list), 'day_threads required')
    thread_map, covered = {}, set()
    for thread in threads:
        require(isinstance(thread, dict) and set(thread) == {'id', 'title', 'substantive', 'evidence_ids'}, 'Invalid day thread')
        ids([thread['id']], 'thread id'); text(thread['title'], 'thread title', 120)
        require(type(thread['substantive']) is bool and thread['id'] not in thread_map, 'Invalid or duplicate thread')
        refs = ids(thread['evidence_ids'], 'thread evidence')
        require(refs and refs <= evidence, 'Thread references unknown evidence')
        covered |= refs; thread_map[thread['id']] = thread
    require(covered == evidence, 'Day map must cover all supplied evidence')
    candidates = value['candidates']
    require(isinstance(candidates, list) and len(candidates) == 20, 'Full Ten requires 20 candidates')
    by_id, normalized = {}, set()
    for candidate in candidates:
        required = {'id', 'text', 'goal_id', 'evidence_ids', 'thread_id', 'move_type', 'mechanism', 'exploratory'}
        require(isinstance(candidate, dict) and required <= set(candidate) <= required | {'repeat_of', 'changed_basis_ids'}, 'Invalid candidate fields')
        ids([candidate['id']], 'candidate id'); text(candidate['text'], 'candidate text', 220)
        require(candidate['id'] not in by_id, 'Duplicate candidate ID')
        key = ' '.join(candidate['text'].casefold().split())
        require(key not in normalized, 'Duplicate candidate text'); normalized.add(key)
        text(candidate['move_type'], 'move_type', 80); text(candidate['mechanism'], 'mechanism')
        require(type(candidate['exploratory']) is bool, 'exploratory must be boolean')
        require(candidate['goal_id'] is None or candidate['goal_id'] in goals, 'Unknown goal')
        refs = ids(candidate['evidence_ids'], 'candidate evidence')
        require(refs and refs <= evidence | {f'goal:{g}' for g in goals}, 'Unknown evidence reference')
        thread_id = candidate['thread_id']
        if refs & evidence:
            require(thread_id in thread_map and bool(refs & set(thread_map[thread_id]['evidence_ids'])), 'Candidate must cite its actual day thread')
        else:
            require(thread_id is None, 'Goal-only opportunity cannot invent a day thread')
        if 'repeat_of' in candidate:
            text(candidate['repeat_of'], 'repeat_of', 100)
            changed = ids(candidate.get('changed_basis_ids'), 'changed_basis_ids')
            require(changed and changed <= evidence and changed <= refs, 'Returning idea needs cited current evidence')
        by_id[candidate['id']] = candidate
    selected = ids(value['selected'], 'selected')
    require(len(selected) == 10 and selected <= by_id.keys(), 'Select exactly ten distinct candidate IDs')
    chosen = [by_id[i] for i in value['selected']]
    require(len({c['move_type'] for c in chosen}) >= 4, 'Need four move types')
    require(sum(c['exploratory'] for c in chosen) >= 3, 'Need three exploratory moves')
    substantive = {t['id'] for t in threads if t['substantive']}
    require(len({c['thread_id'] for c in chosen} & substantive) >= min(3, len(substantive)), 'Selected ideas do not cover day threads')
    checks = value['checks']
    require(isinstance(checks, dict) and set(checks) == {'history_available', 'coverage_complete_for_supplied_input', 'preparation_reviewed'}, 'Explicit review checks required')
    require(type(checks['history_available']) is bool and checks['coverage_complete_for_supplied_input'] is True and checks['preparation_reviewed'] is True, 'Incomplete or unreviewed preparation')
    return value

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

class TenStore:
    def __init__(self, data_dir, timezone='UTC'):
        self.root = Path(data_dir).expanduser().resolve() / 'evening-ten'
        self.timezone = ZoneInfo(timezone)

    @contextmanager
    def locked(self):
        require(not self.root.is_symlink(), 'Ten directory cannot be a symlink')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        path = self.root / '.lock'
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(fd, 'a') as handle:
            os.fchmod(handle.fileno(), 0o600)
            fcntl.flock(handle, fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(handle, fcntl.LOCK_UN)

    def path(self, day):
        require(date.fromisoformat(day).isoformat() == day, 'Invalid date')
        return self.root / f'{day}.json'

    def read(self, day):
        path = self.path(day)
        require(not path.is_symlink(), 'Ten record cannot be a symlink')
        return json.loads(path.read_text()) if path.exists() else None

    def write(self, day, value):
        path = self.path(day)
        require(not path.is_symlink(), 'Ten record cannot be a symlink')
        fd, tmp = tempfile.mkstemp(prefix='.ten-', dir=self.root)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(canonical(value) + '\n'); handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)

    def ingest(self, prepared):
        validate_prepared(prepared)
        require(prepared['timezone'] == str(self.timezone), 'Prepared timezone differs from configured timezone')
        with self.locked():
            old = self.read(prepared['date'])
            if old:
                require(old['prepared'] == prepared, 'Saved Ten is immutable; numbering cannot be replaced')
                return {'status': 'already_saved', 'date': prepared['date']}
            # Catch exact repeats; semantic novelty still requires a preparation review.
            day = date.fromisoformat(prepared['date'])
            prior = {}
            for offset in range(1, 15):
                previous = self.read((day - timedelta(days=offset)).isoformat())
                if previous:
                    p = previous['prepared']; chosen = set(p['selected'])
                    for c in p['candidates']:
                        if c['id'] in chosen: prior[f"{p['date']}:{c['id']}"] = c
            if prior: require(prepared['checks']['history_available'], 'Stored history exists; review it before import')
            for c in prepared['candidates']:
                if c['id'] not in prepared['selected']: continue
                duplicates = [key for key, old in prior.items() if ' '.join(c['text'].casefold().split()) == ' '.join(old['text'].casefold().split())]
                if 'repeat_of' in c: require(c['repeat_of'] in prior, 'repeat_of must resolve to stored recent history')
                if duplicates: require(c.get('repeat_of') in duplicates and c.get('changed_basis_ids'), 'Exact repeat needs a previous ID and changed basis')
            self.write(prepared['date'], {'prepared': prepared, 'delivery': {'status': 'prepared'}, 'feedback': []})
        return {'status': 'saved', 'date': prepared['date']}

    def render(self, prepared):
        by_id = {c['id']: c for c in prepared['candidates']}
        lines = ['Вечерний взгляд — ' + prepared['date'], '', prepared['day_summary']]
        if prepared['alignment']: lines += ['', prepared['alignment']]
        lines += ['', *[f'{n}. {by_id[cid]["text"]}' for n, cid in enumerate(prepared['selected'], 1)]]
        if not prepared['checks']['history_available']: lines += ['', 'История прошлых предложений недоступна; проверка повторов ограничена.']
        lines += ['', 'Отклик необязателен. /ход 2,4 — сохранить интерес, без задачи и обязательств.']
        return '\n'.join(lines)

    def dispatch(self, now, *, send, dry_run=False):
        require(now.tzinfo is not None, 'Timezone-aware timestamp required')
        day = now.astimezone(self.timezone).date().isoformat()
        if not self.root.exists(): return {'status': 'no_data'}
        with self.locked():
            record = self.read(day)
            if not record: return {'status': 'no_data'}
            message = self.render(record['prepared'])
            if dry_run: return {'status': 'preview', 'text': message}
            status = record['delivery']['status']
            if status == 'delivered': return {'status': 'already_delivered'}
            if status != 'prepared': return {'status': 'delivery_uncertain', 'text': 'Проверьте доставку вручную; автоматического повтора нет.'}
            record['delivery'] = {'status': 'sending', 'attempted_at': now.isoformat()}
            self.write(day, record)
            try:
                result = send(message)
                require(isinstance(result, dict) and isinstance(result.get('message_id'), (str, int)) and str(result['message_id']).strip(), 'Missing transport message ID')
            except Exception:
                record['delivery']['status'] = 'uncertain'; self.write(day, record)
                return {'status': 'delivery_uncertain', 'text': 'Доставка не подтверждена; проверьте чат перед дальнейшими действиями.'}
            record['delivery'] = {'status': 'delivered', 'delivered_at': now.isoformat(), 'message_id': str(result['message_id'])}
            self.write(day, record)
            return {'status': 'delivered', 'message_id': str(result['message_id'])}

    def feedback_events(self):
        if not self.root.exists(): return []
        return [event for path in sorted(self.root.glob('????-??-??.json')) for event in self.read(path.stem)['feedback']]

    def feedback(self, command, *, message_id, now):
        text(message_id, 'message_id', 160)
        require(now.tzinfo is not None, 'Timezone-aware timestamp required')
        implicit = re.fullmatch(r'/ход\s+([\d,\s]+)', command.strip(), re.I)
        explicit = re.fullmatch(r'/десятка\s+(\d{4}-\d{2}-\d{2})\s+(интерес|выбран|попробовал|результат|выполнено|неподходит)\s+([\d,\s]+)(?::\s*(.+))?', command.strip(), re.I | re.S)
        require(implicit or explicit, 'Use /ход 2,4 or /десятка YYYY-MM-DD интерес 2')
        day = now.astimezone(self.timezone).date().isoformat() if implicit else explicit[1]
        action = 'interested' if implicit else ACTIONS[explicit[2].lower()]
        numbers = [int(n) for n in re.findall(r'\d+', implicit[1] if implicit else explicit[3])]
        require(numbers and len(set(numbers)) == len(numbers) and all(1 <= n <= 10 for n in numbers), 'Choose distinct numbers 1–10')
        note = '' if implicit else (explicit[4] or '').strip()
        if action in {'attempted', 'reported_outcome', 'completed'}: text(note, 'Describe the action or result; a number alone is not completion', 2000)
        require(len(note) <= 2000, 'Feedback too long')
        with self.locked():
            for old in self.feedback_events():
                if old['message_id'] == message_id:
                    require(old['command'] == command, 'Same message ID has different feedback')
                    return old['response']
            record = self.read(day)
            require(record and record['delivery']['status'] == 'delivered', 'No confirmed delivered Ten for this date')
            if implicit:
                age = (now - datetime.fromisoformat(record['delivery']['delivered_at'])).total_seconds()
                require(0 <= age <= 7200, 'Implicit interest requires today’s delivered Ten within two hours; use the explicit dated command')
            label = {'interested': 'Интерес сохранён; это не задача.', 'chosen': 'Выбор сохранён; действие ещё не подтверждено.', 'attempted': 'Попытка сохранена по твоему сообщению.', 'reported_outcome': 'Твой рассказ о результате сохранён.', 'completed': 'Выполнение отмечено по твоему сообщению, без независимой проверки и записи успеха.', 'did_not_fit': 'Сохранено: не подошло.'}[action]
            response = {'status': 'recorded', 'action': action, 'numbers': numbers, 'text': label}
            record['feedback'].append({'message_id': message_id, 'command': command, 'occurred_at': now.isoformat(), 'action': action, 'numbers': numbers, 'candidate_ids': [record['prepared']['selected'][n-1] for n in numbers], 'note': note, 'evidence_kind': 'explicit_self_report', 'response': response})
            self.write(day, record)
            return response

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=os.environ.get('PDS_DATA_DIR'))
    parser.add_argument('--timezone', default=os.environ.get('PDS_TIMEZONE', 'UTC'))
    sub = parser.add_subparsers(dest='command', required=True)
    ingest = sub.add_parser('ingest'); ingest.add_argument('--prepared', type=Path, required=True)
    dispatch = sub.add_parser('dispatch'); dispatch.add_argument('--target', default=os.environ.get('PDS_TELEGRAM_TARGET')); dispatch.add_argument('--dry-run', action='store_true')
    feedback = sub.add_parser('feedback'); feedback.add_argument('--text-base64', required=True); feedback.add_argument('--message-id', required=True)
    args = parser.parse_args(argv)
    try:
        require(args.data_dir is not None and args.data_dir.is_absolute(), 'Explicit absolute PDS_DATA_DIR or --data-dir required')
        store = TenStore(args.data_dir, args.timezone)
        now = datetime.now(ZoneInfo(args.timezone))
        if args.command == 'ingest':
            require(args.prepared.is_absolute() and args.prepared.is_file() and args.prepared.stat().st_size <= 100000, 'Prepared file must be an absolute path, <=100KB')
            result = store.ingest(json.loads(args.prepared.read_text(encoding='utf-8')))
        elif args.command == 'feedback':
            result = store.feedback(base64.b64decode(args.text_base64, validate=True).decode('utf-8'), message_id=args.message_id, now=now)
        else:
            require(os.environ.get('PDS_EVENING_TEN_ENABLED') == '1', 'Evening Ten delivery is disabled')
            require(args.target and args.target.isdigit(), 'Numeric Telegram owner target required')
            from personal_daily_system import send_openclaw_response
            def send(message):
                result = send_openclaw_response({'text': message}, target=args.target)
                transport = result.get('transport')
                # Supported OpenClaw JSON envelopes; unknown output is inconclusive.
                for candidate in (transport, transport.get('payload') if isinstance(transport, dict) else None, transport.get('result') if isinstance(transport, dict) else None):
                    if isinstance(candidate, dict):
                        mid = candidate.get('messageId') or candidate.get('message_id')
                        if mid: return {'message_id': mid}
                return {}
            result = store.dispatch(now, send=send, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False)); return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'invalid', 'text': str(error)}, ensure_ascii=False)); return 1

if __name__ == '__main__': raise SystemExit(main())
