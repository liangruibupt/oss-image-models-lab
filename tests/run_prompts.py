#!/usr/bin/env python3
"""Drive ComfyUI's HTTP API over a set of test prompts.

Reads tests/prompts.jsonl (one JSON object per line), injects each prompt into
the matching API-format workflow, queues it, waits for completion, and saves
the resulting images into --out. Model-agnostic: the workflow JSON decides which
model runs, so adding a new model = adding a workflow + pointing prompts at it.
"""
import argparse
import copy
import json
import time
import urllib.request
import urllib.parse
import uuid
from pathlib import Path


def load_json(p):
    with open(p) as f:
        return json.load(f)


def post(server, path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{server}{path}", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def get(server, path):
    with urllib.request.urlopen(f"{server}{path}") as r:
        return json.load(r)


def set_by_path(workflow, node_id, field, value):
    """workflow is the API-format graph: {node_id: {inputs:{...}, class_type:..}}"""
    workflow[node_id]["inputs"][field] = value


def apply_overrides(workflow, overrides):
    """overrides: list of {node, field, value} from the prompt record."""
    for o in overrides:
        set_by_path(workflow, str(o["node"]), o["field"], o["value"])


def queue_and_wait(server, workflow, client_id, timeout=600):
    resp = post(server, "/prompt", {"prompt": workflow, "client_id": client_id})
    pid = resp["prompt_id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        hist = get(server, f"/history/{pid}")
        if pid in hist:
            return hist[pid]
        time.sleep(2)
    raise TimeoutError(f"prompt {pid} did not finish in {timeout}s")


def save_images(server, history, out_dir, stem):
    saved = []
    outputs = history.get("outputs", {})
    for node_id, node_out in outputs.items():
        for img in node_out.get("images", []):
            params = urllib.parse.urlencode(
                {"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                 "type": img.get("type", "output")})
            with urllib.request.urlopen(f"{server}/view?{params}") as r:
                data = r.read()
            dest = Path(out_dir) / f"{stem}_{node_id}_{img['filename']}"
            dest.write_bytes(data)
            saved.append(str(dest))
    return saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--t2i-workflow", required=True)
    ap.add_argument("--edit-workflow", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    Path(args.out).mkdir(parents=True, exist_ok=True)
    client_id = str(uuid.uuid4())
    base = {
        "t2i": load_json(args.t2i_workflow),
        "edit": load_json(args.edit_workflow),
    }

    report = []
    with open(args.prompts) as f:
        records = [json.loads(line) for line in f if line.strip() and not line.startswith("#")]

    for i, rec in enumerate(records, 1):
        task = rec.get("task", "t2i")
        wf = copy.deepcopy(base[task])
        apply_overrides(wf, rec.get("overrides", []))
        stem = f"{i:02d}_{rec.get('id', task)}"
        print(f"[run] {stem} ({task}) :: {rec.get('note', '')}")
        t0 = time.time()
        try:
            hist = queue_and_wait(args.server, wf, client_id)
            imgs = save_images(args.server, hist, args.out, stem)
            dt = round(time.time() - t0, 1)
            print(f"[run]   -> {len(imgs)} image(s) in {dt}s")
            report.append({"id": stem, "task": task, "seconds": dt, "images": imgs, "ok": True})
        except Exception as e:  # noqa: BLE001
            print(f"[run]   !! FAILED: {e}")
            report.append({"id": stem, "task": task, "ok": False, "error": str(e)})

    Path(args.out, "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    ok = sum(1 for r in report if r["ok"])
    print(f"\n[run] {ok}/{len(report)} cases succeeded. Report: {Path(args.out)/'report.json'}")


if __name__ == "__main__":
    main()
