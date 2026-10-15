"""AY-06/08 policy and offline FSM integration; not ROS action verification."""

import json
from pathlib import Path
import unittest

from carrier_control.coordination_policy import CoordinationPolicy
from carrier_control.machine_tending_fsm import MachineTendingFSM, StepOutcome
from carrier_control.reachability import evaluate_reachability
from carrier_control.workcell_model import target_world_xyz


CONFIG = Path(__file__).resolve().parents[1] / "config/machine_tending.json"
COORDINATOR = (Path(__file__).resolve().parents[1] /
               "carrier_control/machine_tending_coordinator.py")
QUAT = (0.0, 0.0, 0.0, 1.0)
LOCAL_CENTER = (0.0, 0.25, 0.05)


def placed_at(target):
    return tuple(a - b for a, b in zip(target, LOCAL_CENTER)), QUAT


class TestCoordination(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(CONFIG.read_text())
        self.workspace = self.plan["workspace"]
        self.policy = CoordinationPolicy()
        self.target = target_world_xyz(self.plan["workcell"], "RAW_PICK")

    def choice(self, key, transform, candidate="S1_RAW"):
        reach = evaluate_reachability(self.target, transform, self.workspace)
        return self.policy.choose(key, self.target, "RAW_AT_S1", transform,
                                  reach, candidate)

    def test_positive_local_branch_makes_no_carrier_request(self):
        result = self.choice("raw", placed_at(self.target))
        self.assertEqual((result.decision, result.attempts),
                         ("LOCAL_MANIPULATION", 0))
        self.assertEqual(self.policy.issued, set())

    def test_positive_reposition_updated_tf_then_local(self):
        far = ((10.0, 0.0, 0.0), QUAT)
        self.assertEqual(self.choice("raw", far).decision, "CARRIER_REPOSITION")
        result = self.choice("raw", placed_at(self.target))
        self.assertEqual((result.decision, result.attempts),
                         ("LOCAL_MANIPULATION", 1))

    def test_negative_repeated_request_and_unreachable_recheck(self):
        far = ((10.0, 0.0, 0.0), QUAT)
        self.assertEqual(self.choice("raw", far).decision, "CARRIER_REPOSITION")
        second = self.choice("raw", far)
        self.assertEqual((second.decision, second.reason, second.attempts),
                         ("UNREACHABLE", "RECHECK_STILL_UNREACHABLE", 1))
        self.assertEqual(len(self.policy.issued), 1)
        self.assertEqual(self.choice("other", far, None).decision, "UNREACHABLE")
        self.assertEqual(self.choice("unknown", None).decision, "ERROR")

    def test_positive_full_offline_fsm_has_both_decisions_and_finishes(self):
        events, decisions, carrier_moves = [], [], []
        fsm = MachineTendingFSM(self.plan, events.append)
        transform = placed_at(self.target)

        def adapter(step, deadline, cancelled):
            nonlocal transform
            if not step.get("target"):
                return StepOutcome(True)
            target = target_world_xyz(self.plan["workcell"], step["target"])
            reach = evaluate_reachability(target, transform, self.workspace)
            choice = self.policy.choose(step["name"], target, fsm.workpiece_state,
                                        transform, reach, step["station"])
            decisions.append(choice.decision)
            if choice.decision == "CARRIER_REPOSITION":
                carrier_moves.append(step["name"])
                transform = placed_at(target)  # synthetic updated TF, not ROS
                reach = evaluate_reachability(target, transform, self.workspace)
                choice = self.policy.choose(step["name"], target,
                                            fsm.workpiece_state, transform,
                                            reach, step["station"])
                decisions.append(choice.decision)
            return StepOutcome(choice.decision == "LOCAL_MANIPULATION",
                               None if choice.decision == "LOCAL_MANIPULATION"
                               else choice.reason)

        fsm.start("offline-both-branches")
        outcome = fsm.run(adapter)
        self.assertTrue(outcome.success)
        self.assertEqual(outcome.workpiece_state, "FINISHED_AT_S5")
        self.assertIn("LOCAL_MANIPULATION", decisions)
        self.assertIn("CARRIER_REPOSITION", decisions)
        self.assertNotIn("S1_APPROACH", carrier_moves)
        self.assertEqual(len(carrier_moves), len(set(carrier_moves)))
        self.assertEqual(len([event for event in events
                              if event["event"] == "ENTERED"]), 8)

    def test_negative_rejected_carrier_stops_fsm_before_load_commit(self):
        events = []
        fsm = MachineTendingFSM(self.plan, events.append)

        def adapter(step, deadline, cancelled):
            if step["name"] == "S3_LOAD":
                return StepOutcome(False, "GOAL_REJECTED")
            return StepOutcome(True)

        fsm.start("rejected-load")
        outcome = fsm.run(adapter)
        self.assertEqual((outcome.failure_state, outcome.failure_step,
                          outcome.cause, outcome.workpiece_state),
                         ("LOAD_MACHINE", "S3_LOAD", "GOAL_REJECTED",
                          "HELD_RAW_AT_S2"))
        self.assertNotIn("MACHINE_DWELL", [event.get("step") for event in events])

    def test_positive_ros_adapter_contract_uses_live_tf_and_separate_mechanisms(self):
        source = COORDINATOR.read_text()
        for fragment in (
            'lookup_transform(', '"world", "dual_arm_base_link"',
            'def _coordinate_target(', 'def _move_carrier(',
            'def _animate_visual_state(', '"/cambot/coordination_decision"',
            '"TF_NOT_UPDATED"', '"BM_ACTUATION_UNAVAILABLE"',
            '"CARRIER_ACTION_SUCCEEDED_WITH_FEEDBACK"',
            'def _settled_base_transform(',
            'FINAL_TF_NOT_OBSERVED',
            'self.visual_carrier_positions = list(goal)',
            'if first_updated.status == "REACHABLE"',
            'list(self.visual_carrier_positions) + list(message.position)',
        ):
            self.assertIn(fragment, source)


if __name__ == "__main__":
    unittest.main()
