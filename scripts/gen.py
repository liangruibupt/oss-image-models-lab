#!/usr/bin/env python3
"""Canonical image generator — Diffusers path (verified). See docs/RUNBOOK.md.

RUN ON THE GPU INSTANCE. Reads scenes from prompts.jsonl and renders one image
per seed into an output dir. Supports both models, turbo and full.

Models / params are locked to the RUNBOOK-verified values:
  qwen-turbo : Qwen/Qwen-Image-2.1-Turbo    8 steps  true_cfg_scale=1.0
  qwen-full  : Qwen/Qwen-Image-2.1         40 steps  true_cfg_scale=4.0
  z-turbo    : Tongyi-MAI/Z-Image-Turbo      8 steps  guidance_scale=1.0
  z-full     : Tongyi-MAI/Z-Image           30 steps  guidance_scale=4.0   (NOT Z-Image-Base — 404)

Usage:
  python scripts/gen.py --model qwen-turbo --prompts prompts.jsonl --out out/
  python scripts/gen.py --model z-full --only food_hainan_milan --seeds 101,202,303 --out fix/
"""
import torch, json, os, time, argparse

MODELS = {
    "qwen-turbo": ("Qwen/Qwen-Image-2.1-Turbo", "qwen", 8, 1.0),
    "qwen-full":  ("Qwen/Qwen-Image-2.1",       "qwen", 40, 4.0),
    "z-turbo":    ("Tongyi-MAI/Z-Image-Turbo",  "z", 8, 1.0),
    "z-full":     ("Tongyi-MAI/Z-Image",        "z", 30, 4.0),
}


def load_pipe(repo, family):
    if family == "qwen":
        from diffusers import QwenImage21Pipeline
        return QwenImage21Pipeline.from_pretrained(repo, torch_dtype=torch.bfloat16).to("cuda")
    from diffusers import ZImagePipeline
    return ZImagePipeline.from_pretrained(repo, torch_dtype=torch.bfloat16).to("cuda")


def render(pipe, family, prompt, w, h, steps, cfg, seed):
    g = torch.Generator(device="cuda").manual_seed(seed)
    if family == "qwen":
        return pipe(prompt=prompt, negative_prompt=" ", width=w, height=h,
                    num_inference_steps=steps, true_cfg_scale=cfg, generator=g).images[0]
    return pipe(prompt=prompt, width=w, height=h,
                num_inference_steps=steps, guidance_scale=cfg, generator=g).images[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=list(MODELS))
    ap.add_argument("--prompts", default=os.path.expanduser("~/prompts.jsonl"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="", help="comma-separated scene ids")
    ap.add_argument("--seeds", default="", help="comma-separated ints; overrides prompts.jsonl seeds")
    ap.add_argument("--prefix", default="", help="filename prefix (default = model key)")
    a = ap.parse_args()

    repo, family, steps, cfg = MODELS[a.model]
    os.makedirs(a.out, exist_ok=True)
    only = {s.strip() for s in a.only.split(",") if s.strip()}
    seed_override = [int(s) for s in a.seeds.split(",") if s.strip()]
    prefix = a.prefix or a.model.replace("-", "")

    recs = [json.loads(l) for l in open(a.prompts) if l.strip() and not l.startswith("#")]
    print(f"loading {repo} ...", flush=True)
    pipe = load_pipe(repo, family)

    rep = []
    for r in recs:
        if only and r["id"] not in only:
            continue
        w = r.get("size", {}).get("w", 1024); h = r.get("size", {}).get("h", 1408)
        seeds = seed_override or r.get("seeds", [11, 22, 33, 44])
        print(f"=== {r['id']} {w}x{h} seeds={seeds} ===", flush=True)
        for s in seeds:
            t0 = time.time()
            img = render(pipe, family, r["prompt"], w, h, steps, cfg, s)
            p = os.path.join(a.out, f"{prefix}_{r['id']}_seed{s}.png")
            img.save(p)
            dt = round(time.time() - t0, 1); rep.append({"id": r["id"], "seed": s, "sec": dt})
            print("saved", p, dt, flush=True)
    json.dump(rep, open(os.path.join(a.out, f"report_{prefix}.json"), "w"), ensure_ascii=False, indent=2)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
