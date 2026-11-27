#!/usr/bin/env python3
"""Diffusers baseline — reuses scripts/gen.py's load_pipe()/render() unchanged (the repo's verified path).

RUN ON THE GPU INSTANCE with ~/.venv (scripts/box_env.sh). Offline pipeline, so no concurrency numbers.
  load  = process start -> pipeline on cuda (includes `import torch/diffusers`; weights pre-downloaded)
Usage: ~/.venv/bin/python bench_diffusers.py --model qwen-turbo --gen ~/gen.py --out ~/bench/results
"""
T_PROC = __import__("time").time()
import argparse, importlib.util, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchlib as B


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=list(B.MODELS))
    ap.add_argument("--gen", default=os.path.expanduser("~/gen.py"))
    ap.add_argument("--prompts", default=os.path.expanduser("~/prompts.jsonl"))
    ap.add_argument("--out", default=os.path.expanduser("~/bench/results"))
    a = ap.parse_args()
    out = os.path.join(a.out, a.model, "diffusers"); os.makedirs(out, exist_ok=True)
    sampler = B.GpuSampler(os.path.join(out, "vram.csv"))
    res = {"model": a.model, "framework": "diffusers", **B.gpu_info()}
    try:
        spec = importlib.util.spec_from_file_location("gen", a.gen); gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        import torch, diffusers, transformers
        res["versions"] = {"diffusers": diffusers.__version__, "transformers": transformers.__version__,
                           "torch": torch.__version__, "torch_cuda": torch.version.cuda, "python": sys.version.split()[0]}
        repo, family, steps, cfg = gen.MODELS[a.model]
        assert repo == B.MODELS[a.model]["repo"] and steps == B.MODELS[a.model]["steps"]
        scenes = B.load_scenes(a.prompts)
        pipe = gen.load_pipe(repo, family); torch.cuda.synchronize()
        res["load_s"] = round(time.time() - T_PROC, 1)

        def one(s, seed, tag):
            t0 = time.time()
            img = gen.render(pipe, family, s["prompt"], s["w"], s["h"], steps, cfg, seed)
            torch.cuda.synchronize(); dt = time.time() - t0
            img.save(os.path.join(out, f"{tag}_{s['id']}_seed{seed}.png"))
            return dt, img.size

        dt, size = one(scenes[0], 11, "cold")
        res["cold_s"] = round(dt, 2); res["size"] = list(size)
        warm = []
        t0 = time.time()
        for s, seed in B.warm_jobs(scenes):
            d, _ = one(s, seed, "warm"); warm.append(round(d, 2))
        res["warm_s"] = warm; res["warm_median_s"] = round(B.median(warm), 2)
        res["c1_img_per_s"] = round(len(warm) / (time.time() - t0), 3)
        res["torch_max_alloc_mib"] = round(torch.cuda.max_memory_allocated() / 2**20)
        res["status"] = "ok"
    except Exception as e:
        import traceback
        res["status"] = "error"; res["error"] = traceback.format_exc()[-3000:]
    res["peak_vram_mib"] = sampler.stop()
    B.write_json(os.path.join(out, "result.json"), res)
    print(res.get("status"), res.get("load_s"), res.get("cold_s"), res.get("warm_median_s"), res["peak_vram_mib"], flush=True)


if __name__ == "__main__":
    main()
