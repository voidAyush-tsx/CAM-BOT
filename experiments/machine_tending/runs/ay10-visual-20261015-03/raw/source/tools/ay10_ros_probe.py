#!/usr/bin/env python3
"""Observe reset, readiness, and every attempted visual FSM trial on live ROS."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import time

import rclpy
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformListener

from carrier_control.workflow import load_plan
from carrier_control.workcell_model import target_world_xyz

CUSTOM = ['left_shoulder_joint', 'left_elbow_joint', 'right_shoulder_joint', 'right_elbow_joint']
WORKPIECE = ['workpiece_x_joint', 'workpiece_y_joint', 'workpiece_z_joint']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--count', type=int, default=5)
    parser.add_argument('--timeout-s', type=float, default=120)
    args = parser.parse_args()
    if args.count < 5:
        parser.error('AY-10 requires at least five actual attempts')
    plan = load_plan(args.raw_dir / 'config.json')
    rclpy.init()
    node = Node('ay10_trial_observer')
    buffer = Buffer()
    listener = TransformListener(buffer, node, spin_thread=False)
    tasks, workpieces, joints = [], [], []
    observer = (args.raw_dir / 'attempts.jsonl').open('x')
    topics = (args.raw_dir / 'topics.jsonl').open('x')

    def record(event, **data):
        entry = {'event': event, 'observer_ros_time_ns': node.get_clock().now().nanoseconds, **data}
        observer.write(json.dumps(entry, sort_keys=True) + '\n')
        observer.flush()
        os.fsync(observer.fileno())
        print(json.dumps(entry, sort_keys=True), flush=True)

    def collect(destination, topic):
        def callback(message):
            payload = json.loads(message.data)
            if destination is not None:
                destination.append(payload)
            topics.write(json.dumps({'topic': topic, 'received_ros_time_ns': node.get_clock().now().nanoseconds,
                                     'payload': payload}) + '\n')
            topics.flush()
        return callback

    for topic, target in [('task_state', tasks), ('workpiece_state', workpieces),
                          ('coordination_decision', None), ('coordinator_state', None)]:
        node.create_subscription(String, '/cambot/' + topic, collect(target, topic), 200)

    def joint_callback(message):
        sample = {'stamp_ns': message.header.stamp.sec * 10**9 + message.header.stamp.nanosec,
                  'positions': dict(zip(message.name, message.position))}
        joints.append(sample)
        if len(joints) > 100:
            del joints[:-100]
        topics.write(json.dumps({'topic': 'joint_states', **sample}) + '\n')
        topics.flush()

    node.create_subscription(JointState, '/joint_states', joint_callback, 200)
    clients = {name: node.create_client(Trigger, '/machine_tending_coordinator/' + name)
               for name in ('start', 'reset', 'cancel')}

    def spin_until(predicate, seconds, message):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            if predicate():
                return
            rclpy.spin_once(node, timeout_sec=0.05)
        raise RuntimeError(message)

    def call(name):
        client = clients[name]
        spin_until(lambda: client.service_is_ready(), 20, name + ' service unavailable')
        future = client.call_async(Trigger.Request())
        spin_until(future.done, 10, name + ' service timed out')
        response = future.result()
        if not response.success:
            raise RuntimeError(name + ' rejected: ' + response.message)
        return response.message

    def reset_and_observe(attempt, after=False):
        tasks.clear()
        workpieces.clear()
        joints.clear()
        reset_ns = node.get_clock().now().nanoseconds
        call('reset')
        expected = dict(zip(plan['carrier']['joint_names'], plan['stations']['HOME']['visual_carrier_joints']))
        expected.update(zip(CUSTOM, plan['bimanual_poses']['HOME']))
        expected.update(zip(WORKPIECE, target_world_xyz(plan['workcell'], 'RAW_PICK')))
        state = {}

        def ready():
            if not any(e.get('event') == 'RESET' for e in tasks):
                return False
            if not workpieces or workpieces[-1]['state'] != 'RAW_AT_S1' or not joints:
                return False
            sample = joints[-1]
            if sample['stamp_ns'] < reset_ns or any(
                key not in sample['positions'] or abs(sample['positions'][key] - value) > 1e-8
                for key, value in expected.items()
            ):
                return False
            try:
                base = buffer.lookup_transform('world', 'dual_arm_base_link', Time())
                base_stamp = base.header.stamp.sec * 10**9 + base.header.stamp.nanosec
                if base_stamp < reset_ns:
                    return False
                stations = {}
                for station in plan['workcell']['stations'].values():
                    transform = buffer.lookup_transform('world', station['frame'], Time()).transform
                    xyz = [transform.translation.x, transform.translation.y, transform.translation.z]
                    r, p, y = station['pose_rpy_rad']
                    cr, sr, cp, sp, cy, sy = math.cos(r/2), math.sin(r/2), math.cos(p/2), math.sin(p/2), math.cos(y/2), math.sin(y/2)
                    expected_q = [sr*cp*cy-cr*sp*sy, cr*sp*cy+sr*cp*sy, cr*cp*sy-sr*sp*cy, cr*cp*cy+sr*sp*sy]
                    q = [transform.rotation.x, transform.rotation.y, transform.rotation.z, transform.rotation.w]
                    if any(abs(a-b) > 1e-7 for a,b in zip(xyz, station['pose_xyz_m'])) or abs(sum(a*b for a,b in zip(q, expected_q))) < 1-1e-7:
                        return False
                    stations[station['frame']] = {'xyz_m': xyz, 'quaternion_xyzw': q}
                state.update(joint_home_verified=True, station_tf_verified=True, base_tf_ready=True,
                             joint_sample=sample, base_tf_stamp_ns=base_stamp, stations=stations,
                             workpiece_state=workpieces[-1]['state'], publisher_count=node.count_publishers('/joint_states'))
                return state['publisher_count'] == 1
            except Exception:
                return False

        spin_until(ready, 15, 'reset/HOME/station TF readiness could not be verified')
        record('POST_RESET_VERIFIED' if after else 'RESET_VERIFIED', attempt=attempt, **state)
        tasks.clear()
        workpieces.clear()

    try:
        for attempt in range(1, args.count + 1):
            reset_and_observe(attempt)
            record('START_REQUESTED', attempt=attempt)
            response = call('start')
            record('START_ACCEPTED', attempt=attempt, response=response)
            try:
                spin_until(lambda: any(e.get('event') in ('SUCCESS', 'FAILURE') for e in tasks),
                           args.timeout_s, 'trial deadline exceeded')
            except RuntimeError:
                record('CANCEL_REQUESTED', attempt=attempt, cause='OBSERVER_DEADLINE_EXCEEDED')
                call('cancel')
                spin_until(lambda: any(e.get('event') in ('SUCCESS', 'FAILURE') for e in tasks),
                           20, 'no terminal after cancellation; dataset remains BLOCKED')
            terminals = [e for e in tasks if e.get('event') in ('SUCCESS', 'FAILURE')]
            if len(terminals) != 1:
                raise RuntimeError('expected exactly one live FSM terminal')
            terminal = terminals[0]
            trial_id = terminal['trial_id']

            def finalized():
                path = args.raw_dir / 'trials.csv'
                if not path.exists():
                    return False
                with path.open() as stream:
                    return sum(r['trial_id'] == trial_id for r in csv.DictReader(stream)) == 1

            spin_until(finalized, 5, 'durable final row missing')
            record('OUTCOME_OBSERVED', attempt=attempt, trial_id=trial_id, terminal=terminal,
                   states=[e['state'] for e in tasks if e.get('event') == 'ENTERED'])
            # The next iteration's verified reset also resets after this attempt.
            # Avoid two immediate resets: robot_state_publisher can throttle the
            # second identical joint sample, preventing a fresh TF observation.
        reset_and_observe(args.count, after=True)
        record('CAPTURE_FINISHED', attempted=args.count, actuation_verified=False, grasp_verified=False)
    except BaseException as exc:
        record('CAPTURE_BLOCKED', cause=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        observer.close()
        topics.close()
        del listener
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
