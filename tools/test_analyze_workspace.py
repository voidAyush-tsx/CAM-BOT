"""Analytic kinematics fixtures and cross-checks against the runtime proxy."""

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from tools.analyze_workspace import Chain, ROOT, analyze, pose, proxy_margins
from carrier_control.reachability import evaluate_reachability


PLANAR = '''<robot name="two_link">
<joint name="shoulder" type="revolute">
  <parent link="world"/><child link="upper"/><axis xyz="0 0 1"/>
  <limit lower="-3.141592653589793" upper="3.141592653589793"/>
</joint>
<joint name="elbow" type="revolute">
  <parent link="upper"/><child link="forearm"/><origin xyz="1 0 0"/>
  <axis xyz="0 0 1"/><limit lower="-3.141592653589793" upper="3.141592653589793"/>
</joint>
<joint name="tool" type="fixed"><parent link="forearm"/>
  <child link="dual_arm_base_link"/><origin xyz="1 0 0"/>
</joint></robot>'''


class WorkspaceTests(unittest.TestCase):
    def test_two_link_analytic_positions(self):
        chain = Chain(PLANAR)
        results = chain.forward([[0, 0], [np.pi / 2, 0], [0, np.pi / 2],
                                 [np.pi / 2, -np.pi / 2]])
        np.testing.assert_allclose(results[:, :3, 3],
                                   [[2, 0, 0], [0, 2, 0], [1, 1, 0], [1, 1, 0]], atol=1e-14)

    def test_origin_rotation_precedes_joint_rotation(self):
        xml = PLANAR.replace('<origin xyz="1 0 0"/>',
                             '<origin xyz="1 0 0" rpy="0 0 1.5707963267948966"/>', 1)
        np.testing.assert_allclose(Chain(xml).forward([0, np.pi / 2])[0, :3, 3],
                                   [0, 0, 0], atol=1e-14)

    def test_limits_and_nonfinite_configurations_rejected(self):
        for q in ([0, 4], [float("nan"), 0], [0], [0, 0, 0]):
            with self.subTest(q=q), self.assertRaises(ValueError):
                Chain(PLANAR).forward(q)

    def test_unsupported_or_unbounded_joint_rejected(self):
        for xml in (PLANAR.replace('type="revolute"', 'type="continuous"', 1),
                    PLANAR.replace('lower="-3.141592653589793"', 'unused="0"', 1),
                    PLANAR.replace('axis xyz="0 0 1"', 'axis xyz="0 0 0"', 1)):
            with self.assertRaises(ValueError):
                Chain(xml)

    def test_missing_chain_rejected(self):
        with self.assertRaises(ValueError):
            Chain(PLANAR, tip="missing")

    def test_vectorized_proxy_agrees_with_runtime_evaluator(self):
        workspace = json.loads((ROOT / "src/carrier_control/config/machine_tending.json").read_text())["workspace"]
        rng = np.random.default_rng(42)
        for yaw in (0, np.pi / 2, -0.6):
            transform = pose([0.3, -0.2, 0.4], [0, 0, yaw])
            quaternion = [0, 0, np.sin(yaw / 2), np.cos(yaw / 2)]
            for target in rng.uniform(-0.3, 0.7, (100, 3)):
                runtime = evaluate_reachability(target.tolist(),
                    (transform[:3, 3].tolist(), quaternion), workspace)
                self.assertEqual(bool(proxy_margins(target, transform[None], workspace)[0] >= 0),
                                 runtime.status == "REACHABLE")

    def test_proxy_can_accept_both_arms_and_reject_one_arm(self):
        workspace = json.loads((ROOT / "src/carrier_control/config/machine_tending.json").read_text())["workspace"]
        self.assertGreater(proxy_margins([0, 0.1, 0.05], np.eye(4)[None], workspace)[0], 0)
        self.assertLess(proxy_margins([0.2, 0.1, 0.05], np.eye(4)[None], workspace)[0], 0)

    def test_refuses_existing_output_before_reading_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with self.assertRaises(FileExistsError):
                analyze(path / "absent", path / "absent", path / "absent", path)


if __name__ == "__main__":
    unittest.main()
