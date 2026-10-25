#!/usr/bin/env python3
"""B — model inpaint repaint of garbled text regions (RUN ON GPU BOX).

Tests whether masking just the broken-text region and re-running the SAME model
family as an inpaint pass lets the model render the correct text in place, with
the surface texture/lighting regenerated (which a flat Pillow overlay cannot do).

Two cases Liang flagged (residual errors even in the full-tier winners):
  Lancome : Z-full seed33 — LANCÔME correct but on-bottle body copy is gibberish.
            Inpaint the two garbled blocks on the bottles with ZImageInpaint.
  Hainan  : Qwen-full seed33 — wooden tag reads 分俞十足 (should be 分量十足).
            Inpaint just that tag line with QwenImageInpaint.

Masks are measured source-pixel boxes (verified on a 50px fine grid).
Output: ~/out_b/<name>_inpaint_s<seed>.png
"""
import torch, os, argparse
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.expanduser("~/out_b")
os.makedirs(OUT, exist_ok=True)


def make_mask(size, boxes, feather=12):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    for b in boxes:
        d.rectangle(b, fill=255)
    return m.filter(ImageFilter.GaussianBlur(feather))


def run_z(src, boxes, prompt, seeds, tag):
    from diffusers import ZImageInpaintPipeline
    pipe = ZImageInpaintPipeline.from_pretrained(
        "Tongyi-MAI/Z-Image", torch_dtype=torch.bfloat16).to("cuda")
    img = Image.open(src).convert("RGB")
    mask = make_mask(img.size, boxes)
    mask.save(f"{OUT}/{tag}_mask.png")
    for s in seeds:
        g = torch.Generator(device="cuda").manual_seed(s)
        out = pipe(prompt=prompt, image=img, mask_image=mask,
                   width=img.width, height=img.height,
                   num_inference_steps=30, guidance_scale=4.0,
                   strength=0.95, generator=g).images[0]
        p = f"{OUT}/{tag}_inpaint_s{s}.png"
        out.save(p); print("saved", p, flush=True)


def run_qwen(src, boxes, prompt, seeds, tag):
    from diffusers import QwenImageInpaintPipeline
    pipe = QwenImageInpaintPipeline.from_pretrained(
        "Qwen/Qwen-Image-2.1", torch_dtype=torch.bfloat16).to("cuda")
    img = Image.open(src).convert("RGB")
    mask = make_mask(img.size, boxes)
    mask.save(f"{OUT}/{tag}_mask.png")
    for s in seeds:
        g = torch.Generator(device="cuda").manual_seed(s)
        out = pipe(prompt=prompt, negative_prompt=" ", image=img, mask_image=mask,
                   width=img.width, height=img.height,
                   num_inference_steps=40, true_cfg_scale=4.0,
                   strength=0.9, generator=g).images[0]
        p = f"{OUT}/{tag}_inpaint_s{s}.png"
        out.save(p); print("saved", p, flush=True)


SCENES = {
    # Z-full Lancome — garbled English body copy on both bottles.
    "lancome": dict(
        kind="z",
        src=os.path.expanduser("~/lancome_src.png"),
        boxes=[(225, 645, 375, 790), (505, 740, 655, 855)],
        prompt=("luxury cosmetic product photography, two Lancome bottles, "
                "crisp clean readable embossed text 'LANCÔME ABSOLUE' with fine "
                "serif product description lines, elegant gold packaging, "
                "sharp legible Latin typography, high detail"),
    ),
    # Qwen-full hainan — wooden tag line 分俞 -> 分量.
    "hainan": dict(
        kind="qwen",
        src=os.path.expanduser("~/hainan_src.png"),
        boxes=[(770, 300, 895, 350)],
        prompt=("a wooden hanging menu tag with clean black Chinese calligraphy "
                "text '分量十足', sharp legible Chinese characters on aged paper, "
                "food poster, high detail"),
    ),
}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, choices=list(SCENES))
    ap.add_argument("--seeds", default="11,22,33")
    a = ap.parse_args()
    sc = SCENES[a.scene]
    seeds = [int(x) for x in a.seeds.split(",")]
    print(f"=== inpaint {a.scene} ({sc['kind']}) seeds={seeds} ===", flush=True)
    if sc["kind"] == "z":
        run_z(sc["src"], sc["boxes"], sc["prompt"], seeds, a.scene)
    else:
        run_qwen(sc["src"], sc["boxes"], sc["prompt"], seeds, a.scene)
    print("DONE", a.scene, flush=True)
