#!/usr/bin/env python3
"""Dev helper: apply app changes to the running site automatically.

* DocType / Workflow seed / patches / hooks changes  -> `bench migrate`
* Jinja templates, www pages, public assets          -> clear the website cache
(Python code is reloaded by gunicorn --reload and by autoreload.py for the workers.)

Polling is used because inotify does not fire on Windows bind mounts.
"""

import os
import subprocess
import sys
import time

ROOT = os.environ.get("DM_APP_DIR", "/home/frappe/frappe-bench/apps/document_manager")
BENCH = "/home/frappe/frappe-bench"
POLL_SECONDS = 2.0
SKIP_DIRS = {"__pycache__", ".git", "node_modules"}

MIGRATE_FILES = {"hooks.py", "patches.txt", "install.py", "setup_workflows.py"}
MIGRATE_JSON_DIRS = ("doctype", "print_format", "report", "workspace", "fixtures", "page", "notification")
WEBSITE_SUFFIXES = (".html", ".js", ".css", ".md")


def site_name():
    name = os.environ.get("FRAPPE_SITE_NAME")
    if name:
        return name
    with open(os.path.join(BENCH, "sites", "currentsite.txt")) as handle:
        return handle.read().strip()


def snapshot():
    state = {}
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.endswith(".egg-info")]
        for name in files:
            path = os.path.join(base, name)
            try:
                state[path] = os.stat(path).st_mtime_ns
            except OSError:
                pass
    return state


def needs_migrate(path):
    rel = "/" + os.path.relpath(path, ROOT).replace(os.sep, "/")
    name = os.path.basename(rel)
    if name in MIGRATE_FILES or "/patches/" in rel:
        return True
    return name.endswith(".json") and any(f"/{d}/" in rel for d in MIGRATE_JSON_DIRS)


def needs_website_refresh(path):
    return path.endswith(WEBSITE_SUFFIXES) and "/tests/" not in path


def bench(site, *args):
    print("[watcher] bench --site", site, *args, flush=True)
    result = subprocess.run(["bench", "--site", site, *args], cwd=BENCH)
    if result.returncode:
        print(f"[watcher] command failed (exit {result.returncode}); fix the error and save again", flush=True)


def main():
    site = site_name()
    print(f"[watcher] watching {ROOT} for site {site}", flush=True)
    seen = snapshot()
    while True:
        time.sleep(POLL_SECONDS)
        current = snapshot()
        if current == seen:
            continue
        time.sleep(POLL_SECONDS)  # debounce
        current = snapshot()
        changed = [p for p in set(current) | set(seen) if current.get(p) != seen.get(p)]
        if any(needs_migrate(p) for p in changed):
            bench(site, "migrate")
            bench(site, "clear-website-cache")
        elif any(needs_website_refresh(p) for p in changed):
            bench(site, "clear-website-cache")
        seen = snapshot()  # migrate may rewrite files; do not retrigger on our own writes


if __name__ == "__main__":
    sys.exit(main())
