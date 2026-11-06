import json
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger

rclpy.init()
node = Node('unreachable_visual_observer')
tasks, decisions = [], []
def collect(target, topic):
    def callback(message):
        item = json.loads(message.data)
        target.append(item)
        print(json.dumps({'topic': topic, 'data': item}), flush=True)
    return callback
node.create_subscription(String, '/cambot/task_state', collect(tasks, 'task_state'), 100)
node.create_subscription(String, '/cambot/coordination_decision', collect(decisions, 'coordination_decision'), 100)
start = node.create_client(Trigger, '/machine_tending_coordinator/start')
deadline = time.monotonic() + 60
try:
    while not start.wait_for_service(timeout_sec=0.2):
        assert time.monotonic() < deadline, 'start unavailable'
    future = start.call_async(Trigger.Request())
    while not future.done() and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    assert future.done() and future.result().success, 'start rejected'
    while time.monotonic() < deadline and not any(x.get('event') in ('SUCCESS','FAILURE') for x in tasks):
        rclpy.spin_once(node, timeout_sec=0.1)
    for _ in range(5): rclpy.spin_once(node, timeout_sec=0.1)
    terminal = [x for x in tasks if x.get('event') in ('SUCCESS','FAILURE')][-1]
    entered = [x['state'] for x in tasks if x.get('event') == 'ENTERED']
    moves = [x for x in decisions if x.get('decision') == 'CARRIER_REPOSITION' and x.get('outcome') == 'PENDING']
    assert terminal['event'] == 'FAILURE' and terminal['workpiece_state'] == 'RAW_AT_S1', terminal
    assert entered == ['HOME','PICK_RAW'], entered
    assert len(moves) == 1, moves
    assert any(x.get('decision') == 'UNREACHABLE' and x.get('reason') == 'RECHECK_STILL_UNREACHABLE' for x in decisions), decisions
    print(json.dumps({'probe_result':'PASS','scenario':'unreachable_after_one_reposition','states':entered,'terminal':terminal,'reposition_requests':len(moves)}), flush=True)
finally:
    node.destroy_node()
    rclpy.shutdown()
