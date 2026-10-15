#!/usr/bin/env python3

import time

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import Constraints
from moveit_msgs.msg import PositionConstraint
from moveit_msgs.msg import OrientationConstraint

from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import JointState
from shape_msgs.msg import SolidPrimitive


class MachineShopTrajectory(Node):

    def __init__(self):

        super().__init__('machine_shop_trajectory')

        self.client = ActionClient(
            self,
            MoveGroup,
            '/move_action'
        )

        self.joint_names = [
            'shoulder_pan_joint',
            'shoulder_lift_joint',
            'elbow_joint',
            'wrist_1_joint',
            'wrist_2_joint',
            'wrist_3_joint'
        ]
        self.joint_feedback_count = 0
        self.joint_subscription = self.create_subscription(
            JointState,
            '/joint_states',
            self._joint_feedback,
            10
        )

        self.get_logger().info(
            'Waiting for MoveIt...'
        )

        if not self.client.wait_for_server(
            timeout_sec=10.0
        ):
            self.get_logger().error(
                'MoveIt action server not available.'
            )
            raise RuntimeError(
                'MoveIt unavailable'
            )

        self.get_logger().info(
            'Connected to /move_action'
        )

    def make_goal(self, x, y, z):

        goal = MoveGroup.Goal()

        request = goal.request

        # ------------------------------------------------
        # Planning group
        # ------------------------------------------------

        request.group_name = 'ur_manipulator'

        request.num_planning_attempts = 10

        request.allowed_planning_time = 10.0

        request.max_velocity_scaling_factor = 0.10

        request.max_acceleration_scaling_factor = 0.10

        # ------------------------------------------------
        # Goal constraints
        # ------------------------------------------------

        constraints = Constraints()

        # ------------------------------------------------
        # Position constraint
        # ------------------------------------------------

        position = PositionConstraint()

        position.header.frame_id = 'base_link'

        position.link_name = 'tool0'

        position.weight = 1.0

        sphere = SolidPrimitive()

        sphere.type = SolidPrimitive.SPHERE

        sphere.dimensions = [0.01]

        position.constraint_region.primitives.append(
            sphere
        )

        target_pose = PoseStamped()

        target_pose.header.frame_id = 'base_link'

        target_pose.pose.position.x = x
        target_pose.pose.position.y = y
        target_pose.pose.position.z = z

        target_pose.pose.orientation.x = -0.7071068
        target_pose.pose.orientation.y = 0.0
        target_pose.pose.orientation.z = 0.0
        target_pose.pose.orientation.w = 0.7071068

        position.constraint_region.primitive_poses.append(
            target_pose.pose
        )

        constraints.position_constraints.append(
            position
        )

        # ------------------------------------------------
        # Orientation constraint
        # ------------------------------------------------

        orientation = OrientationConstraint()

        orientation.header.frame_id = 'base_link'

        orientation.link_name = 'tool0'

        orientation.orientation = (
            target_pose.pose.orientation
        )

        # Relax tolerances for the first test.

        orientation.absolute_x_axis_tolerance = 0.15
        orientation.absolute_y_axis_tolerance = 0.15
        orientation.absolute_z_axis_tolerance = 0.15

        orientation.weight = 1.0

        constraints.orientation_constraints.append(
            orientation
        )

        request.goal_constraints.append(
            constraints
        )

        # ------------------------------------------------
        # Planner
        # ------------------------------------------------

        request.planner_id = ''

        # ------------------------------------------------
        # Execute after planning
        # ------------------------------------------------

        goal.planning_options.plan_only = False

        goal.planning_options.look_around = False

        goal.planning_options.replan = True

        goal.planning_options.replan_attempts = 5

        return goal

    def move_to(self, x, y, z):

        self.get_logger().info(
            f'Target: '
            f'X={x:.3f}, '
            f'Y={y:.3f}, '
            f'Z={z:.3f}'
        )

        goal = self.make_goal(
            x,
            y,
            z
        )

        feedback_before = self.joint_feedback_count
        send_future = self.client.send_goal_async(
            goal
        )

        rclpy.spin_until_future_complete(
            self,
            send_future,
            timeout_sec=12.0
        )

        if not send_future.done() or send_future.result() is None:
            self.get_logger().error(
                'MoveIt goal response timed out after 12.0 seconds.'
            )
            return False

        handle = send_future.result()

        if not handle.accepted:

            self.get_logger().error(
                'MoveIt rejected the goal.'
            )

            return False

        self.get_logger().info(
            'MoveIt accepted the goal.'
        )

        result_future = handle.get_result_async()

        rclpy.spin_until_future_complete(
            self,
            result_future,
            timeout_sec=35.0
        )

        if not result_future.done() or result_future.result() is None:
            self.get_logger().error(
                'MoveIt result timed out after 35.0 seconds; cancelling.'
            )
            cancel_future = handle.cancel_goal_async()
            rclpy.spin_until_future_complete(
                self,
                cancel_future,
                timeout_sec=2.0
            )
            return False

        result = result_future.result().result

        error = result.error_code.val

        self.get_logger().info(
            f'MoveIt error code: {error}'
        )

        if error == 1:

            if self.joint_feedback_count <= feedback_before:
                self.get_logger().error(
                    'MoveIt returned success without new /joint_states feedback.'
                )
                return False

            self.get_logger().info(
                'Motion executed successfully.'
            )

            return True

        self.get_logger().error(
            'MoveIt planning/execution failed.'
        )

        return False

    def _joint_feedback(self, message):
        """Count joint-state messages only when all carrier joints are present."""
        if all(name in message.name for name in self.joint_names):
            self.joint_feedback_count += 1


