#!/usr/bin/env python3
"""Thin wrapper around scripts/launch.py / scripts/teardown.py for the framework bench.

Same verified region/AMI/disk as launch.py, but:
  * keeps the SSH key + launch.json at a STABLE path (~/.ssh/oss-bench/), not in
    $KIROCREW_SCRATCH (which is reclaimed on session roll -> box unreachable);
  * uses its own key-pair name (oss-bench-key) so it never collides with an
    existing `oss-image-lab-key` whose private half lives elsewhere.

Usage:
  python scripts/bench/launch_bench.py launch [--type g6e.xlarge]
  python scripts/bench/launch_bench.py teardown
"""
import argparse, importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.expanduser("~/.ssh/oss-bench")
KEY = "oss-bench-key"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "..", f"{name}.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["launch", "teardown"])
    ap.add_argument("--type", default="g6e.xlarge")
    a = ap.parse_args()
    os.makedirs(STATE, mode=0o700, exist_ok=True)
    os.environ["KIROCREW_SCRATCH"] = STATE  # teardown.py reads launch.json from here
    if a.action == "launch":
        m = _load("launch")
        m.SCRATCH, m.KEYFILE, m.KEY, m.INSTANCE_TYPE = STATE, os.path.join(STATE, "key"), KEY, a.type
        m.main()
    else:
        m = _load("teardown")
        m.KEY = KEY
        sys.argv = sys.argv[:1]
        m.main()


if __name__ == "__main__":
    main()
