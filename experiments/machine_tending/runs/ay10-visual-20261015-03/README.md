# Qualifying AY-10 visual capture 03

Five actual attempts, five complete successful FSM cycles, 530 structured
node events. Each attempt has an independently observed pre-start HOME/raw
workpiece/station/TF reset, one FSM terminal, and one durable final CSV row.
The final reset was also observed. Both already-reachable/no-reposition and
carrier-reposition/TF-recheck cases were exercised in every trial.

`raw/` is the sealed source dataset, including node logs, observer events,
ROS bag, screenshot, fixed configuration, exact source snapshot and environment.
`raw_analysis/` contains AY-11 metrics and AY-12 tables/plots, regenerated without
changing raw files. Read [the experiment methods](../../README.md) for commands,
measurement boundaries, precise motion-count semantics, all preliminary captures,
and the distinction between visual evidence and controller/physical validation.

The source commit in raw records is the base commit; the recorded working-tree
patch and source snapshot are required to reconstruct this execution. All
physical/controller/grasp verification flags remain false.
