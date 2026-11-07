import os, signal, subprocess, time
from pathlib import Path
out=Path('/evidence/rviz-valgrind')
out.mkdir(exist_ok=False)
original=Path('/workspace/CAM-BOT/src/carrier_description/launch/dual_arm_demo.launch.py').read_text()
prefix='valgrind --tool=memcheck --num-callers=25 --error-limit=no --log-file=/evidence/rviz-valgrind/memory.log'
launch_file=out/'debug.launch.py'
launch_file.write_text(original.replace('package="rviz2",', 'package="rviz2",\n            sigterm_timeout="30", sigkill_timeout="10", prefix='+repr(prefix)+','))
with (out/'launch.log').open('w') as log:
    proc=subprocess.Popen(['ros2','launch',str(launch_file),'auto_start:=false','enable_coordination:=true','results_file:='+str(out/'trials.csv')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        deadline=time.monotonic()+100
        while 'Stereo is NOT SUPPORTED' not in (out/'launch.log').read_text():
            assert time.monotonic()<deadline,'RViz startup timed out'
            time.sleep(1)
        time.sleep(10)
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=45)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            proc.wait(timeout=15)
print('Valgrind capture complete')
