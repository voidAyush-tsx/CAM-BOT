#!/usr/bin/env python3
"""Snapshot actual source/environment and seal a new AY-10 raw capture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/carrier_control'))
from carrier_control.metrics import parameter_hash


def command(*args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('raw_dir', type=Path)
    parser.add_argument('count', type=int)
    parser.add_argument('--seal', action='store_true')
    args = parser.parse_args()
    raw = args.raw_dir
    if args.seal:
        files = {str(p.relative_to(raw)): digest(p) for p in sorted(raw.rglob('*'))
                 if p.is_file() and p.name != 'checksums.json'}
        (raw / 'checksums.json').write_text(json.dumps(files, indent=2, sort_keys=True) + '\n')
        return
    (raw / 'source.patch').write_text(command('git', 'diff', '--binary', 'HEAD') + '\n')
    sources = {}
    # Include untracked implementation files: the base commit alone cannot identify a dirty run.
    for base in ('src', 'tools', 'experiments/machine_tending/scripts'):
        for p in sorted((ROOT / base).rglob('*')):
            if p.is_file() and p.suffix in ('.py', '.json', '.xml', '.xacro', '.yaml', '.rviz', '.sh'):
                if any(part in ('__pycache__', 'build', 'install') for part in p.parts):
                    continue
                rel = p.relative_to(ROOT)
                destination = raw / 'source' / rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, destination)
                sources[str(rel)] = digest(p)
    manifest = {
        'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'mode': 'visual_simulation', 'scenario': 'ay10-visual-fixed-v1', 'requested_attempts': args.count,
        'git_commit': command('git', 'rev-parse', 'HEAD'),
        'git_status': command('git', 'status', '--porcelain'),
        'source_tree_sha256': parameter_hash(sources), 'source_files_sha256': sources,
        'parameter_hash_sha256': parameter_hash(json.loads((raw / 'config.json').read_text())),
        'parameters': {'auto_start': False, 'enable_coordination': True, 'trial_count': 1,
                       'visual_time_scale': 1.0, 'fault_injection_step': ''},
        'environment': {'platform': platform.platform(), 'python': sys.version,
                        'os_release': Path('/etc/os-release').read_text(),
                        'ros_distro': os.getenv('ROS_DISTRO'), 'ros_domain_id': os.getenv('ROS_DOMAIN_ID'),
                        'rmw_implementation': os.getenv('RMW_IMPLEMENTATION', 'ROS default'),
                        'qt_qpa_platform': os.getenv('QT_QPA_PLATFORM'),
                        'libgl_always_software': os.getenv('LIBGL_ALWAYS_SOFTWARE'),
                        'packages': command('dpkg-query', '-W', 'ros-humble-rclpy', 'ros-humble-robot-state-publisher',
                                            'ros-humble-ur-description', 'ros-humble-rviz2', 'python3-matplotlib')},
        'invocation': ['bash', 'tools/capture_ay10_humble.sh', str(raw), str(args.count)],
        'reset': 'Trigger reset; observe fresh HOME joints, raw workpiece, station TF, base TF, one publisher before each start',
        'measurement': 'PICK_RAW S1_APPROACH STEP_STARTED through HOME_END STEP_COMPLETED; failures retained',
        'actuation_verified': False, 'grasp_verified': False,
    }
    (raw / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
