#!/usr/bin/env python3
"""Validate immutable AY-09 events and derive AY-11/12 visual-runtime results."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/carrier_control'))
from carrier_control.metrics import SUMMARY_FIELDS, parameter_hash, validate_event, validate_trial_record
from carrier_control.machine_tending_fsm import STATE_STEPS
from carrier_control.workcell_model import target_world_xyz

BOUNDARY = 'S1_APPROACH STEP_STARTED through HOME_END STEP_COMPLETED; failures through terminal event'
COUNT_RULE = ('Distinct CARRIER_MOTION IDs with max absolute goal-start joint delta > 1e-6 rad; '
              'repositions exclude HOME. REQUESTED/ACCEPTED/COMPLETED counted separately. '
              'Visual COMPLETED means final joint publication, not controller execution.')
STATES = [state for state, _ in STATE_STEPS]
STEPS = [step for _, names in STATE_STEPS for step in names]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_checksums(raw_dir):
    raw_dir = Path(raw_dir)
    checksums = json.loads((raw_dir / 'checksums.json').read_text())
    actual = {str(p.relative_to(raw_dir)) for p in raw_dir.rglob('*')
              if p.is_file() and p.name != 'checksums.json'}
    require(set(checksums) == actual, 'raw capture inventory changed')
    for name, expected in checksums.items():
        require(sha256(raw_dir / name) == expected, f'raw checksum mismatch: {name}')


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'timezone missing')
    return parsed


def boolean(value):
    require(value in ('True', 'False', 'true', 'false'), f'invalid boolean: {value}')
    return value.lower() == 'true'


def load_raw(path):
    path = Path(path)
    with path.open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream)
        require(tuple(reader.fieldnames or ()) == SUMMARY_FIELDS, 'invalid CSV header')
        rows = list(reader)
    by_id = {}
    for row in rows:
        require(None not in row and all(v is not None for v in row.values()), 'malformed CSV row')
        row['cycle_time_s'] = float(row['cycle_time_s'])
        row['carrier_repositions'] = int(row['carrier_repositions'])
        for key in ('success', 'runtime_verified', 'end_to_end_verified'):
            row[key] = boolean(row[key])
        for key in ('failure_state', 'failure_reason'):
            row[key] = row[key] or None
        validate_trial_record(row)
        require(timestamp(row['end_timestamp_utc']) >= timestamp(row['start_timestamp_utc']),
                'end timestamp precedes start')
        require(row['trial_id'] not in by_id, 'duplicate trial ID')
        by_id[row['trial_id']] = row
    events = defaultdict(list)
    event_path = path.with_suffix('.events.jsonl')
    for line in event_path.read_text().splitlines():
        event = json.loads(line)
        validate_event(event)
        events[event['trial_id']].append(event)
    require(set(events) == set(by_id), 'summary/events ID mismatch: dangling attempts must not be dropped')
    return rows, events


def motion_counts(events):
    motions = defaultdict(list)
    for event in events:
        if event['action'] == 'CARRIER_MOTION':
            motions[event['details']['motion_id']].append(event)
    counts = Counter(requested=0, accepted=0, completed=0, all_completed=0)
    for selected in motions.values():
        phases = [e['result'] for e in selected]
        require(phases in (['REQUESTED'], ['REQUESTED', 'ACCEPTED'],
                           ['REQUESTED', 'ACCEPTED', 'COMPLETED'],
                           ['REQUESTED', 'ACCEPTED', 'FAILED']), 'invalid motion lifecycle')
        d = selected[0]['details']
        require(d['evidence_kind'] == 'visual_joint_publication', 'unknown motion evidence')
        for key in ('start_joints_rad', 'goal_joints_rad'):
            require(len(d[key]) == 6 and all(isinstance(x, (int, float)) and
                    not isinstance(x, bool) and math.isfinite(x) for x in d[key]),
                    'malformed motion joints')
        nontrivial = max(abs(a - b) for a, b in zip(d['start_joints_rad'], d['goal_joints_rad'])) > 1e-6
        require(d['nontrivial'] == nontrivial and d['is_reposition'] == (d['station'] != 'HOME'),
                'motion classification inconsistent')
        for event in selected:
            require(all(event['details'][key] == d[key] for key in d
                        if key not in ('ros_time_ns', 'final_joints_rad')), 'motion identity changed')
        if 'COMPLETED' in phases:
            final = selected[-1]['details']['final_joints_rad']
            require(len(final) == 6 and all(math.isfinite(x) and abs(x - y) <= 1e-9
                    for x, y in zip(final, d['goal_joints_rad'])), 'completed motion missed goal')
            counts['all_completed'] += int(nontrivial)
        if nontrivial and d['is_reposition']:
            for phase in ('requested', 'accepted', 'completed'):
                counts[phase] += int(phase.upper() in phases)
    return counts


def derive_trial(row, events):
    label = row['trial_id']
    require([e['sequence'] for e in events] == list(range(len(events))), f'{label}: event sequence')
    elapsed = [e['monotonic_elapsed_s'] for e in events]
    require(elapsed == sorted(elapsed), f'{label}: time inconsistency')
    wall = [timestamp(e['timestamp_utc']) for e in events]
    require(wall == sorted(wall), f'{label}: wall clock rollback; split/review this capture')
    require(all(e['experiment_id'] == row['experiment_id'] for e in events), 'experiment mismatch')
    require(events[0]['action'] == 'START' and sum(e['action'] == 'START' for e in events) == 1,
            'exactly one start required')
    finals = [e for e in events if e['action'] == 'FINALIZE']
    require(len(finals) == 1 and events[-1] == finals[0], 'exactly one final terminal record required')
    final = finals[0]
    require(final['result'] == row['status'] and final['details']['success'] == row['success']
            and final['details']['workpiece_final_state'] == row['workpiece_final_state']
            and final['details']['failure_reason'] == row['failure_reason'], 'terminal/row disagreement')
    require(abs(row['cycle_time_s'] - final['monotonic_elapsed_s']) <= 0.1,
            'logger duration/event time inconsistency')
    start = events[0]['details']
    require(all(start[k] == row[k] for k in ('git_commit', 'parameter_hash_sha256', 'parameter_config')),
            'source/config identity mismatch')
    terminals = [e for e in events if e['result'] in ('SUCCESS', 'FAILURE') and e['action'] == 'FSM']
    if row['status'] != 'INCOMPLETE':
        require(len(terminals) == 1, 'exactly one FSM terminal event required')
        require(terminals[0]['result'] == ('SUCCESS' if row['success'] else 'FAILURE'),
                'FSM terminal outcome mismatch')
        require(terminals[0]['details']['cause'] == row['failure_reason'], 'failure cause mismatch')
    else:
        require(len(terminals) <= 1, 'multiple FSM terminal events')
    entered = [e['state'] for e in events if e['result'] == 'ENTERED']
    require(entered == STATES[:len(entered)], 'invalid FSM state prefix')
    started_steps = [e['action'] for e in events if e['result'] == 'STEP_STARTED']
    require(started_steps == STEPS[:len(started_steps)], 'invalid started step prefix')
    completed = [e['action'] for e in events if e['result'] == 'STEP_COMPLETED']
    require(completed == STEPS[:len(completed)], 'invalid completed step prefix')
    require(len(completed) <= len(started_steps), 'completed step without start')
    if row['success']:
        require(entered == STATES and completed == STEPS and row['workpiece_final_state'] == 'FINISHED_AT_S5',
                'success missing full state/step sequence or final workpiece')
    contexts = [e['details'] for e in events if e['action'] == 'CONTEXT']
    require(len(contexts) == 1, 'one runtime context required; legacy records need explicit migration')
    context = contexts[0]
    require(row['mode'] == 'visual_simulation', 'this analysis version qualifies visual adapter evidence only')
    started = [e for e in events if e['result'] == 'STEP_STARTED' and e['action'] == 'S1_APPROACH']
    ends = [e for e in events if e['result'] == 'STEP_COMPLETED' and e['action'] == 'HOME_END']
    require(len(started) <= 1 and len(ends) <= 1, 'ambiguous cycle boundary')
    end = ends[0] if row['success'] else (terminals[0] if terminals else final)
    duration = end['monotonic_elapsed_s'] - started[0]['monotonic_elapsed_s'] if started else None
    require(duration is None or duration >= 0, 'negative derived duration')
    adapters = [e for e in events if e['action'] == 'ADAPTER_RESULT']
    for adapter in adapters:
        require(adapter['details']['step'] in started_steps and
                adapter['details'].get('ros_time_ns', 0) > 0, 'invalid timestamped adapter result')
    require(len({e['details']['step'] for e in adapters}) == len(adapters), 'duplicate adapter result')
    for step in completed:
        matching = [e for e in adapters if e['details']['step'] == step and e['result'] == 'COMPLETED']
        require(len(matching) == 1 and matching[0]['details'].get('ros_time_ns', 0) > 0,
                f'missing timestamped adapter result: {step}')
        begin = next(e for e in events if e['action'] == step and e['result'] == 'STEP_STARTED')
        finish = next(e for e in events if e['action'] == step and e['result'] == 'STEP_COMPLETED')
        require(begin['sequence'] < matching[0]['sequence'] < finish['sequence'], 'adapter lifecycle order')
    if not row['success'] and terminals:
        failed = [e for e in adapters if e['result'] == 'FAILED']
        require(bool(failed) or any(word in row['failure_reason'] for word in ('CANCEL', 'TIMEOUT', 'PRECONDITION')),
                'failed trial missing adapter failure or explicit FSM stop cause')
    counts = motion_counts(events)
    choices = [e for e in events if e['decision']]
    local = [e for e in choices if e['decision'] == 'LOCAL_MANIPULATION' and
             e['result'] == 'PENDING' and e['details']['attempts'] == 0]
    reposition = [e for e in choices if e['decision'] == 'LOCAL_MANIPULATION' and
                  e['result'] == 'RECHECKED_AFTER_CARRIER']
    group_key = {k: row[k] for k in ('experiment_id', 'git_commit', 'parameter_hash_sha256', 'mode')}
    group_key.update({k: context[k] for k in ('visual_time_scale', 'enable_coordination', 'fault_injection_step')})
    scenario = hashlib.sha256(json.dumps(group_key, sort_keys=True).encode()).hexdigest()[:12]
    return {
        'trial_id': label, 'scenario_id': scenario, 'mode': row['mode'], 'status': row['status'],
        'success': row['success'], 'failure_state': row['failure_state'], 'failure_reason': row['failure_reason'],
        'cycle_time_s': duration, 'duration_censored': not row['success'],
        'logger_elapsed_s': row['cycle_time_s'], 'carrier_repositions_requested': counts['requested'],
        'carrier_repositions_accepted': counts['accepted'], 'carrier_repositions_completed': counts['completed'],
        'carrier_moves_completed_including_home': counts['all_completed'],
        'local_no_reposition_steps': len(local), 'successful_rechecks': len(reposition),
        'runtime_verified': row['runtime_verified'], 'end_to_end_verified': row['end_to_end_verified'],
        'scenario': group_key,
    }


def aggregate(trials):
    groups = defaultdict(list)
    for trial in trials:
        groups[trial['scenario_id']].append(trial)
    summaries = []
    for scenario, selected in sorted(groups.items()):
        successful = [t['cycle_time_s'] for t in selected if t['success'] and t['cycle_time_s'] is not None]
        durations = {
            'mean_s': statistics.mean(successful) if successful else None,
            'median_s': statistics.median(successful) if successful else None,
            'min_s': min(successful) if successful else None,
            'max_s': max(successful) if successful else None,
            'sample_stdev_s': statistics.stdev(successful) if len(successful) > 1 else None,
        }
        summaries.append({
            'scenario_id': scenario, 'scenario': selected[0]['scenario'], 'attempts': len(selected),
            'successful_attempts': sum(t['success'] for t in selected),
            'success_rate_pct': 100 * sum(t['success'] for t in selected) / len(selected),
            'missing_durations': sum(t['cycle_time_s'] is None for t in selected),
            'censored_durations': sum(t['duration_censored'] for t in selected),
            'failure_categories': dict(Counter(t['failure_reason'] for t in selected if not t['success'])),
            'successful_cycle_time': durations,
            **{f'carrier_repositions_{phase}': sum(t[f'carrier_repositions_{phase}'] for t in selected)
               for phase in ('requested', 'accepted', 'completed')},
        })
    return summaries


def analyze(path):
    rows, by_id = load_raw(path)
    trials = [derive_trial(row, by_id[row['trial_id']]) for row in rows]
    capture = {}
    manifest_path = Path(path).parent / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        capture = {'source_tree_sha256': manifest['source_tree_sha256'],
                   'environment_sha256': parameter_hash(manifest['environment']),
                   'manifest_sha256': sha256(manifest_path)}
        for trial in trials:
            trial['scenario'].update({key: capture[key] for key in ('source_tree_sha256', 'environment_sha256')})
            trial['scenario_id'] = hashlib.sha256(json.dumps(trial['scenario'], sort_keys=True).encode()).hexdigest()[:12]
    return trials, {'analysis_version': 1, 'analysis_script_sha256': sha256(__file__), 'capture': capture,
                    'cycle_boundary': BOUNDARY, 'motion_count_rule': COUNT_RULE,
                    'input_sha256': {'trials.csv': sha256(path),
                                     'trials.events.jsonl': sha256(Path(path).with_suffix('.events.jsonl'))},
                    'attempts': len(trials), 'empty_dataset': not trials,
                    'comparison': 'descriptive only; no controlled baseline', 'scenarios': aggregate(trials)}


def qualify(raw_dir, trials, events, minimum=5):
    raw_dir = Path(raw_dir)
    verify_checksums(raw_dir)
    manifest = json.loads((raw_dir / 'manifest.json').read_text())
    plan = json.loads((raw_dir / 'config.json').read_text())
    require(parameter_hash(plan) == manifest['parameter_hash_sha256'], 'config hash mismatch')
    sources = manifest['source_files_sha256']
    require(parameter_hash(sources) == manifest['source_tree_sha256'], 'source tree hash mismatch')
    for name, expected in sources.items():
        require(sha256(raw_dir / 'source' / name) == expected, f'source snapshot mismatch: {name}')
    require(len(manifest['git_commit']) == 40 and manifest['environment']['ros_distro'] == 'humble',
            'missing source commit or Humble environment')
    require(manifest['mode'] == 'visual_simulation', 'unsupported qualification mode')
    require(len(trials) >= minimum, f'at least {minimum} actual attempted trials required')
    observations = [json.loads(line) for line in (raw_dir / 'attempts.jsonl').read_text().splitlines()]
    ready = [o for o in observations if o['event'] == 'RESET_VERIFIED']
    outcomes = [o for o in observations if o['event'] == 'OUTCOME_OBSERVED']
    requested = [o for o in observations if o['event'] == 'START_REQUESTED']
    accepted = [o for o in observations if o['event'] == 'START_ACCEPTED']
    post = [o for o in observations if o['event'] == 'POST_RESET_VERIFIED']
    require(len(ready) == len(outcomes) == len(trials), 'attempt/reset/outcome count mismatch')
    require(len(requested) == len(accepted) == len(trials), 'unresolved or uncounted start requests')
    require(observations[-1]['event'] == 'CAPTURE_FINISHED' and post, 'capture/final reset incomplete')
    require({o['trial_id'] for o in outcomes} == {t['trial_id'] for t in trials}, 'observer trial IDs mismatch')
    require(len({o['attempt'] for o in ready}) == len(ready), 'duplicate reset verification')
    joint_names = plan['carrier']['joint_names']
    expected_home = dict(zip(joint_names, plan['stations']['HOME']['visual_carrier_joints']))
    expected_home.update(zip(('left_shoulder_joint', 'left_elbow_joint', 'right_shoulder_joint', 'right_elbow_joint'),
                            plan['bimanual_poses']['HOME']))
    expected_home.update(zip(('workpiece_x_joint', 'workpiece_y_joint', 'workpiece_z_joint'),
                            target_world_xyz(plan['workcell'], 'RAW_PICK')))
    for reset in ready + post:
        require(all(abs(reset['joint_sample']['positions'][name] - value) < 1e-8
                    for name, value in expected_home.items()), 'observed reset joints not HOME')
        require(abs(reset['base_tf_stamp_ns'] - reset['joint_sample']['stamp_ns']) < 100_000_000,
                'reset TF and joint timestamps disagree')
        for station in plan['workcell']['stations'].values():
            measured = reset['stations'][station['frame']]
            require(all(abs(a-b) < 1e-7 for a,b in zip(measured['xyz_m'], station['pose_xyz_m'])),
                    'observed station differs from fixed configuration')
    topics = [json.loads(line) for line in (raw_dir / 'topics.jsonl').read_text().splitlines()]
    joint_samples = [t for t in topics if t['topic'] == 'joint_states']
    for t in trials:
        outcome = next(o for o in outcomes if o['trial_id'] == t['trial_id'])
        reset = next(o for o in ready if o['attempt'] == outcome['attempt'])
        require(reset['joint_home_verified'] and reset['station_tf_verified'] and reset['base_tf_ready']
                and reset['workpiece_state'] == 'RAW_AT_S1' and reset['publisher_count'] == 1,
                'reset/readiness not verified')
        require(reset['observer_ros_time_ns'] < outcome['observer_ros_time_ns'], 'reset after outcome')
        context = next(e for e in events[t['trial_id']] if e['action'] == 'CONTEXT')
        require(reset['observer_ros_time_ns'] < context['details']['ros_time_ns'], 'trial started before reset verified')
        require(all(t['scenario'][key] == manifest['parameters'][key]
                    for key in ('visual_time_scale', 'enable_coordination', 'fault_injection_step')),
                'runtime parameters differ from manifest')
        require(outcome['terminal']['event'] == ('SUCCESS' if t['success'] else 'FAILURE'), 'observer outcome mismatch')
        require(outcome['terminal']['cause'] == t['failure_reason'] if 'cause' in outcome['terminal']
                else t['success'], 'observer failure cause mismatch')
        require(t['scenario']['parameter_hash_sha256'] == manifest['parameter_hash_sha256'] and
                t['scenario']['git_commit'] == manifest['git_commit'], 'manifest identity mismatch')
        require(any(e['action'] == 'CARRIER_MOTION' for e in events[t['trial_id']]), 'motion evidence missing')
        for event in events[t['trial_id']]:
            if event['action'] != 'CARRIER_MOTION' or event['result'] != 'COMPLETED':
                continue
            motion = event['details']
            request = next(e for e in events[t['trial_id']] if e['action'] == 'CARRIER_MOTION'
                           and e['result'] == 'REQUESTED' and e['details']['motion_id'] == motion['motion_id'])
            require(any(request['details']['ros_time_ns'] <= sample['stamp_ns'] <= motion['ros_time_ns'] and
                        all(abs(sample['positions'][name] - value) < 1e-8
                            for name, value in zip(joint_names, motion['goal_joints_rad']))
                        for sample in joint_samples), 'completed motion lacks observed goal joint publication')
    require(len({t['scenario_id'] for t in trials}) == 1, 'qualify each differing scenario separately')
    require(any(t['local_no_reposition_steps'] for t in trials), 'local/no-reposition case missing')
    require(any(t['successful_rechecks'] for t in trials), 'reposition/recheck case missing')
    return {'qualification': 'VISUAL_SIMULATION_PASS', 'trials': len(trials),
            'actuation_verified': False, 'grasp_verified': False}


def write_csv(path, rows, fields):
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render(trials, metrics, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    trial_fields = [k for k in trials[0] if k != 'scenario'] if trials else [
        'trial_id', 'scenario_id', 'status', 'success', 'cycle_time_s', 'duration_censored']
    write_csv(output / 'trials.csv', [{k: t[k] for k in trial_fields} for t in trials], trial_fields)
    summaries = []
    for s in metrics['scenarios']:
        row = {k: v for k, v in s.items() if k not in ('scenario', 'successful_cycle_time', 'failure_categories')}
        row.update(s['successful_cycle_time'])
        row['failure_categories'] = json.dumps(s['failure_categories'], sort_keys=True)
        summaries.append(row)
    write_csv(output / 'summary.csv', summaries, list(summaries[0]) if summaries else ['scenario_id', 'attempts'])
    (output / 'metrics.json').write_text(json.dumps(metrics, indent=2, sort_keys=True) + '\n')
    plots = {}
    for kind in ('cycle_time_by_trial', 'trial_outcomes', 'carrier_repositions_by_trial'):
        fig, ax = plt.subplots(figsize=(max(8, min(16, len(trials) * 0.7)), 4.8))
        positions = list(range(1, len(trials) + 1))
        if not trials:
            ax.text(0.5, 0.5, 'No attempted trials; no measured results', ha='center', transform=ax.transAxes)
        elif kind == 'cycle_time_by_trial':
            for i, t in zip(positions, trials):
                if t['cycle_time_s'] is None:
                    ax.annotate('missing', (i, 0), rotation=90)
                else:
                    ax.bar(i, t['cycle_time_s'], color='#277b50' if t['success'] else '#bd4d35',
                           hatch='' if t['success'] else '//')
                    if not t['success']:
                        ax.annotate('censored', (i, t['cycle_time_s']), ha='center', fontsize=8)
            ax.set_ylabel('Elapsed time (s)')
        elif kind == 'trial_outcomes':
            for i, t in zip(positions, trials):
                ax.bar(i, 1, color='#277b50' if t['success'] else '#bd4d35')
                failure = t['failure_reason'] or ''
                ax.text(i, 0.5, t['status'] + ('\n' + failure if failure else ''),
                        ha='center', va='center', rotation=90, color='white', fontsize=8)
            ax.set_ylim(0, 1.05)
            ax.set_yticks([])
            ax.set_ylabel('One observation per attempted trial')
        else:
            for offset, phase, color in ((-0.25, 'requested', '#8da0cb'), (0, 'accepted', '#66c2a5'),
                                         (0.25, 'completed', '#265d7b')):
                ax.bar([i + offset for i in positions], [t[f'carrier_repositions_{phase}'] for t in trials],
                       width=0.24, label=phase, color=color)
            ax.set_ylabel('Nontrivial visual carrier repositions (count)')
            maximum = max(t['carrier_repositions_requested'] for t in trials)
            ax.set_ylim(0, max(1, maximum * 1.25))
            ax.legend(loc='upper center', ncol=3)
        ax.set_xticks(positions)
        ax.set_xticklabels([f'{i}\n{"success" if t["success"] else t["status"].lower()}'
                            for i, t in zip(positions, trials)])
        ax.set_xlabel('Attempt in raw record order (failed attempts retained)')
        subtitle = ('Visual joint publication; bars distinguish request, acceptance, completion'
                    if kind == 'carrier_repositions_by_trial' else
                    'Visual ROS simulation; green=success, red=failed/incomplete')
        ax.set_title(f'{kind.replace("_", " ").title()} — n={len(trials)}\n{subtitle}', fontsize=11)
        if len(metrics['scenarios']) > 1:
            ax.set_xticklabels([f'{i}\n{t["scenario_id"][:5]}\n{t["status"].lower()}' for i, t in zip(positions, trials)])
            ax.set_xlabel('Attempt / scenario (different scenarios are not pooled)')
        fig.tight_layout()
        fig.savefig(output / f'{kind}.png', dpi=160)
        plt.close(fig)
        plots[kind] = {'observations': len(trials), 'bytes': (output / f'{kind}.png').stat().st_size}
    (output / 'artifacts.json').write_text(json.dumps(plots, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw_csv', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--qualify', action='store_true', help='require >=5 attempts plus live reset/observer evidence')
    args = parser.parse_args()
    require(args.raw_csv.resolve().parent != args.output.resolve() and
            args.raw_csv.resolve().parent not in args.output.resolve().parents,
            'output must be separate from immutable raw data')
    trials, metrics = analyze(args.raw_csv)
    if args.qualify:
        _, events = load_raw(args.raw_csv)
        metrics['ay10'] = qualify(args.raw_csv.parent, trials, events)
    render(trials, metrics, args.output)
    print(json.dumps({'attempts': len(trials), 'scenarios': len(metrics['scenarios']), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