def main(args=None):

    rclpy.init(args=args)

    node = MachineShopTrajectory()

    try:

        # ==================================================
        # MACHINE SHOP STATIONS
        # ==================================================

        stations = [
            ("P1", 0.200, 0.241, 0.500),
            ("P2", 0.200, 0.341, 0.500),
            ("P3", 0.150, -0.341, 0.500),
            ("P4", 0.100, 0.241, 0.500),
            ("P5", 0.150, -0.291, 0.500),
        ]

        # ==================================================
        # EXECUTE STATION SEQUENCE
        # ==================================================

        for name, x, y, z in stations:

            node.get_logger().info("")
            node.get_logger().info(
                "=========================================="
            )

            node.get_logger().info(
                f"        MACHINE SHOP STATION {name}"
            )

            node.get_logger().info(
                "=========================================="
            )

            node.get_logger().info(
                "Target position:"
            )

            node.get_logger().info(
                f"  X = {x:.3f} m"
            )

            node.get_logger().info(
                f"  Y = {y:.3f} m"
            )

            node.get_logger().info(
                f"  Z = {z:.3f} m"
            )

            # ----------------------------------------------
            # PLAN + EXECUTE
            # ----------------------------------------------

            success = node.move_to(
                x,
                y,
                z
            )

            if not success:

                node.get_logger().error(
                    f"Station {name} failed."
                )

                return

            # ----------------------------------------------
            # DWELL
            # ----------------------------------------------

            node.get_logger().info(
                f"{name} reached successfully."
            )

            node.get_logger().info(
                "Performing machine operation..."
            )

            node.get_logger().info(
                "Holding position for 10 seconds."
            )

            time.sleep(10.0)

            node.get_logger().info(
                f"{name} operation complete."
            )

        # ==================================================
        # RETURN TO P1
        # ==================================================

        node.get_logger().info("")
        node.get_logger().info(
            "=========================================="
        )

        node.get_logger().info(
            "Returning to P1"
        )

        node.get_logger().info(
            "=========================================="
        )

        x, y, z = stations[0][1:]

        success = node.move_to(
            x,
            y,
            z
        )

        if success:

            node.get_logger().info(
                "Returned to P1."
            )

        else:

            node.get_logger().error(
                "Return to P1 failed."
            )

    except KeyboardInterrupt:

        node.get_logger().warn(
            "Trajectory interrupted by user."
        )

    finally:

        node.destroy_node()

        rclpy.shutdown()


if __name__ == '__main__':
    main()
