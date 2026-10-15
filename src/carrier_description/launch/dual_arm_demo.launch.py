from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

from carrier_control.workflow import load_plan
from carrier_control.workcell_model import render_workcell_xacro


def _assemble(context):
    trial_count = LaunchConfiguration("trial_count")
    visual_time_scale = LaunchConfiguration("visual_time_scale")
    config_file = LaunchConfiguration("config_file")
    results_file = LaunchConfiguration("results_file")
    experiment_id = LaunchConfiguration("experiment_id")
    auto_start = LaunchConfiguration("auto_start")
    fault_injection_step = LaunchConfiguration("fault_injection_step")
    enable_coordination = LaunchConfiguration("enable_coordination")
    xacro_file = (
        Path(get_package_share_directory("carrier_description")) /
        "urdf" / "ur5_with_test_tool.xacro"
    )
    rviz_config = PathJoinSubstitution([
        FindPackageShare("carrier_description"), "rviz", "dual_arm.rviz"
    ])
    plan = load_plan(config_file.perform(context))
    description = render_workcell_xacro(xacro_file, plan["workcell"])

    # Visual-only: one joint-state publisher, with no controller or actuation.
    return [
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            output="screen",
            parameters=[{"robot_description": description}],
        ),
        Node(
            package="carrier_control",
            executable="machine_tending_coordinator",
            name="machine_tending_coordinator",
            output="screen",
            parameters=[{
                "mode": "visual_simulation",
                "config_file": config_file,
                "results_file": results_file,
                "experiment_id": experiment_id,
                "trial_count": trial_count,
                "visual_time_scale": visual_time_scale,
                "auto_start": ParameterValue(auto_start, value_type=bool),
                "fault_injection_step": ParameterValue(
                    fault_injection_step, value_type=str
                ),
                "enable_coordination": ParameterValue(
                    enable_coordination, value_type=bool
                ),
            }],
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2",
            output="screen",
            arguments=["-d", rviz_config],
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("trial_count", default_value="1"),
        DeclareLaunchArgument("visual_time_scale", default_value="1.0"),
        DeclareLaunchArgument("auto_start", default_value="true"),
        DeclareLaunchArgument("fault_injection_step", default_value=""),
        DeclareLaunchArgument("enable_coordination", default_value="false"),
        DeclareLaunchArgument("config_file", default_value=PathJoinSubstitution([
            FindPackageShare("carrier_control"), "config", "machine_tending.json"
        ])),
        DeclareLaunchArgument("results_file", default_value=str(
            Path.home() / ".ros" / "cambot" / "machine_tending_trials.csv"
        )),
        DeclareLaunchArgument("experiment_id", default_value="cambot-machine-tending"),
        OpaqueFunction(function=_assemble),
    ])
