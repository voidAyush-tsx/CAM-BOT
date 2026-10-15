"""Arithmetic and evidence-integrity fixtures; these never count as observed trials."""
import copy
import csv
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('analysis', BASE / 'scripts/analyze_trials.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
EXPECTED = json.loads((BASE / 'tests/fixtures/expected.json').read_text())


def fixture(directory, specifications=None):
    """Construct schema-shaped records with predetermined, independently tabulated times."""
    specs = EXPECTED['trials'] if specifications is None else specifications
    rows, all_events = [], []
    for item in specs:
        events = []
        epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
        wall = lambda sec: (epoch + timedelta(seconds=sec)).isoformat()
        identity = {'git_commit': 'a'*40, 'parameter_hash_sha256': 'b'*64, 'parameter_config': 'fixture.json'}

        def emit(at, action, result, state='TRIAL', details=None):
            events.append({'schema_version': '2.0', 'experiment_id': 'synthetic-fixture', 'trial_id': item['id'],
                           'sequence': 0, 'timestamp_utc': wall(at), 'monotonic_elapsed_s': at,
                           'state': state, 'target': None, 'reachability': None, 'decision': None,
                           'action': action, 'result': result, 'details': details or {}})

        emit(0, 'START', 'INCOMPLETE_PENDING', details=identity)
        emit(0.01, 'CONTEXT', 'RECORDED', details={'visual_time_scale': 1.0, 'enable_coordination': True,
                                                 'fault_injection_step': '', 'ros_time_ns': 1})
        names = [('HOME', ['HOME_START']), ('PICK_RAW', ['S1_APPROACH', 'S1_GRASP']),
                 ('STAGE', ['S2_STAGE']), ('LOAD_MACHINE', ['S3_LOAD', 'S3_RELEASE']),
                 ('MACHINE_DWELL', ['MACHINE_DWELL']), ('UNLOAD_MACHINE', ['S3_REGRASP', 'S4_UNLOAD']),
                 ('PLACE_FINISHED', ['S5_PLACE', 'S5_RELEASE']), ('HOME', ['HOME_END'])]
        at = 0.1
        for state, steps in names:
            emit(at, 'FSM', 'ENTERED', state)
            at += 0.01
            for step in steps:
                if step == 'S1_APPROACH':
                    at = 2.0
                emit(at, step, 'STEP_STARTED', state)
                at += 0.01
                if not item['success'] and step == 'S3_LOAD':
                    emit(8.0, 'ADAPTER_RESULT', 'FAILED', state,
                         {'step': step, 'ros_time_ns': 2, 'cause': 'INJECTED_VISUAL_TEST_FAILURE'})
                    break
                if step == 'HOME_END':
                    at = 2 + item['duration_s'] - 0.01
                emit(at, 'ADAPTER_RESULT', 'COMPLETED', state, {'step': step, 'ros_time_ns': 2, 'cause': None})
                at += 0.01
                emit(at, step, 'STEP_COMPLETED', state)
                at += 0.01
            if not item['success'] and state == 'LOAD_MACHINE':
                break
        for number in range(item['requested']):
            d = {'motion_id': str(number), 'station': 'S1_RAW', 'start_joints_rad': [0]*6,
                 'goal_joints_rad': [1]*6, 'nontrivial': True, 'is_reposition': True,
                 'evidence_kind': 'visual_joint_publication', 'ros_time_ns': 2}
            for index, phase in enumerate(('REQUESTED', 'ACCEPTED',
                                          'COMPLETED' if number < item['completed'] else 'FAILED')):
                emit(2.5 + number*0.1 + index*0.01, 'CARRIER_MOTION', phase, 'PICK_RAW',
                     {**d, 'final_joints_rad': [1]*6 if phase == 'COMPLETED' else [0]*6})
        end = 2 + item['duration_s']
        cause = None if item['success'] else 'INJECTED_VISUAL_TEST_FAILURE'
        final_workpiece = 'FINISHED_AT_S5' if item['success'] else 'HELD_RAW_AT_S2'
        emit(end+0.01 if item['success'] else end, 'FSM', 'SUCCESS' if item['success'] else 'FAILURE',
             'HOME' if item['success'] else 'LOAD_MACHINE', {'cause': cause})
        emit(end+0.02, 'FINALIZE', 'COMPLETE' if item['success'] else 'FAILED',
             details={'success': item['success'], 'failure_reason': cause, 'workpiece_final_state': final_workpiece})
        events.sort(key=lambda e: e['monotonic_elapsed_s'])
        for index, event in enumerate(events):
            event['sequence'] = index
        row = {'schema_version': '2.0', 'experiment_id': 'synthetic-fixture', 'trial_id': item['id'], **identity,
               'start_timestamp_utc': wall(0), 'end_timestamp_utc': wall(end+0.02),
               'time_source': 'monotonic_duration+utc_wall_timestamps', 'cycle_time_s': end+0.02,
               'status': 'COMPLETE' if item['success'] else 'FAILED', 'success': item['success'],
               'failure_state': None if item['success'] else 'LOAD_MACHINE', 'failure_reason': cause,
               'carrier_repositions': 999,  # Deliberately wrong legacy counter; events determine counts.
               'mode': 'visual_simulation', 'workpiece_final_state': final_workpiece,
               'runtime_verified': False, 'end_to_end_verified': False, 'notes': 'SYNTHETIC FIXTURE ONLY'}
        rows.append(row)
        all_events.extend(events)
    path = directory / 'trials.csv'
    analysis.write_csv(path, rows, analysis.SUMMARY_FIELDS)
    path.with_suffix('.events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in all_events))
    return path


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.raw = self.root / 'raw'
        self.raw.mkdir()
        self.path = fixture(self.raw)

    def edit_events(self, mutate):
        path = self.path.with_suffix('.events.jsonl')
        events = [json.loads(line) for line in path.read_text().splitlines()]
        mutate(events)
        path.write_text(''.join(json.dumps(e)+'\n' for e in events))

    def test_independent_mixed_arithmetic_and_motion_totals(self):
        trials, metrics = analysis.analyze(self.path)
        summary = metrics['scenarios'][0]
        expected = EXPECTED['expected']
        for field in ('attempts', 'successful_attempts', 'censored_durations', 'failure_categories'):
            self.assertEqual(summary[field], expected[field])
        self.assertAlmostEqual(summary['success_rate_pct'], expected['success_rate_pct'])
        self.assertEqual([t['cycle_time_s'] for t in trials], [10, 14, 6])
        for field in ('mean_s', 'median_s', 'min_s', 'max_s'):
            self.assertEqual(summary['successful_cycle_time'][field], expected[field])
        self.assertAlmostEqual(summary['successful_cycle_time']['sample_stdev_s']**2, 8)
        for phase in ('requested', 'accepted', 'completed'):
            self.assertEqual(summary['carrier_repositions_'+phase], expected[phase])

    def test_empty_dataset_is_explicit_and_has_no_success_percentage(self):
        fixture(self.raw, [])
        trials, metrics = analysis.analyze(self.path)
        self.assertEqual(trials, [])
        self.assertTrue(metrics['empty_dataset'])
        self.assertEqual(metrics['scenarios'], [])

    def test_duplicate_ids_rejected(self):
        specs = copy.deepcopy(EXPECTED['trials'])
        specs[1]['id'] = specs[0]['id']
        fixture(self.raw, specs)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            analysis.analyze(self.path)

    def test_malformed_boolean_rejected(self):
        text = self.path.read_text().replace('True', 'perhaps', 1)
        self.path.write_text(text)
        with self.assertRaisesRegex(ValueError, 'boolean'):
            analysis.analyze(self.path)

    def test_time_rollback_rejected(self):
        self.edit_events(lambda events: events[4].update(monotonic_elapsed_s=0))
        with self.assertRaisesRegex(ValueError, 'time inconsistency'):
            analysis.analyze(self.path)

    def test_duplicate_terminal_rejected(self):
        def duplicate(events):
            at = next(i for i,e in enumerate(events) if e['action'] == 'FINALIZE')
            events.insert(at, copy.deepcopy(events[at]))
            selected = [e for e in events if e['trial_id'] == events[0]['trial_id']]
            for i,e in enumerate(selected): e['sequence'] = i
        self.edit_events(duplicate)
        with self.assertRaisesRegex(ValueError, 'exactly one final'):
            analysis.analyze(self.path)

    def test_dangling_attempt_not_silently_dropped(self):
        self.edit_events(lambda events: events.append({**events[0], 'trial_id': 'dangling'}))
        with self.assertRaisesRegex(ValueError, 'dangling'):
            analysis.analyze(self.path)

    def test_missing_adapter_evidence_rejected(self):
        def change(events):
            next(e for e in events if e['action'] == 'ADAPTER_RESULT')['details']['ros_time_ns'] = 0
        self.edit_events(change)
        with self.assertRaisesRegex(ValueError, 'adapter result'):
            analysis.analyze(self.path)

    def test_changed_scenarios_are_separate(self):
        def change(events):
            [e for e in events if e['action'] == 'CONTEXT'][1]['details']['visual_time_scale'] = 2
        self.edit_events(change)
        _, metrics = analysis.analyze(self.path)
        self.assertEqual(len(metrics['scenarios']), 2)
        self.assertEqual(sorted(s['attempts'] for s in metrics['scenarios']), [1,2])

    def test_missing_duration_is_reported_when_failure_precedes_pick(self):
        def stop_before_pick(events):
            selected = [e for e in events if e['trial_id'] == 'fixture-failure-6']
            retained = [e for e in selected if e['action'] in ('START', 'CONTEXT', 'FINALIZE') or
                        e['result'] == 'FAILURE' or e['action'] == 'HOME_START' and e['result'] == 'STEP_STARTED' or
                        e['result'] == 'ENTERED' and e['state'] == 'HOME']
            adapter = next(e for e in selected if e['action'] == 'ADAPTER_RESULT' and e['result'] == 'FAILED')
            adapter['details']['step'] = 'HOME_START'
            retained.append(adapter)
            retained.sort(key=lambda e:e['monotonic_elapsed_s'])
            for i,e in enumerate(retained): e['sequence'] = i
            events[:] = [e for e in events if e['trial_id'] != 'fixture-failure-6'] + retained
        self.edit_events(stop_before_pick)
        trials, metrics = analysis.analyze(self.path)
        self.assertIsNone(trials[-1]['cycle_time_s'])
        self.assertEqual(metrics['scenarios'][0]['missing_durations'], 1)

    def test_raw_checksum_tampering_rejected(self):
        files = {p.name: analysis.sha256(p) for p in self.raw.iterdir() if p.is_file()}
        (self.raw/'checksums.json').write_text(json.dumps(files))
        analysis.verify_checksums(self.raw)
        self.path.write_text(self.path.read_text()+'\n')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            analysis.verify_checksums(self.raw)

    def test_nontrivial_threshold_home_exclusion_and_failed_completion(self):
        _, by_id = analysis.load_raw(self.path)
        events = by_id['fixture-success-14']
        for e in events:
            if e['action'] == 'CARRIER_MOTION' and e['details']['motion_id'] == '0':
                e['details'].update(station='HOME', is_reposition=False)
            if e['action'] == 'CARRIER_MOTION' and e['details']['motion_id'] == '1':
                e['details'].update(goal_joints_rad=[0]*6, final_joints_rad=[0]*6, nontrivial=False)
        counts = analysis.motion_counts(events)
        self.assertEqual(counts['completed'], 1)
        self.assertEqual(counts['all_completed'], 2)

    def test_completed_motion_must_reach_recorded_goal(self):
        def corrupt(events):
            next(e for e in events if e['action']=='CARRIER_MOTION' and e['result']=='COMPLETED')['details']['final_joints_rad']=[0]*6
        self.edit_events(corrupt)
        with self.assertRaisesRegex(ValueError, 'missed goal'):
            analysis.analyze(self.path)

    def test_cli_regenerates_tables_plots_and_preserves_raw_bytes(self):
        before = [analysis.sha256(p) for p in (self.path, self.path.with_suffix('.events.jsonl'))]
        out = self.root / 'derived'
        subprocess.run([sys.executable, str(BASE/'scripts/analyze_trials.py'), str(self.path), '--output', str(out)], check=True)
        original = (out/'metrics.json').read_bytes()
        subprocess.run([sys.executable, str(BASE/'scripts/analyze_trials.py'), str(self.path), '--output', str(out)], check=True)
        self.assertEqual(original, (out/'metrics.json').read_bytes())
        self.assertEqual(before, [analysis.sha256(p) for p in (self.path, self.path.with_suffix('.events.jsonl'))])
        with (out/'trials.csv').open() as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 3)
        for name, data in json.loads((out/'artifacts.json').read_text()).items():
            self.assertEqual(data['observations'], 3)
            self.assertGreater(data['bytes'], 1000)
        fixture(self.raw, [])
        subprocess.run([sys.executable, str(BASE/'scripts/analyze_trials.py'), str(self.path), '--output', str(out)], check=True)
        self.assertTrue(json.loads((out/'metrics.json').read_text())['empty_dataset'])


if __name__ == '__main__':
    unittest.main()
