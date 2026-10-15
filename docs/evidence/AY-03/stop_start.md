# AY-03 start/stop outcomes

Three ROS launch/stop repetitions: **NOT RUN**. `ROS_DISTRO` is unset and
the host is CachyOS/Arch, not Ubuntu 22.04/Humble. The capture script rejects
this environment with exit 2. No child cleanup or resource release has been
observed here.

In a sourced Humble workspace with an RViz-capable GUI, run:

```bash
bash tools/capture_ay03_humble.sh
```

The script uses bounded retries, records `/joint_states` publisher authority,
nodes, topics, actions, `/tf`, `/tf_static`, workpiece state and SIGINT cleanup
on each of three visual-only starts, then checks that the supplied unvalidated
controller launch rejects promptly. Inspect visual appearance, process logs,
and node disappearance before accepting these as visual runtime evidence.
Controlled-carrier start/stop and dynamic UR5 joint checks remain blocked by
the missing controller bring-up and validated station targets.
