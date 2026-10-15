#!/usr/bin/env python3

import time
from pathlib import Path

import rclpy
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from rclpy.action import ActionClient

from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint
from carrier_control.waypoints import UR5_JOINT_NAMES, load_waypoints


class MachineShopJointCycle(Node):

    def __init__(self):

        super().__init__('machine_shop_joint_cycle')

        # =====================================================
        # UR5 JOINT ORDER
        # =====================================================

        self.joint_names = list(UR5_JOINT_NAMES)

        waypoint_file = Path(get_package_share_directory('carrier_control')) / 'config' / 'waypoints.yaml'
        self.waypoints = load_waypoints(waypoint_file)
        self.get_logger().info(f'Loaded taught waypoints from {waypoint_file}')

        # =====================================================
        # CONTROLLER ACTION
        # =====================================================

        self.client = ActionClient(
            self,
            FollowJointTrajectory,
            '/joint_trajectory_controller/follow_joint_trajectory'
        )

        self.feedback_count = 0

        self.get_logger().info(
            'Waiting for joint trajectory controller...'
        )

        if not self.client.wait_for_server(
            timeout_sec=10.0
        ):

            self.get_logger().error(
                'Joint trajectory controller not available.'
            )

            raise RuntimeError(
                'Controller action unavailable'
            )

        self.get_logger().info(
            'Connected to joint trajectory controller.'
        )

    # =========================================================
    # MOVE TO JOINT CONFIGURATION
    # =========================================================

    def move_to(
        self,
        name,
        joints,
        move_time=2.0
    ):

        self.get_logger().info('')
        self.get_logger().info(
            '=========================================='
        )
        self.get_logger().info(
            f'MOVING TO {name}'
        )
        self.get_logger().info(
            '=========================================='
        )

        goal = FollowJointTrajectory.Goal()

        trajectory = goal.trajectory

        trajectory.joint_names = self.joint_names

        # -----------------------------------------------------
        # TARGET POINT
        # -----------------------------------------------------

        point = JointTrajectoryPoint()

        point.positions = joints

        point.velocities = [0.0] * 6

        point.accelerations = [0.0] * 6

        point.time_from_start.sec = int(move_time)

        point.time_from_start.nanosec = int(
            (move_time - int(move_time)) * 1e9
        )

        trajectory.points.append(point)

        # -----------------------------------------------------
        # SEND
        # -----------------------------------------------------

        feedback_before = self.feedback_count
        send_future = self.client.send_goal_async(
            goal,
            feedback_callback=self._feedback
        )

        rclpy.spin_until_future_complete(
            self,
            send_future,
            timeout_sec=5.0
        )

        if not send_future.done() or send_future.result() is None:
            self.get_logger().error(
                f'{name}: goal response timed out after 5.0 seconds.'
            )
            return False

        goal_handle = send_future.result()

        if not goal_handle.accepted:

            self.get_logger().error(
                f'{name}: trajectory rejected.'
            )

            return False

        self.get_logger().info(
            f'{name}: trajectory accepted.'
        )

        # -----------------------------------------------------
        # WAIT FOR RESULT
        # -----------------------------------------------------

        result_future = (
            goal_handle.get_result_async()
        )

        rclpy.spin_until_future_complete(
            self,
            result_future,
            timeout_sec=move_time + 5.0
        )

        if not result_future.done() or result_future.result() is None:
            self.get_logger().error(
                f'{name}: controller result timed out; cancelling goal.'
            )
            cancel_future = goal_handle.cancel_goal_async()
            rclpy.spin_until_future_complete(
                self,
                cancel_future,
                timeout_sec=2.0
            )
            return False

        result = result_future.result().result

        # -----------------------------------------------------
        # CONTROLLER RESULT
        # -----------------------------------------------------

        if result.error_code == 0:

            if self.feedback_count <= feedback_before:
                self.get_logger().error(
                    f'{name}: success result had no actual-position feedback.'
                )
                return False

            self.get_logger().info(
                f'{name}: motion completed successfully.'
            )

            return True

        self.get_logger().error(
            f'{name}: controller error '
            f'{result.error_code}'
        )

        return False

    def _feedback(self, message):
        """Count only feedback that includes all six actual joint positions."""
        if len(message.feedback.actual.positions) == len(self.joint_names):
            self.feedback_count += 1

    # =========================================================
    # HOLD
    # =========================================================

    def dwell(
        self,
        name,
        seconds=3.0
    ):

        self.get_logger().info(
            f'{name}: holding for '
            f'{seconds:.1f} seconds.'
        )

        time.sleep(seconds)

    # =========================================================
    # MACHINE SHOP CYCLE
    # =========================================================

    def run_cycle(self):
        HOME = self.waypoints['home']

        # =====================================================
        # STATIONS
        # =====================================================

        stations = [
            (name, self.waypoints[name]) for name in ('P1', 'P2', 'P3', 'P4')
        ]

        # =====================================================
        # INITIAL HOME
        # =====================================================

        if not self.move_to(
            'HOME',
            HOME,
            move_time=2.0
        ):
            return

        self.dwell(
            'HOME',
            self.waypoints['dwell_time']
        )

        # =====================================================
        # MACHINE SHOP CYCLE
        # =====================================================

        for name, configuration in stations:

            # -------------------------------------------------
            # HOME → STATION
            # -------------------------------------------------

            if not self.move_to(
                name,
                configuration,
                move_time=2.0
            ):

                self.get_logger().error(
                    f'Cycle stopped at {name}.'
                )

                return

            # -------------------------------------------------
            # STATION HOLD
            # -------------------------------------------------

            self.dwell(
                name,
                self.waypoints['dwell_time']
            )

            # -------------------------------------------------
            # STATION → HOME
            # -------------------------------------------------

            if not self.move_to(
                'HOME',
                HOME,
                move_time=2.0
            ):

                self.get_logger().error(
                    f'Failed to return HOME after {name}.'
                )

                return

            # -------------------------------------------------
            # HOME HOLD
            # -------------------------------------------------

            self.dwell(
                'HOME',
                self.waypoints['dwell_time']
            )

        # =====================================================
        # COMPLETE
        # =====================================================

        self.get_logger().info('')
        self.get_logger().info(
            '=========================================='
        )
        self.get_logger().info(
            ' MACHINE SHOP CYCLE COMPLETE'
        )
        self.get_logger().info(
            '=========================================='
        )


# =============================================================
# MAIN
# =============================================================

def main(args=None):

    rclpy.init(args=args)

    node = MachineShopJointCycle()

    try:

        node.run_cycle()

    except KeyboardInterrupt:

        node.get_logger().warn(
            'Cycle interrupted by user.'
        )

    finally:

        node.destroy_node()

        rclpy.shutdown()


if __name__ == '__main__':

    main()
