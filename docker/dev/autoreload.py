#!/usr/bin/env python3
"""Run a command and restart it whenever a Python file of the app changes.

Used by the dev compose override for workers and the scheduler, which (unlike gunicorn --reload)
never reload code themselves. Polling is used because inotify does not fire on Windows bind mounts.

Usage: autoreload.py <command> [args...]
"""

import os
import signal
import subprocess
import sys
import time

ROOT = os.environ.get("DM_APP_DIR", "/home/frappe/frappe-bench/apps/document_manager")
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "public"}
POLL_SECONDS = 1.0


def snapshot():
    state = {}
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.endswith(".egg-info")]
        for name in files:
            if name.endswith(".py"):
                path = os.path.join(base, name)
                try:
                    state[path] = os.stat(path).st_mtime_ns
                except OSError:
                    pass
    return state


def stop(proc):
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def main():
    cmd = sys.argv[1:]
    if not cmd:
        sys.exit("usage: autoreload.py <command> [args...]")
    proc = subprocess.Popen(cmd)

    def forward(signum, _frame):
        stop(proc)
        sys.exit(0)

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)

    seen = snapshot()
    while True:
        time.sleep(POLL_SECONDS)
        code = proc.poll()
        if code is not None:
            sys.exit(code)  # let the container restart policy decide
        current = snapshot()
        if current != seen:
            time.sleep(POLL_SECONDS)  # debounce: wait for a burst of saves to finish
            current = snapshot()
            print("[autoreload] change detected, restarting:", " ".join(cmd), flush=True)
            stop(proc)
            seen = current
            proc = subprocess.Popen(cmd)
        seen = current


if __name__ == "__main__":
    main()
