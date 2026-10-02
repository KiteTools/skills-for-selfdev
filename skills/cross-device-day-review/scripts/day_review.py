#!/usr/bin/env python3
"""Offline review of explicitly normalized day records; Python 3.10+, stdlib only."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
import math
import os
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

MAX_BYTES = 20 * 1024 * 1024
KINDS = {'device', 'self_report', 'machine'}


class InputError(ValueError):
    """Only fixed error codes are printed; input text and secrets are not echoed."""


def need(condition, code):
    if not condition:
        raise InputError(code)


def obj(value, required, optional=()):
    need(isinstance(value, dict), 'object_required')
    need(set(required) <= set(value) <= set(required) | set(optional), 'unexpected_or_missing_fields')
    return value


def items(value, maximum=100000):
    need(isinstance(value, list) and len(value) <= maximum, 'invalid_list')
    return value


def ident(value):
    need(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', value), 'invalid_id')
    return value


def label(value):
    need(isinstance(value, str) and 0 < len(value.strip()) <= 300 and
         not any(ord(c) < 32 for c in value), 'invalid_label')
    return value.strip()


def timestamp(value):
    need(isinstance(value, str), 'timestamp_required')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        need(result.tzinfo is not None and result.utcoffset() is not None, 'timestamp_offset_required')
        seconds = result.timestamp()
        need(math.isfinite(seconds), 'invalid_timestamp')
        return seconds
    except (ValueError, OverflowError, OSError):
        raise InputError('invalid_timestamp_or_missing_offset') from None


def day_window(day, zone):
    try:
        d = date.fromisoformat(day)
        need(d.isoformat() == day, 'iso_date_required')
        z = ZoneInfo(zone)
        return (datetime.combine(d, datetime.min.time(), z).timestamp(),
                datetime.combine(d + timedelta(days=1), datetime.min.time(), z).timestamp())
    except (ValueError, KeyError, TypeError, OverflowError):
        raise InputError('invalid_date_or_timezone') from None


def merged(intervals):
    out = []
    for start, end in sorted(intervals):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(end, out[-1][1]))
        else:
            out.append((start, end))
    return out


def minutes(intervals):
    return round(sum(end-start for start, end in merged(intervals))/60, 3)


def clip(start, end, window):
    start, end = max(start, window[0]), min(end, window[1])
    return [(start, end)] if end > start else []


def read_json(path):
    path = Path(path)
    need(not path.is_symlink(), 'symlink_input_refused')
    def pairs(values):
        out = {}
        for key, value in values:
            need(key not in out, 'duplicate_json_key')
            out[key] = value
        return out
    try:
        with path.open('rb') as handle:
            raw = handle.read(MAX_BYTES+1)
        need(len(raw) <= MAX_BYTES, 'input_too_large')
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(InputError('nonfinite_json')))
    except (UnicodeError, json.JSONDecodeError):
        raise InputError('invalid_json') from None


def analyze(config, data):
    obj(config, ['schema_version', 'timezone', 'sources'])
    obj(data, ['schema_version', 'date', 'sources'], ['unknown_activities', 'intentions'])
    need(type(config['schema_version']) is int and config['schema_version'] == 1 and
         type(data['schema_version']) is int and data['schema_version'] == 1, 'unsupported_schema')
    window = day_window(data['date'], config['timezone'])
    definitions = {}
    for source in items(config['sources'], 64):
        obj(source, ['id', 'label', 'kind'])
        sid = ident(source['id']); label(source['label'])
        need(source['kind'] in KINDS, 'invalid_source_kind')
        need(sid not in definitions, 'duplicate_source_id')
        definitions[sid] = source
    need(bool(definitions), 'sources_required')
    selected = {}
    for source in items(data['sources'], 64):
        obj(source, ['id', 'status', 'records'])
        sid = ident(source['id'])
        need(sid in definitions and sid not in selected, 'unknown_or_duplicate_source')
        need(source['status'] in {'ready', 'partial', 'missing'}, 'invalid_source_status')
        items(source['records'])
        need(source['status'] != 'missing' or not source['records'], 'missing_source_has_records')
        selected[sid] = source

    spans = {'device': [], 'self_report': [], 'machine': []}
    known = {k: False for k in KINDS}
    episodes, jobs, report_sources, gaps = {}, {}, [], []

    def episode(eid, title, category):
        eid, title, category = ident(eid), label(title), ident(category)
        if eid in episodes:
            need((episodes[eid]['label'], episodes[eid]['category']) == (title, category), 'conflicting_episode_labels')
        else:
            episodes[eid] = dict(id=eid, label=title, category=category,
                                 intervals=[], source_ids=set(), evidence_ids=set(), duration_incomplete=False)
        return episodes[eid]

    for sid, definition in definitions.items():
        source = selected.get(sid, dict(id=sid, status='missing', records=[]))
        kind, status = definition['kind'], source['status']
        local, seen = [], {}
        for record in source['records']:
            required = ['id', 'label', 'start', 'end'] + ([] if kind == 'machine' else ['episode', 'category'])
            obj(record, required)
            rid = ident(record['id']); label(record['label'])
            start, end = timestamp(record['start']), timestamp(record['end'])
            need(end > start, 'positive_interval_required')
            if rid in seen:
                need(seen[rid] == record, 'conflicting_record_id')
                continue
            seen[rid] = record
            if kind == 'machine':
                # A job ID is global across exported machine sources.
                signature = (start, end, record['label'])
                need(rid not in jobs or jobs[rid]['signature'] == signature, 'conflicting_job_id')
                jobs[rid] = dict(signature=signature, intervals=clip(start, end, window))
            else:
                ident(record['episode']); ident(record['category'])
            interval = clip(start, end, window)
            if not interval:
                continue
            local += interval
            if kind != 'machine':
                item = episode(record['episode'], record['label'], record['category'])
                item['intervals'] += interval
                item['source_ids'].add(sid); item['evidence_ids'].add(sid+':'+rid)
        # An explicit ready empty export is observed zero in that selected export,
        # never proof of a whole empty day. Empty partial/missing remains unknown.
        source_known = status == 'ready' or bool(local)
        known[kind] |= source_known
        spans[kind] += local
        report_sources.append(dict(id=sid, label=definition['label'], kind=kind, status=status,
                                   minutes=minutes(local) if source_known else None))
        if status != 'ready':
            gaps.append(dict(source_id=sid, reason='source_'+status))

    for entry in items(data.get('unknown_activities', [])):
        obj(entry, ['id', 'label', 'category', 'source_id'])
        sid = ident(entry['source_id'])
        need(sid in selected and definitions[sid]['kind'] != 'machine' and
             selected[sid]['status'] != 'missing', 'unknown_activity_source_unavailable')
        item = episode(entry['id'], entry['label'], entry['category'])
        item['duration_incomplete'] = True
        item['source_ids'].add(sid)
        item['evidence_ids'].add(sid+':unknown:'+entry['id'])
        gaps.append(dict(episode_id=entry['id'], reason='unknown_duration'))

    activities = []
    for item in episodes.values():
        activities.append({k: v for k, v in item.items() if k not in {'intervals', 'source_ids', 'evidence_ids'}} |
                          dict(minutes=minutes(item['intervals']) if item['intervals'] else None,
                               source_ids=sorted(item['source_ids']), evidence_ids=sorted(item['evidence_ids'])))
    activities.sort(key=lambda a: (a['minutes'] is None, -(a['minutes'] or 0), a['id']))
    intentions = []
    for entry in items(data.get('intentions', []), 100):
        obj(entry, ['label', 'category'])
        title, category = label(entry['label']), ident(entry['category'])
        intentions.append(dict(label=title, category=category,
                               episode_ids=[a['id'] for a in activities if a['category'] == category]))
    runtime = sum(sum(b-a for a, b in job['intervals']) for job in jobs.values())/60
    return dict(schema_version=1, date=data['date'], timezone=config['timezone'],
                day_minutes=round((window[1]-window[0])/60, 3),
                status='partial' if gaps else 'selected_records_processed', complete_day_claim=False,
                human=dict(union_minutes=minutes(spans['device']+spans['self_report']) if known['device'] or known['self_report'] else None,
                           device_minutes=minutes(spans['device']) if known['device'] else None,
                           self_report_minutes=minutes(spans['self_report']) if known['self_report'] else None,
                           basis='union_of_observed_device_and_explicit_self_report_intervals'),
                machine=dict(runtime_minutes=round(runtime, 3) if known['machine'] else None,
                             wall_minutes=minutes(spans['machine']) if known['machine'] else None,
                             add_to_human_time=False),
                activities=activities, sources=report_sources, intentions=intentions, gaps=gaps,
                follow_up='Что из значимых занятий дня не попало в эти записи?',
                limits=['Only explicitly supplied records; no automatic collection or complete-day claim.',
                        'Device activity is not proof of attention, understanding or task completion.',
                        'Activities and source subtotals may overlap; do not add them to the union.',
                        'Minutes for an incomplete episode are a known lower bound.',
                        'No prediction of motives, state or vitality; personal labels remain private.'])


def md(value):
    return re.sub(r'([\\`*_{}\[\]()<>#!|])', r'\\\1', str(value))


def fmt(value):
    return 'неизвестно' if value is None else f'{value:g} мин'


def markdown(report):
    lines = [f"# Разбор дня · {report['date']}", '', f"Часовой пояс: {md(report['timezone'])}.", '',
             f"По доступным интервалам человека и устройств: **{fmt(report['human']['union_minutes'])}**.",
             'Пересечения учтены один раз. Это объём доступных записей, а не полная длительность дня.', '',
             '## Занятия', '']
    for activity in report['activities']:
        bound = ' (известная часть; общая длительность не определена)' if activity['duration_incomplete'] and activity['minutes'] is not None else ''
        lines.append(f"- **{md(activity['label'])}** — {fmt(activity['minutes'])}{bound}. Источники: {', '.join(md(x) for x in activity['evidence_ids'])}.")
    if not report['activities']:
        lines.append('Нет занятий с доступными записями.')
    lines += ['', 'Занятия могут пересекаться: их длительности нельзя складывать в итог дня.', '',
              '## Машинная работа', '',
              f"Суммарная работа завершённых заданий: {fmt(report['machine']['runtime_minutes'])}.",
              f"Объединённый интервал их работы: {fmt(report['machine']['wall_minutes'])}.",
              'Параллельные задания могут дать большую сумму. Это время не прибавляется к времени человека.', '',
              '## Источники и пробелы', '', '| Источник | Тип | Статус | Наблюдаемое время |', '| --- | --- | --- | --- |']
    for source in report['sources']:
        lines.append(f"| {md(source['label'])} | {source['kind']} | {source['status']} | {fmt(source['minutes'])} |")
    lines += ['', 'Пропущенный источник и неизвестная длительность не равны нулю. `ready` означает обработанный выбранный экспорт, а не непрерывный охват суток.']
    if report['intentions']:
        lines += ['', '## Выбранные направления', '']
        for intent in report['intentions']:
            links=', '.join(md(x) for x in intent['episode_ids']) or 'в доступных записях не найдено; это не доказывает отсутствия работы'
            lines.append(f"- {md(intent['label'])}: {links}.")
    lines += ['', report['follow_up'], '',
              'Активное приложение не доказывает внимание, понимание или завершение задачи. Отчёт содержит твои подписи: проверь его перед передачей другому человеку или модели.', '']
    return '\n'.join(lines)


def write_report(report, output):
    output = Path(output)
    need(not output.exists() and not output.is_symlink(), 'output_directory_must_be_new')
    need(output.parent.is_dir(), 'output_parent_must_exist')
    output.mkdir(mode=0o700)
    compact = {k: report[k] for k in ['schema_version', 'date', 'timezone', 'status', 'complete_day_claim', 'human', 'machine', 'activities', 'intentions', 'gaps']}
    contents = {'report.md': markdown(report), 'report.json': json.dumps(report, ensure_ascii=False, indent=2)+'\n',
                'compact.json': json.dumps(compact, ensure_ascii=False, separators=(',', ':'))+'\n'}
    for name, content in contents.items():
        fd = os.open(output/name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(content)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = analyze(read_json(args.config), read_json(args.input))
        write_report(report, args.output_dir)
    except (InputError, OSError, TypeError, ValueError, RecursionError):
        print('Review stopped: invalid input or unavailable/new output directory. Check the schema and private paths.', file=sys.stderr)
        return 2
    print(json.dumps({'status': report['status'], 'files': ['report.md', 'report.json', 'compact.json']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
