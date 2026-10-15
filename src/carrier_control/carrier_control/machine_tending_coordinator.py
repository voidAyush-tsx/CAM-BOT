#!/usr/bin/env python3
"""Feedback-gated CAM-BOT machine-tending workflow coordinator."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
from typing import Any, Dict, Optional

from ament_index_python.packages import get_package_share_directory
from control_msgs.action import FollowJointTrajectory
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger
from std_msgs.msg import String
from trajectory_msgs.msg import JointTrajectoryPoint
from tf2_ros import Buffer, TransformListener

from carrier_control.coordination_policy import CoordinationPolicy
from carrier_control.metrics import (
    ExperimentLogger, TrialRecordError, resolve_git_commit,
)
from carrier_control.machine_tending_fsm import FSMError, MachineTendingFSM, StepOutcome
from carrier_control.reachability import evaluate_reachability
from carrier_control.workflow import PROCESS_PHASES, WorkflowError, load_plan
from carrier_control.waypoints import UR5_JOINT_NAMES
from carrier_control.workcell_model import station_for_target, target_world_xyz


CUSTOM_JOINTS = (
    "left_shoulder_joint",
    "left_elbow_joint",
    "right_shoulder_joint",
    "right_elbow_joint",
)
WORKPIECE_JOINTS = (
    "workpiece_x_joint",
    "workpiece_y_joint",
    "workpiece_z_joint",
)
VISUAL_CARRIER_JOINTS = UR5_JOINT_NAMES


class MachineTendingCoordinator(Node):
    """Run one bounded, traceable workflow in controller or visual mode."""

    def __init__(self) -> None:
        super().__init__("machine_tending_coordinator")
        share = Path(get_package_share_directory("carrier_control"))
        default_config = str(share / "config" / "machine_tending.json")
        default_results = str(Path.home() / ".ros" / "cambot" / "machine_tending_trials.csv")
        self.declare_parameter("mode", "visual_simulation")
        self.declare_parameter("config_file", default_config)
        self.declare_parameter("results_file", default_results)
        self.declare_parameter("experiment_id", "cambot-machine-tending")
        self.declare_parameter("trial_count", 1)
        self.declare_parameter("visual_time_scale", 1.0)
        self.declare_parameter("auto_start", True)
        self.declare_parameter("fault_injection_step", "")
        self.declare_parameter("enable_coordination", False)

        self.mode = self.get_parameter("mode").value
        if self.mode not in ("controller", "visual_simulation"):
            raise WorkflowError("mode must be controller or visual_simulation")
        config_file = self.get_parameter("config_file").value
        self.plan = load_plan(
            config_file,
            require_controller_ready=self.mode == "controller",
        )
        self.results_file = self.get_parameter("results_file").value
        self.experiment_id = self.get_parameter("experiment_id").value
        if not isinstance(self.experiment_id, str) or not self.experiment_id:
            raise WorkflowError("experiment_id must be a nonempty string")
        self.experiment_logger = ExperimentLogger(
            self.results_file, self.experiment_id,
            resolve_git_commit(Path(__file__)), str(config_file), self.plan,
        )
        self.trial_count = int(self.get_parameter("trial_count").value)
        self.visual_time_scale = float(self.get_parameter("visual_time_scale").value)
        self.fault_injection_step = self.get_parameter("fault_injection_step").value
        self.enable_coordination = self.get_parameter("enable_coordination").value
        if not isinstance(self.enable_coordination, bool):
            raise WorkflowError("enable_coordination must be true or false")
        if self.mode == "controller" and not self.enable_coordination:
            raise WorkflowError("controller mode requires enable_coordination=true")
        auto_value = self.get_parameter("auto_start").value
        if isinstance(auto_value, bool):
            self.auto_start = auto_value
        elif isinstance(auto_value, str) and auto_value.lower() in ("true", "false"):
            self.auto_start = auto_value.lower() == "true"
        else:
            raise WorkflowError("auto_start must be true or false")
        if not 1 <= self.trial_count <= 25:
            raise WorkflowError("trial_count must be in [1, 25]")
        if not 0.01 <= self.visual_time_scale <= 10.0:
            raise WorkflowError("visual_time_scale must be in [0.01, 10.0]")
        if (not isinstance(self.fault_injection_step, str) or
                (self.fault_injection_step and self.mode != "visual_simulation") or
                (self.fault_injection_step and self.fault_injection_step not in
                 {step["name"] for step in self.plan["workflow"]})):
            raise WorkflowError(
                "fault_injection_step must name a workflow step in visual simulation only"
            )

        self.joint_publisher = self.create_publisher(JointState, "/joint_states", 10)
        self.task_publisher = self.create_publisher(String, "/cambot/task_state", 10)
        self.workpiece_publisher = self.create_publisher(
            String, "/cambot/workpiece_state", 10
        )
        self.coordinator_publisher = self.create_publisher(
            String, "/cambot/coordinator_state", 10
        )
        self.decision_publisher = self.create_publisher(
            String, "/cambot/coordination_decision", 10
        )
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self, spin_thread=False)
        self.policy = CoordinationPolicy(
            self.plan["workspace"]["max_reposition_attempts"]
        )

        self.custom_positions = list(self.plan["bimanual_poses"]["HOME"])
        self.visual_carrier_positions = list(
            self.plan["stations"]["HOME"]["visual_carrier_joints"]
        )
        self.workpiece_positions = target_world_xyz(self.plan["workcell"], "RAW_PICK")
        self.workpiece_state = "RAW_AT_S1"
        self.coordinator_state = "INITIALIZING"
        self.carrier_motion_count = 0
        self.carrier_reposition_count = 0
        self.feedback_count = 0
        self.feedback_joint_travel = 0.0
        self._last_feedback_positions: Optional[list[float]] = None
        self.carrier_joint_sample: Optional[tuple[float, ...]] = None
        self.client = None
        self.last_motion_failure = None
        self.last_local_decision = None
        self.start_requested = False
        self.fsm = MachineTendingFSM(
            self.plan,
            notify=self._fsm_event,
            timeout_scale=(max(1.0, self.visual_time_scale)
                           if self.mode == "visual_simulation" else 1.0),
        )

        if self.mode == "controller":
            self.client = ActionClient(
                self,
                FollowJointTrajectory,
                self.plan["carrier"]["action_name"],
            )
            timeout = self.plan["carrier"]["server_timeout_s"]
            if not self.client.wait_for_server(timeout_sec=timeout):
                raise RuntimeError(
                    f"carrier controller unavailable after {timeout:.1f}s"
                )
            self.carrier_joint_subscription = self.create_subscription(
                JointState, "/joint_states", self._carrier_joint_state, 10
            )
            joint_deadline = time.monotonic() + timeout
            while self.carrier_joint_sample is None:
                remaining = joint_deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError(
                        f"carrier /joint_states unavailable after {timeout:.1f}s"
                    )
                rclpy.spin_once(self, timeout_sec=min(0.1, remaining))
        else:
            self.get_logger().warning(
                "VISUAL SIMULATION ONLY: carrier joints are not commanded; "
                "this run is not runtime or end-to-end verification"
            )

        self._publish_coordinator("READY")
        self._publish_workpiece()
        self._publish_visual_joints()
        self.start_service = self.create_service(Trigger, "~/start", self._start_service)
        self.reset_service = self.create_service(Trigger, "~/reset", self._reset_service)
        self.cancel_service = self.create_service(Trigger, "~/cancel", self._cancel_service)

    def _publish_json(self, publisher, payload: Dict[str, Any]) -> None:
        message = String()
        message.data = json.dumps(payload, sort_keys=True)
        publisher.publish(message)

    def _publish_coordinator(self, state: str, **extra: Any) -> None:
        self.coordinator_state = state
        self._publish_json(
            self.coordinator_publisher,
            {"state": state, "mode": self.mode, **extra},
        )

    def _publish_task(self, state: str, **extra: Any) -> None:
        self._publish_json(
            self.task_publisher,
            {"state": state, "mode": self.mode, **extra},
        )

    def _fsm_event(self, event: Dict[str, Any]) -> None:
        payload = {**event, "mode": self.mode}
        step_name = event.get("step")
        if step_name:
            step = next(item for item in self.plan["workflow"]
                        if item["name"] == step_name)
            target_id = step.get("target")
            if target_id:
                station_id = station_for_target(self.plan["workcell"], target_id)
                payload.update({
                    "target": target_id,
                    "target_frame": self.plan["workcell"]["stations"][station_id]["frame"],
                    "visual_target_world_xyz_m": target_world_xyz(
                        self.plan["workcell"], target_id
                    ),
                })
        self._publish_json(self.task_publisher, payload)
        if self.experiment_logger.active is not None:
            self.experiment_logger.log_event(
                state=event.get("state") or "FSM",
                target=payload.get("target"), action=event.get("step") or "FSM",
                result=event["event"], details={
                    "ros_time_ns": self.get_clock().now().nanoseconds,
                    "workpiece_state": event["workpiece_state"],
                    "failure_step": event.get("failure_step"),
                    "cause": event.get("cause"),
                },
            )
        if event["event"] in ("STEP_COMPLETED", "RESET"):
            self.workpiece_state = event["workpiece_state"]
            if event["event"] == "RESET":
                self.workpiece_positions = target_world_xyz(
                    self.plan["workcell"], "RAW_PICK"
                )
                self.custom_positions = list(self.plan["bimanual_poses"]["HOME"])
                self.visual_carrier_positions = list(
                    self.plan["stations"]["HOME"]["visual_carrier_joints"]
                )
                self._publish_visual_joints()
            self._publish_workpiece()

    def _start_service(self, request, response):
        if self.fsm.status != "IDLE" or self.start_requested:
            response.success = False
            response.message = "start requires IDLE; reset after terminal state"
        else:
            self.start_requested = True
            response.success = True
            response.message = "one-shot cycle queued"
        return response

    def _reset_service(self, request, response):
        try:
            self.fsm.reset()
        except FSMError as exc:
            response.success = False
            response.message = str(exc)
            return response
        self.start_requested = False
        self.policy.reset()
        self._publish_coordinator("READY")
        response.success = True
        response.message = "FSM reset to IDLE and raw workpiece"
        return response

    def _cancel_service(self, request, response):
        if self.start_requested and self.fsm.status == "IDLE":
            self.start_requested = False
            response.success = True
            response.message = "queued start cancelled"
            return response
        try:
            self.fsm.cancel()
        except FSMError as exc:
            response.success = False
            response.message = str(exc)
            return response
        response.success = True
        response.message = "cancellation requested; awaiting bounded step stop"
        return response

    def _publish_workpiece(self) -> None:
        self._publish_json(
            self.workpiece_publisher,
            {
                "state": self.workpiece_state,
                "process_phase": PROCESS_PHASES[self.workpiece_state],
                "simulated_attachment": self.workpiece_state.startswith("HELD_"),
                "mode": self.mode,
                "visual_xyz": self.workpiece_positions,
            },
        )

    def _publish_visual_joints(self) -> None:
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = list(CUSTOM_JOINTS + WORKPIECE_JOINTS)
        message.position = self.custom_positions + self.workpiece_positions
        if self.mode == "visual_simulation":
            message.name = list(VISUAL_CARRIER_JOINTS) + message.name
            message.position = list(self.visual_carrier_positions) + list(message.position)
        self.joint_publisher.publish(message)

    def _feedback(self, message) -> None:
        positions = list(message.feedback.actual.positions)
        if len(positions) != len(self.plan["carrier"]["joint_names"]):
            return
        if self._last_feedback_positions is not None:
            self.feedback_joint_travel += sum(
                abs(current - previous)
                for current, previous in zip(positions, self._last_feedback_positions)
            )
        self._last_feedback_positions = positions
        self.feedback_count += 1

    def _carrier_joint_state(self, message: JointState) -> None:
        """Accept a complete UR5 sample, never our custom-only joint update."""
        positions = dict(zip(message.name, message.position))
        names = self.plan["carrier"]["joint_names"]
        if (len(message.name) == len(message.position) and
                all(name in positions and math.isfinite(positions[name]) for name in names)):
            self.carrier_joint_sample = tuple(float(positions[name]) for name in names)

    def _cancel_bounded(self, goal_handle) -> bool:
        cancel_future = goal_handle.cancel_goal_async()
        rclpy.spin_until_future_complete(self, cancel_future, timeout_sec=2.0)
        return bool(cancel_future.done() and cancel_future.result() is not None and
                    cancel_future.result().goals_canceling)

    def _wait_future(self, future, timeout_s, cancelled) -> str:
        deadline = time.monotonic() + timeout_s
        while not future.done():
            if cancelled():
                return "CANCELLED"
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return "TIMEOUT"
            rclpy.spin_once(self, timeout_sec=min(0.1, remaining))
        return "DONE"

    def _fail_move(self, cause, message) -> bool:
        self.last_motion_failure = cause
        self.get_logger().error(message)
        return False

    def _move_carrier(self, station_name: str, duration_s: float,
                      cancelled=lambda: False) -> bool:
        self.last_motion_failure = None
        if cancelled():
            return self._fail_move("CANCELLED", f"{station_name}: cancelled before goal")
        if self.mode == "visual_simulation":
            self._publish_task(
                "CARRIER_NOT_COMMANDED", station=station_name,
                fsm_state=self.fsm.current_state, trial_id=self.fsm.trial_id,
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
            )
            return True

        station = self.plan["stations"][station_name]
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = list(self.plan["carrier"]["joint_names"])
        point = JointTrajectoryPoint()
        point.positions = list(station["carrier_joints"])
        point.velocities = [0.0] * 6
        point.accelerations = [0.0] * 6
        point.time_from_start.sec = int(duration_s)
        point.time_from_start.nanosec = int((duration_s % 1.0) * 1e9)
        goal.trajectory.points.append(point)

        feedback_before = self.feedback_count
        send_future = self.client.send_goal_async(goal, feedback_callback=self._feedback)
        response_timeout = self.plan["carrier"]["goal_response_timeout_s"]
        response_wait = self._wait_future(send_future, response_timeout, cancelled)
        if response_wait == "CANCELLED":
            rclpy.spin_until_future_complete(
                self, send_future, timeout_sec=response_timeout
            )
            if (send_future.done() and send_future.result() is not None and
                    send_future.result().accepted):
                cancel_accepted = self._cancel_bounded(send_future.result())
            else:
                cancel_accepted = False
            cause = ("CANCEL_REQUEST_ACCEPTED" if cancel_accepted
                     else "CANCEL_UNCONFIRMED")
            return self._fail_move(cause, f"{station_name}: cancelled during goal response")
        if not send_future.done() or send_future.result() is None:
            return self._fail_move("GOAL_RESPONSE_TIMEOUT",
                                   f"{station_name}: goal response timed out")
        goal_handle = send_future.result()
        if not goal_handle.accepted:
            return self._fail_move("GOAL_REJECTED", f"{station_name}: trajectory rejected")

        result_future = goal_handle.get_result_async()
        result_timeout = duration_s + self.plan["carrier"]["result_margin_s"]
        result_wait = self._wait_future(result_future, result_timeout, cancelled)
        if result_wait == "CANCELLED":
            cancel_accepted = self._cancel_bounded(goal_handle)
            cause = ("CANCEL_REQUEST_ACCEPTED" if cancel_accepted
                     else "CANCEL_UNCONFIRMED")
            return self._fail_move(cause, f"{station_name}: cancellation requested")
        if not result_future.done() or result_future.result() is None:
            cancel_accepted = self._cancel_bounded(goal_handle)
            cause = ("RESULT_TIMEOUT_CANCEL_REQUEST_ACCEPTED" if cancel_accepted
                     else "RESULT_TIMEOUT_CANCEL_UNCONFIRMED")
            return self._fail_move(cause, f"{station_name}: result timed out; cancelling")
        result = result_future.result().result
        if result.error_code != FollowJointTrajectory.Result.SUCCESSFUL:
            return self._fail_move(
                f"CONTROLLER_ERROR_{result.error_code}",
                f"{station_name}: controller error {result.error_code}",
            )
        feedback_deadline = time.monotonic() + self.plan["carrier"][
            "feedback_timeout_s"
        ]
        while self.feedback_count <= feedback_before:
            if cancelled():
                return self._fail_move("CANCELLED_AFTER_RESULT",
                                       f"{station_name}: cancelled while awaiting feedback")
            remaining = feedback_deadline - time.monotonic()
            if remaining <= 0:
                break
            rclpy.spin_once(self, timeout_sec=min(0.1, remaining))
        if self.feedback_count <= feedback_before:
            return self._fail_move(
                "NO_ACTUAL_POSITION_FEEDBACK",
                f"{station_name}: success result had no actual-position feedback",
            )
        self.carrier_motion_count += 1
        return True

    @staticmethod
    def _state_target(state: str) -> Optional[str]:
        if state.endswith("AT_S1"):
            return "RAW_PICK"
        if state.endswith("AT_S2"):
            return "STAGE_INSPECT"
        if state.endswith("AT_S3") or state.endswith("IN_MACHINE"):
            return "MACHINE_UNLOAD" if "PROCESSED" in state else "MACHINE_LOAD"
        if state.endswith("AT_S4"):
            return "OUTPUT_UNLOAD"
        if state.endswith("AT_S5"):
            return "FINISHED_PLACE"
        return None

    def _animate_visual_state(
            self,
            pose_name: str,
            next_state: str,
            duration_s: float,
            station_name: Optional[str],
            deadline: float,
            cancelled,
    ) -> bool:
        start_custom = list(self.custom_positions)
        start_workpiece = list(self.workpiece_positions)
        start_carrier = list(self.visual_carrier_positions)
        target_custom = list(self.plan["bimanual_poses"][pose_name])
        target_workpiece = list(self.workpiece_positions)
        target_carrier = list(self.visual_carrier_positions)
        if self.mode == "visual_simulation" and station_name is not None:
            target_carrier = list(
                self.plan["stations"][station_name]["visual_carrier_joints"]
            )
        workpiece_target = self._state_target(next_state)
        if workpiece_target is not None:
            target_workpiece = target_world_xyz(self.plan["workcell"], workpiece_target)
        # In controller mode, placeholder joints have no actuator feedback.
        # Publish their visual target once; do not use sleep as action success.
        scaled_duration = (duration_s * self.visual_time_scale
                           if self.mode == "visual_simulation" else 0.0)
        ticks = max(1, int(scaled_duration * 20.0))
        for tick in range(1, ticks + 1):
            if cancelled() or time.monotonic() >= deadline:
                return False
            alpha = tick / ticks
            smooth = 3.0 * alpha * alpha - 2.0 * alpha * alpha * alpha
            self.custom_positions = [
                start + (target - start) * smooth
                for start, target in zip(start_custom, target_custom)
            ]
            self.visual_carrier_positions = [
                start + (target - start) * smooth
                for start, target in zip(start_carrier, target_carrier)
            ]
            self.workpiece_positions = [
                start + (target - start) * smooth
                for start, target in zip(start_workpiece, target_workpiece)
            ]
            self._publish_visual_joints()
            if scaled_duration > 0:
                rclpy.spin_once(self, timeout_sec=min(
                    scaled_duration / ticks, max(0.0, deadline - time.monotonic())
                ))
        return not cancelled() and time.monotonic() < deadline

    def _wait_machine_dwell(self, seconds, deadline, cancelled) -> bool:
        end = min(time.monotonic() + seconds, deadline)
        while time.monotonic() < end:
            if cancelled():
                return False
            rclpy.spin_once(self, timeout_sec=min(0.1, end - time.monotonic()))
        return not cancelled() and time.monotonic() < deadline

    def _current_base_transform(self, deadline, cancelled, previous=None):
        """Read current world->BM TF; after reposition require a changed pose."""
        until = min(deadline, time.monotonic() + self.plan["workspace"]["tf_timeout_s"])
        while time.monotonic() < until and not cancelled():
            try:
                if self.tf_buffer.can_transform("world", "dual_arm_base_link", Time()):
                    tf = self.tf_buffer.lookup_transform(
                        "world", "dual_arm_base_link", Time()
                    ).transform
                    pose = (
                        (tf.translation.x, tf.translation.y, tf.translation.z),
                        (tf.rotation.x, tf.rotation.y, tf.rotation.z, tf.rotation.w),
                    )
                    if previous is None or self._transform_changed(previous, pose):
                        return pose
            except Exception:
                pass
            rclpy.spin_once(self, timeout_sec=min(0.1, until - time.monotonic()))
        return None

    @staticmethod
    def _transform_changed(before, after):
        distance = sum((a - b) ** 2 for a, b in zip(before[0], after[0]))
        dot = abs(sum(a * b for a, b in zip(before[1], after[1])))
        return distance > 1e-8 or dot < 1 - 1e-6

    def _settled_base_transform(self, deadline, cancelled, previous=None):
        """
        Wait for a newer world->dual_arm_base_link TF to settle.

        Visual carrier motion publishes multiple intermediate joint states.
        Require several nearly-identical samples from a transform that is
        newer than ``previous`` before using it for a reachability recheck.
        """
        timeout = self.plan["workspace"]["tf_timeout_s"]
        until = min(deadline, time.monotonic() + timeout)

        latest = None
        stable_samples = 0
        required_stable_samples = 4
        translation_tol_sq = 1e-8
        quaternion_dot_tol = 1.0 - 1e-6

        while time.monotonic() < until and not cancelled():
            try:
                if self.tf_buffer.can_transform(
                    "world", "dual_arm_base_link", Time()
                ):
                    tf = self.tf_buffer.lookup_transform(
                        "world", "dual_arm_base_link", Time()
                    ).transform
                    pose = (
                        (
                            tf.translation.x,
                            tf.translation.y,
                            tf.translation.z,
                        ),
                        (
                            tf.rotation.x,
                            tf.rotation.y,
                            tf.rotation.z,
                            tf.rotation.w,
                        ),
                    )

                    if previous is not None and not self._transform_changed(
                        previous, pose
                    ):
                        rclpy.spin_once(self, timeout_sec=0.05)
                        continue

                    if latest is None:
                        latest = pose
                        stable_samples = 1
                    else:
                        translation_delta_sq = sum(
                            (a - b) ** 2
                            for a, b in zip(latest[0], pose[0])
                        )
                        quaternion_dot = abs(
                            sum(a * b for a, b in zip(latest[1], pose[1]))
                        )
                        if (
                            translation_delta_sq <= translation_tol_sq
                            and quaternion_dot >= quaternion_dot_tol
                        ):
                            stable_samples += 1
                        else:
                            latest = pose
                            stable_samples = 1

                    if stable_samples >= required_stable_samples:
                        return latest
            except Exception:
                pass

            rclpy.spin_once(
                self,
                timeout_sec=min(
                    0.05, max(0.0, until - time.monotonic())
                ),
            )

        return latest

    def _animate_carrier_visual(self, station, duration_s, deadline, cancelled):
        """Record visual requests and completed publications, never actuator results."""
        if self.mode != "visual_simulation":
            return True
        start = list(self.visual_carrier_positions)
        goal = list(self.plan["stations"][station]["visual_carrier_joints"])
        motion_id = f"{self.fsm.trial_id}:{self.experiment_logger.active['sequence']}"
        details = {
            "motion_id": motion_id, "station": station,
            "start_joints_rad": start, "goal_joints_rad": goal,
            "nontrivial": max(abs(a - b) for a, b in zip(start, goal)) > 1e-6,
            "is_reposition": station != "HOME",
            "evidence_kind": "visual_joint_publication",
        }

        def emit(result):
            self.experiment_logger.log_event(
                state=self.fsm.current_state or "HOME", action="CARRIER_MOTION",
                result=result, details={
                    **details, "ros_time_ns": self.get_clock().now().nanoseconds,
                    "final_joints_rad": list(self.visual_carrier_positions),
                },
            )

        emit("REQUESTED")
        emit("ACCEPTED")  # Accepted by the visual adapter, not a ROS action server.
        completed = self._animate_carrier_visual_impl(
            station, duration_s, deadline, cancelled
        )
        emit("COMPLETED" if completed else "FAILED")
        return completed

    def _animate_carrier_visual_impl(self, station, duration_s, deadline, cancelled):
        if self.mode != "visual_simulation":
            return True
        start = list(self.visual_carrier_positions)
        goal = self.plan["stations"][station]["visual_carrier_joints"]
        ticks = max(1, int(duration_s * self.visual_time_scale * 20))
        interval = duration_s * self.visual_time_scale / ticks
        for tick in range(1, ticks + 1):
            if cancelled() or time.monotonic() >= deadline:
                return False
            alpha = tick / ticks
            smooth = 3 * alpha * alpha - 2 * alpha * alpha * alpha
            self.visual_carrier_positions = [
                a + (b - a) * smooth for a, b in zip(start, goal)
            ]
            self._publish_visual_joints()
            rclpy.spin_once(self, timeout_sec=min(
                interval, max(0.0, deadline - time.monotonic())
            ))

        # Publish the exact final carrier pose repeatedly so
        # robot_state_publisher consumes it and emits the corresponding final
        # TF before the reachability recheck.
        self.visual_carrier_positions = list(goal)
        for _ in range(4):
            if cancelled() or time.monotonic() >= deadline:
                return False
            self._publish_visual_joints()
            rclpy.spin_once(
                self,
                timeout_sec=min(
                    0.05, max(0.0, deadline - time.monotonic())
                ),
            )

        return not cancelled() and time.monotonic() < deadline

    def _emit_decision(self, step, target_xyz, transform, reach, decision,
                       outcome="PENDING"):
        payload = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "trial_id": self.fsm.trial_id,
            "step": step["name"], "target": step.get("target"),
            "target_world_xyz_m": target_xyz,
            "workpiece_state": self.fsm.workpiece_state,
            "world_from_dual_arm_base": transform,
            "local_xyz_m": reach.local_xyz_m,
            "reachability": reach.status, "arm_results": reach.arms,
            "decision": decision.decision, "reason": decision.reason,
            "attempts": decision.attempts, "outcome": outcome,
            "mode": self.mode,
        }
        self._publish_json(self.decision_publisher, payload)
        if self.experiment_logger.active is not None:
            self.experiment_logger.log_event(
                state=self.fsm.current_state or "COORDINATION",
                target=step.get("target"), reachability=reach.status,
                decision=decision.decision, action=step["name"], result=outcome,
                details={"reason": decision.reason,
                         "attempts": decision.attempts,
                         "target_world_xyz_m": target_xyz,
                         "world_from_dual_arm_base": transform,
                         "local_xyz_m": reach.local_xyz_m,
                         "arm_results": reach.arms},
            )

    def _coordinate_target(self, step, deadline, cancelled):
        """Policy selects; carrier adapter moves; TF recheck precedes BM adapter."""
        target_xyz = target_world_xyz(self.plan["workcell"], step["target"])
        command_id = (self.fsm.trial_id, step["name"])
        before = self._current_base_transform(deadline, cancelled)
        workspace = self.plan["workspace"]
        reach = evaluate_reachability(
            target_xyz, before, workspace, workspace["required_arms"]
        )
        decision = self.policy.choose(
            command_id, target_xyz, self.fsm.workpiece_state, before,
            reach, step["station"]
        )
        self._emit_decision(step, target_xyz, before, reach, decision)
        if decision.decision == "LOCAL_MANIPULATION":
            self.last_local_decision = (step, target_xyz, before, reach, decision)
            return StepOutcome(True)
        if decision.decision != "CARRIER_REPOSITION":
            return StepOutcome(False, decision.reason)
        station = step["station"]
        if not self._move_carrier(station, step["duration_s"], cancelled):
            self._emit_decision(step, target_xyz, before, reach, decision,
                                self.last_motion_failure or "CARRIER_ACTION_FAILED")
            return StepOutcome(False, self.last_motion_failure or "CARRIER_ACTION_FAILED")
        self.carrier_reposition_count += 1
        self._emit_decision(
            step, target_xyz, before, reach, decision,
            "CARRIER_ACTION_SUCCEEDED_WITH_FEEDBACK" if self.mode == "controller"
            else "CARRIER_VISUAL_ONLY",
        )
        if not self._animate_carrier_visual(station, step["duration_s"],
                                            deadline, cancelled):
            return StepOutcome(False, "CARRIER_VISUAL_UPDATE_CANCELLED_OR_TIMEOUT")
        # First accept any post-animation TF that already proves the target
        # reachable. If that first update is still outside the proxy, require
        # a newer settled transform so an intermediate visual carrier pose
        # cannot be mistaken for the final station pose.
        first_after = self._current_base_transform(
            deadline, cancelled, previous=before
        )
        if first_after is None:
            self._emit_decision(
                step, target_xyz, before, reach, decision, "TF_NOT_UPDATED"
            )
            return StepOutcome(False, "TF_NOT_UPDATED")

        first_updated = evaluate_reachability(
            target_xyz, first_after, workspace, workspace["required_arms"]
        )
        if first_updated.status == "REACHABLE":
            after = first_after
            updated = first_updated
        else:
            settled_after = self._settled_base_transform(
                deadline, cancelled, previous=first_after
            )
            if settled_after is None:
                self._emit_decision(
                    step, target_xyz, first_after, first_updated, decision,
                    "FINAL_TF_NOT_OBSERVED",
                )
                return StepOutcome(False, "FINAL_TF_NOT_OBSERVED")
            after = settled_after
            updated = evaluate_reachability(
                target_xyz, after, workspace, workspace["required_arms"]
            )
        recheck = self.policy.choose(
            command_id, target_xyz, self.fsm.workpiece_state, after,
            updated, station
        )
        self._emit_decision(step, target_xyz, after, updated, recheck,
                            "RECHECKED_AFTER_CARRIER")
        if recheck.decision != "LOCAL_MANIPULATION":
            return StepOutcome(False, recheck.reason)
        self.last_local_decision = (step, target_xyz, after, updated, recheck)
        return StepOutcome(True)

    def _execute_fsm_step(self, step, deadline, cancelled) -> StepOutcome:
        try:
            outcome = self._execute_fsm_step_impl(step, deadline, cancelled)
        except Exception as exc:
            self.experiment_logger.log_event(
                state=self.fsm.current_state, action="ADAPTER_RESULT", result="FAILED",
                details={"step": step["name"], "cause": f"{type(exc).__name__}:{exc}",
                         "ros_time_ns": self.get_clock().now().nanoseconds,
                         "mode": self.mode},
            )
            raise
        self.experiment_logger.log_event(
            state=self.fsm.current_state, action="ADAPTER_RESULT",
            result="COMPLETED" if outcome.success else "FAILED",
            details={"step": step["name"], "cause": outcome.cause,
                     "ros_time_ns": self.get_clock().now().nanoseconds,
                     "mode": self.mode},
        )
        return outcome

    def _execute_fsm_step_impl(self, step, deadline, cancelled) -> StepOutcome:
        self.last_local_decision = None
        if step["name"] == self.fault_injection_step:
            return StepOutcome(False, "INJECTED_VISUAL_TEST_FAILURE")
        if step["name"] == "MACHINE_DWELL":
            completed = self._wait_machine_dwell(step["duration_s"], deadline, cancelled)
            return StepOutcome(completed, None if completed else "DWELL_CANCELLED_OR_TIMEOUT")
        if self.mode == "controller" and step["bimanual_pose"] != "HOME":
            return StepOutcome(False, "BM_ACTUATION_UNAVAILABLE")
        if step.get("target") and self.enable_coordination:
            coordinated = self._coordinate_target(step, deadline, cancelled)
            if not coordinated.success:
                return coordinated
        elif step["station"] is not None:
            if not self._move_carrier(step["station"], step["duration_s"], cancelled):
                return StepOutcome(False, self.last_motion_failure or "CARRIER_ACTION_FAILED")
            if not self._animate_carrier_visual(
                    step["station"], step["duration_s"], deadline, cancelled):
                return StepOutcome(False, "CARRIER_VISUAL_UPDATE_CANCELLED_OR_TIMEOUT")
        local_completed = self._animate_visual_state(
            step["bimanual_pose"], step["to_state"], step["duration_s"],
            None, deadline, cancelled)
        if self.last_local_decision is not None:
            self._emit_decision(
                *self.last_local_decision,
                outcome=("BM_VISUAL_UPDATE_ONLY" if local_completed else
                         "BM_VISUAL_UPDATE_FAILED"),
            )
        if not local_completed:
            return StepOutcome(False, "VISUAL_UPDATE_CANCELLED_OR_TIMEOUT")
        return StepOutcome(True)

    def run_trial(self, trial_number: int) -> Dict[str, Any]:
        trial_id = self.experiment_logger.begin_trial(self.mode)
        self.experiment_logger.log_event(
            state="TRIAL", action="CONTEXT", result="RECORDED",
            details={"visual_time_scale": self.visual_time_scale,
                     "enable_coordination": self.enable_coordination,
                     "fault_injection_step": self.fault_injection_step,
                     "ros_time_ns": self.get_clock().now().nanoseconds},
        )
        self.carrier_motion_count = 0
        self.carrier_reposition_count = 0
        self.policy.reset()
        self.feedback_count = 0
        self.feedback_joint_travel = 0.0
        self._last_feedback_positions = None
        self.workpiece_state = "RAW_AT_S1"
        self.workpiece_positions = target_world_xyz(self.plan["workcell"], "RAW_PICK")
        try:
            self._publish_coordinator("RUNNING", trial_id=trial_id)
            self._publish_workpiece()
            self.fsm.start(trial_id)
            outcome = self.fsm.run(self._execute_fsm_step)
            self._publish_coordinator(
                outcome.terminal, trial_id=trial_id,
                failure_state=outcome.failure_state,
                failure_stage=outcome.failure_step,
                failure_cause=outcome.cause,
            )
            return self.experiment_logger.finalize(
                success=outcome.success, failure_state=outcome.failure_state,
                failure_reason=outcome.cause,
                carrier_repositions=self.carrier_reposition_count,
                workpiece_final_state=outcome.workpiece_state,
                runtime_verified=False, end_to_end_verified=False,
                notes=(
                    "carrier results/feedback observed but BM/TF runtime unverified"
                    if self.mode == "controller" and outcome.success else
                    "controller trial failed; no end-to-end verification claim"
                    if self.mode == "controller" else
                    "visual state-machine exercise only; no actuation or verified grasp"
                ),
            )
        except BaseException as exc:
            if self.experiment_logger.active is not None:
                self.experiment_logger.finalize_incomplete(
                    reason=f"{type(exc).__name__}:{exc}",
                    state=self.fsm.current_state or "INTERRUPTED",
                    workpiece_state=self.fsm.workpiece_state,
                    notes="trial interrupted before a durable final summary",
                )
            raise

    def run_trials(self) -> bool:
        all_successful = True
        for trial_number in range(1, self.trial_count + 1):
            if trial_number > 1:
                self.fsm.reset()
            record = self.run_trial(trial_number)
            all_successful = all_successful and record["success"]
            if not record["success"]:
                break
        return all_successful


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = MachineTendingCoordinator()
        if node.auto_start:
            if not node.run_trials():
                raise RuntimeError("machine-tending FSM failed")
        else:
            while rclpy.ok():
                rclpy.spin_once(node, timeout_sec=0.1)
                if node.start_requested:
                    node.start_requested = False
                    node.run_trials()
    except (RuntimeError, WorkflowError, FSMError, TrialRecordError) as exc:
        if node is not None:
            node.get_logger().error(str(exc))
        else:
            print(f"machine_tending_coordinator: {exc}")
        raise
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
