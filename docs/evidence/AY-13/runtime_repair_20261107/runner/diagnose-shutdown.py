import os, signal, subprocess, time
from pathlib import Path
output=Path('/evidence/shutdown-parent-python')
output.mkdir(exist_ok=False)
with (output/'launch.log').open('w') as log:
    launch=subprocess.Popen(['ros2','launch','carrier_description','dual_arm_demo.launch.py','auto_start:=false','enable_coordination:=true'], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    time.sleep(8)
    subprocess.run(['ps','-eo','pid,ppid,pgid,sid,comm'], stdout=(output/'processes.txt').open('w'))
    launch.send_signal(signal.SIGINT)
    try:
        code=launch.wait(timeout=15)
        print('EXIT',code,flush=True)
    except subprocess.TimeoutExpired:
        print('TIMEOUT: SIGINT to launch PID did not stop processes',flush=True)
        os.killpg(launch.pid,signal.SIGTERM)
        launch.wait(timeout=10)
print((output/'launch.log').read_text()[-5500:])
