#!/usr/bin/env python3
"""LOCAL: turn pulled raw results into repo assets + a markdown results table.

Input : <raw>/<model>/<framework>/{result.json, warm_*.png, cold_*.png}  (rsync'd from ~/bench/results)
Output: assets/bench/<model>/<framework>/<scene>_seed<n>.jpg   (longest side 512px, JPEG q85)
        assets/bench/<model>/sidebyside.jpg                       (rows = scenes @ seed 11, cols = frameworks)
        assets/bench/results.json                                 (all result.json, error logs trimmed)
        prints markdown tables to stdout
Usage : python scripts/bench/collect.py --raw ~/.ssh/oss-bench/raw --assets assets/bench
Needs : Pillow.
"""
import argparse, glob, json, os
from PIL import Image, ImageDraw, ImageFont

FWS = ["diffusers", "sglang", "vllm-omni"]
MODELS = ["qwen-turbo", "z-turbo"]
SCENES = ["food_sandwich_bread", "cosmetic_lancome_essence", "portrait_bird"]


def thumb(src, dst, side=512):
    im = Image.open(src).convert("RGB"); im.thumbnail((side, side), Image.LANCZOS)
    os.makedirs(os.path.dirname(dst), exist_ok=True); im.save(dst, "JPEG", quality=85); return im


def font(sz):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def sidebyside(model, assets, results):
    cols = [f for f in FWS if os.path.exists(os.path.join(assets, model, f, f"{SCENES[0]}_seed11.jpg"))]
    if not cols:
        return None
    w, h, pad, head = 372, 512, 8, 40
    W = len(cols) * (w + pad) + pad; H = head + len(SCENES) * (h + pad) + pad
    canvas = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(canvas); f = font(20)
    for ci, fw in enumerate(cols):
        r = results.get((model, fw), {})
        label = f"{fw}  {r.get('warm_median_s', '?')} s/img"
        d.text((pad + ci * (w + pad) + 6, 10), label, fill="black", font=f)
        for ri, sc in enumerate(SCENES):
            p = os.path.join(assets, model, fw, f"{sc}_seed11.jpg")
            if os.path.exists(p):
                im = Image.open(p); im.thumbnail((w, h))
                canvas.paste(im, (pad + ci * (w + pad), head + ri * (h + pad)))
    out = os.path.join(assets, model, "sidebyside.jpg"); canvas.save(out, "JPEG", quality=85)
    return out


def fmt(v, suf=""):
    return "—" if v is None else f"{v}{suf}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--assets", default="assets/bench")
    a = ap.parse_args()
    results = {}
    for rj in glob.glob(os.path.join(a.raw, "*", "*", "result.json")):
        r = json.load(open(rj)); results[(r["model"], r["framework"])] = r
        src_dir = os.path.dirname(rj)
        for png in glob.glob(os.path.join(src_dir, "warm_*.png")):
            name = os.path.basename(png)[len("warm_"):-4]
            thumb(png, os.path.join(a.assets, r["model"], r["framework"], name + ".jpg"))
    for m in MODELS:
        print("sidebyside:", sidebyside(m, a.assets, results))
    slim = []
    for k in sorted(results):
        r = dict(results[k])
        for key in ("error", "server_log_tail"):
            if key in r and r[key]:
                r[key] = r[key][-2500:]
        r.pop("models_endpoint", None)
        slim.append(r)
    json.dump(slim, open(os.path.join(a.assets, "results.json"), "w"), ensure_ascii=False, indent=2)

    print("\n| 模型 | 框架 | 状态 | 加载 (s) | 冷启动首图 (s) | 热态 s/img (中位数, n=6) | 吞吐 c=1 (img/s) | 吞吐 c=4 (img/s) | 峰值显存 (GiB) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for m in MODELS:
        for fw in FWS:
            r = results.get((m, fw))
            if not r:
                print(f"| {m} | {fw} | 未运行 | | | | | | |"); continue
            vram = round(r["peak_vram_mib"] / 1024, 1) if r.get("peak_vram_mib") else None
            c4 = r.get("c4_img_per_s") if fw != "diffusers" else "n/a"
            print(f"| {m} | {fw} | {r['status']} | {fmt(r.get('load_s'))} | {fmt(r.get('cold_s'))} | "
                  f"{fmt(r.get('warm_median_s'))} | {fmt(r.get('c1_img_per_s'))} | {fmt(c4)} | {fmt(vram)} |")
    print("\nversions:")
    for k in sorted(results):
        print(k, json.dumps(results[k].get("versions"), ensure_ascii=False), results[k].get("driver_cuda"), results[k].get("size"))


if __name__ == "__main__":
    main()
