"""Fail-closed checks before assembling a controlled-carrier launch."""

from pathlib import Path

from carrier_control.workflow import WorkflowError, load_plan


def validate_controller_launch(config_file, controller_bringup_file):
    """Require a validated plan and a selected, existing controller launch file."""
    plan = load_plan(config_file, require_controller_ready=True)
    bringup = Path(controller_bringup_file)
    if (not bringup.is_absolute() or not bringup.is_file() or
            not bringup.name.endswith(".launch.py")):
        raise WorkflowError(
            "controller_bringup_file must be an absolute path to an existing "
            "Python ROS launch file that starts the carrier controller and "
            "joint-state broadcaster"
        )
    return plan, bringup
