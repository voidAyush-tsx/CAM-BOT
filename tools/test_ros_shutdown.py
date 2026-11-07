"""Guard capture shutdown against ignored interrupts and hidden child crashes."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

from tools.check_ros_shutdown import check_shutdown


CLEAN = "\n".join(f"[INFO] [{name}-{index}]: process has finished cleanly [pid 123]"
                  for index, name in enumerate(
                      ("robot_state_publisher", "machine_tending_coordinator", "rviz2"), 1))


class ShutdownCaptureTests(unittest.TestCase):
    def test_clean_children(self):
        check_shutdown(CLEAN)

    def test_rviz_crash_is_not_hidden_by_successful_probe(self):
        with self.assertRaisesRegex(ValueError, "process has died"):
            check_shutdown(CLEAN + "\n[ERROR] [rviz2-3]: process has died [exit code -6]")

    def test_forced_termination_is_not_a_clean_shutdown(self):
        with self.assertRaisesRegex(ValueError, "failed to terminate"):
            check_shutdown(CLEAN + "\nprocess failed to terminate; escalating to SIGKILL")

    def test_missing_child_exit_fails(self):
        with self.assertRaisesRegex(ValueError, "rviz2"):
            check_shutdown(CLEAN.replace("rviz2", "different_node"))

    def test_background_session_restores_sigint_and_owns_process_group(self):
        helper = Path(__file__).with_name("start_ros_session.py").resolve()
        with tempfile.TemporaryDirectory() as directory:
            ready = Path(directory) / "ready"
            script = Path(directory) / "wait.py"
            script.write_text(
                "import os, signal, sys, time\n"
                "assert os.getpid() == os.getpgrp() == os.getsid(0)\n"
                "assert signal.getsignal(signal.SIGINT) != signal.SIG_IGN\n"
                "signal.signal(signal.SIGINT, lambda *args: sys.exit(0))\n"
                "open(sys.argv[1], 'w').close()\n"
                "while True: time.sleep(0.01)\n"
            )
            # A noninteractive Bash background child starts with SIGINT ignored.
            process = subprocess.Popen([
                "bash", "-c", '"$1" "$2" "$1" "$3" "$4" & child=$!; '
                'while [ ! -e "$4" ]; do sleep 0.01; done; '
                'kill -INT "$child"; wait "$child"',
                "test", sys.executable, str(helper), str(script), str(ready),
            ], start_new_session=True)
            try:
                self.assertEqual(0, process.wait(timeout=5))
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
