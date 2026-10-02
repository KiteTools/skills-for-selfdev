import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('day_review', ROOT / 'skills/cross-device-day-review/scripts/day_review.py')
day = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(day)


def config():
    return {'schema_version': 1, 'timezone': 'UTC', 'sources': [
        {'id': 'computer', 'label': 'Computer', 'kind': 'device'},
        {'id': 'phone', 'label': 'Phone', 'kind': 'device'},
        {'id': 'notes', 'label': 'Notes', 'kind': 'self_report'},
        {'id': 'agent', 'label': 'Agent', 'kind': 'machine'}]}


def interval(id, start, end, episode='learning'):
    return dict(id=id, episode=episode, label=episode.title(), category='learning',
                start=f'2030-01-15T{start}:00+00:00', end=f'2030-01-15T{end}:00+00:00')


def payload():
    return {'schema_version': 1, 'date': '2030-01-15', 'sources': [
        {'id': 'computer', 'status': 'ready', 'records': [interval('screen', '09:00', '10:00')]},
        {'id': 'phone', 'status': 'ready', 'records': [interval('phone-use', '09:30', '10:30')]},
        {'id': 'notes', 'status': 'partial', 'records': []},
        {'id': 'agent', 'status': 'ready', 'records': [
            {'id': 'job-one', 'label': 'Build', 'start': '2030-01-15T09:00:00Z', 'end': '2030-01-15T10:00:00Z'},
            {'id': 'job-two', 'label': 'Check', 'start': '2030-01-15T09:15:00Z', 'end': '2030-01-15T09:45:00Z'}]}],
        'unknown_activities': [], 'intentions': []}


class DayReviewTests(unittest.TestCase):
    def test_union_across_devices_and_one_episode(self):
        report = day.analyze(config(), payload())
        self.assertEqual(report['human']['union_minutes'], 90)
        self.assertEqual(report['activities'][0]['minutes'], 90)
        self.assertEqual(len(report['activities']), 1)

    def test_machine_parallel_runtime_is_separate(self):
        report = day.analyze(config(), payload())
        self.assertEqual(report['machine']['runtime_minutes'], 90)
        self.assertEqual(report['machine']['wall_minutes'], 60)
        self.assertFalse(report['machine']['add_to_human_time'])

    def test_missing_source_is_null_and_coverage_is_partial(self):
        data = payload(); data['sources'] = []
        report = day.analyze(config(), data)
        self.assertIsNone(report['human']['union_minutes'])
        self.assertIsNone(report['machine']['runtime_minutes'])
        self.assertTrue(all(s['minutes'] is None for s in report['sources']))
        self.assertFalse(report['complete_day_claim'])

    def test_unknown_duration_sorts_last(self):
        data = payload()
        data['unknown_activities'] = [dict(id='walk', label='Walk', category='rest', source_id='notes')]
        report = day.analyze(config(), data)
        self.assertEqual(report['activities'][-1]['id'], 'walk')
        self.assertIsNone(report['activities'][-1]['minutes'])

    def test_duplicates_do_not_add_time(self):
        data = payload()
        data['sources'][0]['records'] *= 2
        data['sources'][3]['records'] *= 2
        report = day.analyze(config(), data)
        self.assertEqual(report['human']['union_minutes'], 90)
        self.assertEqual(report['machine']['runtime_minutes'], 90)

    def test_dst_day_window(self):
        self.assertEqual(day.day_window('2030-03-31', 'Europe/Berlin')[1] - day.day_window('2030-03-31', 'Europe/Berlin')[0], 23*3600)
        self.assertEqual(day.day_window('2030-10-27', 'Europe/Berlin')[1] - day.day_window('2030-10-27', 'Europe/Berlin')[0], 25*3600)

    def test_rejects_naive_time_and_reversed_interval(self):
        for a,b in [('2030-01-15T09:00:00','2030-01-15T10:00:00Z'), ('2030-01-15T11:00:00Z','2030-01-15T10:00:00Z')]:
            data=payload(); data['sources'][0]['records'][0].update(start=a,end=b)
            with self.assertRaises(day.InputError): day.analyze(config(),data)

    def test_explicit_empty_source_vs_unavailable(self):
        data=payload(); data['sources']=[dict(id='computer',status='ready',records=[])]
        report=day.analyze(config(),data)
        self.assertEqual(report['sources'][0]['minutes'],0)
        self.assertIsNone(report['sources'][1]['minutes'])
        self.assertEqual(report['human']['union_minutes'],0)

    def test_clip_to_selected_local_day(self):
        data=payload(); data['sources']=[dict(id='computer',status='ready',records=[interval('midnight','00:00','01:00')])]
        data['sources'][0]['records'][0]['start']='2030-01-14T23:00:00Z'
        self.assertEqual(day.analyze(config(),data)['human']['union_minutes'],60)

    def test_missing_source_cannot_carry_records(self):
        data=payload(); data['sources'][0]['status']='missing'
        with self.assertRaises(day.InputError):day.analyze(config(),data)

    def test_unknown_source_and_conflicting_episode_rejected(self):
        data=payload(); data['sources'][1]['id']='unknown'
        with self.assertRaises(day.InputError):day.analyze(config(),data)
        data=payload();data['sources'][1]['records'][0]['label']='Different interpretation'
        with self.assertRaises(day.InputError):day.analyze(config(),data)

    def test_unknown_part_makes_episode_lower_bound(self):
        data=payload();data['unknown_activities']=[dict(id='learning',label='Learning',category='learning',source_id='notes')]
        item=day.analyze(config(),data)['activities'][0]
        self.assertEqual(item['minutes'],90)
        self.assertTrue(item['duration_incomplete'])

    def test_self_report_overlap_not_added_twice(self):
        data=payload();data['sources'][2]['records']=[interval('notes','09:10','09:50')]
        self.assertEqual(day.analyze(config(),data)['human']['union_minutes'],90)

    def test_same_machine_id_across_sources_deduplicates(self):
        cfg=config();cfg['sources'].append(dict(id='agent-copy',label='Copy',kind='machine'))
        data=payload();data['sources'].append(dict(id='agent-copy',status='ready',records=data['sources'][3]['records']))
        self.assertEqual(day.analyze(cfg,data)['machine']['runtime_minutes'],90)

    def test_empty_partial_is_unknown_not_zero(self):
        data=payload();data['sources']=[dict(id='notes',status='partial',records=[])]
        self.assertIsNone(day.analyze(config(),data)['human']['union_minutes'])

    def test_raw_private_fields_rejected(self):
        data=payload();data['sources'][0]['records'][0]['window_title']='PRIVATE_CANARY'
        with self.assertRaises(day.InputError):day.analyze(config(),data)

    def test_output_refuses_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'report'
            report=day.analyze(config(),payload());day.write_report(report,out)
            before=(out/'report.json').read_bytes()
            with self.assertRaises(day.InputError):day.write_report(report,out)
            self.assertEqual(before,(out/'report.json').read_bytes())
            self.assertTrue((out/'report.md').exists());self.assertTrue((out/'compact.json').exists())

    def test_synthetic_example_runs(self):
        base=ROOT/'skills/cross-device-day-review/examples'
        report=day.analyze(day.read_json(base/'config.json'),day.read_json(base/'day.json'))
        self.assertEqual(report['human']['union_minutes'],140)
        self.assertEqual(report['machine']['runtime_minutes'],90)
        self.assertEqual(report['activities'][-1]['minutes'],None)

if __name__=='__main__':unittest.main()
