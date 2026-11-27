"""Shared bench config + helpers (stdlib only, so the HTTP client runs under any python3).

Matrix is fixed so every framework sees identical work:
  * 3 scenes from tests/prompts.jsonl (all 1024x1408, the repo's standard size)
  * cold  = first request after ready: scene[0] seed 11
  * warm  = 3 scenes x seeds (11, 22) = 6 images, sequential (concurrency 1); median s/img
  * c4    = 8 requests, 4 in flight (serving frameworks only); throughput = 8 / wall
Model params are the repo's (scripts/gen.py / DEPLOY_MODEL_RUNBOOK):
  qwen-turbo : Qwen/Qwen-Image-2.1-Turbo  8 steps, true_cfg_scale=1.0, negative_prompt=" "
  z-turbo    : Tongyi-MAI/Z-Image-Turbo   8 steps, guidance_scale=1.0
"""
import json, os, struct, subprocess, threading, time

SCENES = ["food_sandwich_bread", "cosmetic_lancome_essence", "portrait_bird"]
WARM_SEEDS = [11, 22]
C4_SEEDS = [33, 44, 55]
C4_N, C4_CONC = 8, 4

MODELS = {
    "qwen-turbo": {"repo": "Qwen/Qwen-Image-2.1-Turbo", "steps": 8,
                   "extra": {"true_cfg_scale": 1.0, "negative_prompt": " "}},
    "z-turbo": {"repo": "Tongyi-MAI/Z-Image-Turbo", "steps": 8,
                "extra": {"guidance_scale": 1.0}},
}


def load_scenes(path):
    recs = {}
    for line in open(path, encoding="utf-8"):
        if line.strip() and not line.startswith("#"):
            r = json.loads(line); recs[r["id"]] = r
    out = []
    for sid in SCENES:
        r = recs[sid]
        out.append({"id": sid, "prompt": r["prompt"], "w": r["size"]["w"], "h": r["size"]["h"]})
    return out


def warm_jobs(scenes):
    return [(s, seed) for s in scenes for seed in WARM_SEEDS]


def c4_jobs(scenes):
    jobs, i = [], 0
    while len(jobs) < C4_N:
        jobs.append((scenes[i % len(scenes)], C4_SEEDS[(i // len(scenes)) % len(C4_SEEDS)])); i += 1
    return jobs


def png_size(b):
    if b[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", b[16:24])


def median(xs):
    s = sorted(xs); n = len(s)
    return None if not n else (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)


class GpuSampler:
    """nvidia-smi memory.used sampled every 250 ms; .peak_mib() over the sampling window."""

    def __init__(self, path):
        self.path = path
        self.p = subprocess.Popen(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits",
                                   "-lms", "250"], stdout=open(path, "w"), stderr=subprocess.DEVNULL)

    def stop(self):
        self.p.terminate(); self.p.wait()
        return self.peak_mib()

    def peak_mib(self):
        vals = [int(x) for x in open(self.path).read().split() if x.strip().isdigit()]
        return max(vals) if vals else None


def gpu_info():
    q = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
                       capture_output=True, text=True).stdout.strip()
    cuda = ""
    for line in subprocess.run(["nvidia-smi"], capture_output=True, text=True).stdout.splitlines():
        if "CUDA Version" in line:
            cuda = line.split("CUDA Version:")[1].strip(" |"); break
    return {"gpu": q, "driver_cuda": cuda}


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w"), ensure_ascii=False, indent=2)
