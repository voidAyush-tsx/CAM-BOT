import csv, json, os, signal, subprocess, sys, time
from pathlib import Path
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger
sys.path.insert(0, str(Path.cwd()))
from tools.check_ros_shutdown import check_shutdown
out=Path('/evidence/' + sys.argv[1])
out.mkdir(exist_ok=False)
rclpy.init()
node=Node('ay13_interrupt_observer')
events=[]
node.create_subscription(String,'/cambot/task_state',lambda msg: events.append(json.loads(msg.data)),100)
client=node.create_client(Trigger,'/machine_tending_coordinator/start')
with (out/'launch.log').open('w') as log:
    process=subprocess.Popen(['ros2','launch',sys.argv[2],'auto_start:=false','enable_coordination:=true','results_file:='+str(out/'trials.csv')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        deadline=time.monotonic()+30
        while not client.wait_for_service(timeout_sec=0.2):
            assert time.monotonic()<deadline,'start unavailable'
        future=client.call_async(Trigger.Request())
        while not future.done():
            assert time.monotonic()<deadline
            rclpy.spin_once(node,timeout_sec=0.1)
        assert future.result().success
        while not any(e.get('state')=='PICK_RAW' and e.get('event')=='ENTERED' for e in events):
            assert time.monotonic()<deadline
            rclpy.spin_once(node,timeout_sec=0.1)
        process.send_signal(signal.SIGINT)
        assert process.wait(timeout=15)==0
        check_shutdown((out/'launch.log').read_text())
        with (out/'trials.csv').open() as stream:
            rows=list(csv.DictReader(stream))
        assert len(rows)==1 and rows[0]['status']=='INCOMPLETE' and rows[0]['success']=='False',rows
        assert rows[0]['workpiece_final_state']=='RAW_AT_S1',rows
        (out/'result.json').write_text(json.dumps({'result':'PASS','shutdown_during':'PICK_RAW','trial':rows[0],'actuation_verified':False,'grasp_verified':False},indent=2)+'\n')
        print('ACTIVE_INTERRUPT_PASS: clean process exits and durable INCOMPLETE record')
    finally:
        node.destroy_node()
        rclpy.shutdown()
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            process.wait(timeout=10)
subprocess.run(['ros2','node','list','--no-daemon'],stdout=(out/'residual_nodes.txt').open('w'),check=True)
assert not (out/'residual_nodes.txt').read_text()
