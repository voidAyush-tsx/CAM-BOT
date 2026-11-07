import os, signal, subprocess, time, sys
from pathlib import Path
out=Path('/evidence/rviz-gdb-' + sys.argv[1])
out.mkdir(exist_ok=False)
original=Path('/workspace/CAM-BOT/src/carrier_description/launch/dual_arm_demo.launch.py').read_text()
prefix="gdb -batch -ex 'handle SIGINT nostop noprint pass' -ex run -ex 'thread apply all bt' --args"
launch_file=out/'debug.launch.py'
launch_file.write_text(original.replace('package="rviz2",', 'package="rviz2",\n            prefix='+repr(prefix)+','))
with (out/'launch.log').open('w') as log:
    proc=subprocess.Popen(['ros2','launch',str(launch_file),'auto_start:=false','enable_coordination:=true','results_file:='+str(out/'trials.csv')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        subprocess.run(['python3','tools/ay0608_ros_probe.py'],stdout=(out/'probe.jsonl').open('w'),stderr=subprocess.STDOUT,check=True,timeout=110)
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=20)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            proc.wait(timeout=10)
text=(out/'launch.log').read_text()
print(out, 'CRASH' if 'received signal SIG' in text else 'normal')
if 'received signal SIG' in text: sys.exit(1)
