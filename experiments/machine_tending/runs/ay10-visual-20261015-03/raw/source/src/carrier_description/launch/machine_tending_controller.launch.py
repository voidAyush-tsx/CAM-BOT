"""Gated integration entry point for a supplied UR5 controller stack.

The repository does not contain that stack or validated station targets.
Preflight deliberately rejects the supplied default config before any node
is started. A selected external bring-up must provide the carrier action and
joint-state broadcaster; this file never starts dual_arm_cycle.
"""

from pathlib import Path

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, EmitEvent,
                            IncludeLaunchDescription, OpaqueFunction,
                            RegisterEventHandler, TimerAction)
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

from ament_index_python.packages import get_package_share_directory
from carrier_control.launch_preflight import validate_controller_launch
from carrier_control.workcell_model import render_workcell_xacro


def _assemble(context):
    config_file = LaunchConfiguration("config_file").perform(context)
    controller_file = LaunchConfiguration("controller_bringup_file").perform(context)
    plan, bringup = validate_controller_launch(config_file, controller_file)
    xacro_file = (
        Path(get_package_share_directory("carrier_description")) /
        "urdf" / "ur5_with_test_tool.xacro"
    )
    rviz_file = PathJoinSubstitution([
        FindPackageShare("carrier_description"), "rviz", "dual_arm.rviz"
    ])
    description = render_workcell_xacro(xacro_file, plan["workcell"])
    coordinator = Node(
        package="carrier_control", executable="machine_tending_coordinator",
        name="machine_tending_coordinator", output="screen",
        parameters=[{
            "mode": "controller", "config_file": config_file,
            "enable_coordination": True,
            "results_file": LaunchConfiguration("results_file"),
            "experiment_id": LaunchConfiguration("experiment_id"),
            "trial_count": LaunchConfiguration("trial_count"),
            "auto_start": ParameterValue(
                LaunchConfiguration("auto_start"), value_type=bool
            ),
        }],
    )
    return [
        Node(package="robot_state_publisher", executable="robot_state_publisher",
             name="robot_state_publisher", output="screen",
             parameters=[{"robot_description": description}]),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(bringup))),
        # The coordinator itself waits for the action server with a bounded
        # timeout. A short startup grace period is not treated as readiness.
        TimerAction(period=2.0, actions=[coordinator]),
        RegisterEventHandler(OnProcessExit(
            target_action=coordinator,
            on_exit=[EmitEvent(event=Shutdown(reason="coordinator exited"))],
        )),
        Node(package="rviz2", executable="rviz2", name="rviz2",
             output="screen", arguments=["-d", rviz_file]),
    ]


def generate_launch_description():
    default_config = (
        get_package_share_directory("carrier_control") + "/config/machine_tending.json"
    )
    return LaunchDescription([
        DeclareLaunchArgument("config_file", default_value=default_config),
        DeclareLaunchArgument("controller_bringup_file", default_value=""),
        DeclareLaunchArgument("results_file", default_value=str(
            Path.home() / ".ros" / "cambot" / "machine_tending_trials.csv"
        )),
        DeclareLaunchArgument("trial_count", default_value="1"),
        DeclareLaunchArgument("experiment_id", default_value="cambot-machine-tending"),
        DeclareLaunchArgument("auto_start", default_value="true"),
        OpaqueFunction(function=_assemble),
    ])
