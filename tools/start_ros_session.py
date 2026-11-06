#!/usr/bin/env python3
"""Exec a ROS command in an owned session with SIGINT enabled.

Bash background jobs inherit SIGINT ignored. Reset it before exec so launch
can handle one parent-directed interrupt and relay it to its children.
"""

import os
import signal
import sys


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: start_ros_session.py COMMAND [ARG ...]")
    os.setsid()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
