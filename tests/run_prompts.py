#!/usr/bin/env python3
"""Drive ComfyUI's HTTP API over a set of test prompts.

Reads tests/prompts.jsonl (one JSON object per line). Each record describes a
scene: a prompt, an output size, and a list of seeds. For every seed the driver
injects prompt/size/seed into the matching API-format workflow, queues it, waits
for completion, and saves the image as a repo asset under --out.

Record schema:
  { "id": str, "task": "t2i"|"edit", "note": str,
    "prompt": str, "size": {"w": int, "h": int},
    "batch": int, "seeds": [int, ...],
    "negative": str (optional), "steps": int (optional) }

Model-agnostic: the workflow JSON decides which model runs. Node ids used:
  t2i:  "6"=positive CLIPTextEncode, "7"=negative, "5"=EmptyLatent(w/h), "3"=KSampler(seed/steps)
If your re-exported workflow uses different ids, update NODE below.
"""
import argparse
import copy
import json
import time
import urllib.request
import urllib.parse
import uuid
from pathlib import Path

NODE = {"positive": "6", "negative": "7", "latent": "5", "sampler": "3"}


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


def build(workflow, rec, seed):
    wf = copy.deepcopy(workflow)
    wf[NODE["positive"]]["inputs"]["text"] = rec["prompt"]
    if "negative" in rec:
        wf[NODE["negative"]]["inputs"]["text"] = rec["negative"]
    size = rec.get("size", {})
    if "w" in size:
        wf[NODE["latent"]]["inputs"]["width"] = size["w"]
    if "h" in size:
        wf[NODE["latent"]]["inputs"]["height"] = size["h"]
    wf[NODE["sampler"]]["inputs"]["seed"] = seed
    if "steps" in rec:
        wf[NODE["sampler"]]["inputs"]["steps"] = rec["steps"]
    return wf


def queue_and_wait(server, workflow, client_id, timeout=900):
    pid = post(server, "/prompt", {"prompt": workflow, "client_id": client_id})["prompt_id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        hist = get(server, f"/history/{pid}")
        if pid in hist:
            return hist[pid]
        time.sleep(2)
    raise TimeoutError(f"prompt {pid} did not finish in {timeout}s")


def save_images(server, history, out_dir, stem):
    saved = []
    for node_out in history.get("outputs", {}).values():
        for i, img in enumerate(node_out.get("images", [])):
            params = urllib.parse.urlencode(
                {"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                 "type": img.get("type", "output")})
            with urllib.request.urlopen(f"{server}/view?{params}") as r:
                data = r.read()
            dest = Path(out_dir) / f"{stem}.png"
            dest.write_bytes(data)
            saved.append(str(dest))
    return saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--t2i-workflow", required=True)
    ap.add_argument("--edit-workflow", required=True)
    ap.add_argument("--out", required=True, help="asset output dir (committed to repo)")
    ap.add_argument("--only", default="", help="comma-separated scene ids to run (default: all)")
    args = ap.parse_args()

    Path(args.out).mkdir(parents=True, exist_ok=True)
    client_id = str(uuid.uuid4())
    base = {"t2i": load_json(args.t2i_workflow), "edit": load_json(args.edit_workflow)}
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    records = []
    with open(args.prompts) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            records.append(json.loads(line))

    report = []
    for rec in records:
        if only and rec["id"] not in only:
            continue
        task = rec.get("task", "t2i")
        seeds = rec.get("seeds") or list(range(rec.get("batch", 1)))
        print(f"\n[run] === {rec['id']} ({task}) :: {rec.get('note','')} — {len(seeds)} seeds ===")
        for seed in seeds:
            wf = build(base[task], rec, seed)
            stem = f"{rec['id']}_seed{seed}"
            t0 = time.time()
            try:
                hist = queue_and_wait(args.server, wf, client_id)
                imgs = save_images(args.server, hist, args.out, stem)
                dt = round(time.time() - t0, 1)
                print(f"[run]   {stem} -> {imgs} ({dt}s)")
                report.append({"id": rec["id"], "seed": seed, "seconds": dt, "images": imgs, "ok": bool(imgs)})
            except Exception as e:  # noqa: BLE001
                print(f"[run]   {stem} !! FAILED: {e}")
                report.append({"id": rec["id"], "seed": seed, "ok": False, "error": str(e)})

    Path(args.out, "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    ok = sum(1 for r in report if r["ok"])
    print(f"\n[run] {ok}/{len(report)} renders ok. Report: {Path(args.out)/'report.json'}")


if __name__ == "__main__":
    main()
