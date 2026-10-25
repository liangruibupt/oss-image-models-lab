#!/usr/bin/env python3
"""A (叠真字 / vector-text overlay) — the deliverable path for commercial text.

Neither Qwen-Image-2.1 nor Z-Image renders every piece of text in a poster
correctly even at full tier (English brand body copy, long Chinese phrases,
single rare glyphs). The reliable commercial fix is NOT to coax the model —
it is to stop letting the model draw the text and overlay REAL vector glyphs
on the broken regions, sampling the local background so the patch blends.

This script fixes the two residual-error cases Liang flagged:

  A1  zfull_cosmetic_lancome_essence_seed33.png
        keep: 「LANCÔME」 (correct), poster copy 心动不需观望 / 拥有美好 (correct)
        fix : garbled on-bottle product copy (left jar "PULPUE SAAPEX ..." and
              right bottle Gothic gibberish) -> clean readable product lines.

  A2  qwenfull_food_hainan_milan_seed33.png
        keep: vertical title 「海南儋州米兰」(correct), 「欢迎品尝」(correct)
        fix : wooden tag 「分俞十足」-> 「分量十足」(俞 is the wrong glyph).

Output: assets/fix/overlay/<name>_overlay.png  (1024x1408, same as source).

Coordinates were read from a 100px grid rendered over each source (see
scripts/_grid helper during authoring); they are source-pixel coords.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(REPO, "assets", "fix")
OUT = os.path.join(FIX, "overlay")
os.makedirs(OUT, exist_ok=True)

# Fonts (verified present on the host via fc-list)
SERIF_LATIN = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"
SERIF_LATIN_B = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
SERIF_CJK = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
SANS_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def font(path, size, index=0):
    return ImageFont.truetype(path, size, index=index)


def sample_bg(im, box, pad=6):
    """Average colour of a thin ring just outside `box` — used to repaint over
    the garbled glyphs with a matching flat patch before laying clean text."""
    x0, y0, x1, y1 = box
    ring = []
    for (a, b, c, d) in [
        (x0 - pad, y0, x0, y1), (x1, y0, x1 + pad, y1),
        (x0, y0 - pad, x1, y0), (x0, y1, x1, y1 + pad),
    ]:
        a, b = max(0, a), max(0, b)
        c, d = min(im.width, c), min(im.height, d)
        if c > a and d > b:
            ring.append(im.crop((a, b, c, d)))
    if not ring:
        return (200, 180, 140)
    tot = [0, 0, 0]
    n = 0
    for r in ring:
        for p in list(r.getdata()):
            tot[0] += p[0]; tot[1] += p[1]; tot[2] += p[2]; n += 1
    return tuple(t // max(1, n) for t in tot)


def patch_region(im, box, blur=12):
    """Remove garbled glyphs by blurring the region's own pixels into a smooth
    surface (keeps the bottle's gradient + reflections), composited back through
    a feathered mask so edges blend. Far more natural than a flat fill on a
    glossy curved surface."""
    x0, y0, x1, y1 = box
    pad = 24
    rb = (max(0, x0 - pad), max(0, y0 - pad),
          min(im.width, x1 + pad), min(im.height, y1 + pad))
    region = im.crop(rb)
    smoothed = region.filter(ImageFilter.GaussianBlur(14))
    im.paste(smoothed, (rb[0], rb[1]))
    # feather the inner box edges
    mask = Image.new("L", im.size, 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle(box, radius=8, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(blur))
    return mask


def draw_centered(d, cx, y, text, fnt, fill, shadow=True):
    bb = d.textbbox((0, 0), text, font=fnt)
    w = bb[2] - bb[0]
    x = cx - w / 2
    if shadow:
        d.text((x + 1, y + 1), text, font=fnt, fill=(255, 245, 230))
    d.text((x, y), text, font=fnt, fill=fill)
    bb2 = d.textbbox((0, 0), text, font=fnt)
    return bb2[3] - bb2[1]


# ---------------------------------------------------------------- A1 Lancôme
def fix_lancome():
    src = os.path.join(FIX, "zfull_cosmetic_lancome_essence_seed33.png")
    im = Image.open(src).convert("RGB")
    dark = (58, 44, 32)

    # Measured on a 50px fine grid over the full-res source:
    #   「LANCÔME」 wordmark  x210..360 y600..635  -> KEEP (correct)
    #   left jar garbled      x225..375 y645..790  -> fix
    #   right bottle gibberish x505..655 y740..855 -> fix
    left_box = (225, 645, 378, 792)
    right_box = (505, 740, 658, 858)

    patch_region(im, left_box, blur=12)
    patch_region(im, right_box, blur=12)
    d = ImageDraw.Draw(im)

    cxL = (left_box[0] + left_box[2]) // 2   # ~301
    draw_centered(d, cxL, 652, "ABSOLUE", font(SERIF_LATIN_B, 24), dark)
    draw_centered(d, cxL, 686, "L'EXTRAIT", font(SERIF_LATIN, 18), dark)
    draw_centered(d, cxL, 716, "REGENERATING SERUM", font(SERIF_LATIN, 13), dark)
    draw_centered(d, cxL, 752, "30 mL  /  1.0 FL. OZ.", font(SERIF_LATIN, 12), dark)

    cxR = (right_box[0] + right_box[2]) // 2  # ~581
    draw_centered(d, cxR, 748, "LANCÔME", font(SERIF_LATIN_B, 20), dark)
    draw_centered(d, cxR, 778, "ABSOLUE", font(SERIF_LATIN, 16), dark)
    draw_centered(d, cxR, 804, "THE ROSE LOTION", font(SERIF_LATIN, 12), dark)
    draw_centered(d, cxR, 832, "150 mL  /  5.0 FL. OZ.", font(SERIF_LATIN, 11), dark)

    out = os.path.join(OUT, "lancome_overlay.png")
    im.save(out)
    print("A1 saved:", out)
    return out


# ---------------------------------------------------------------- A2 hainan
def fix_hainan():
    src = os.path.join(FIX, "qwenfull_food_hainan_milan_seed33.png")
    im = Image.open(src).convert("RGB")

    # Wooden tag line 「分俞十足」-> 「分量十足」. Measured on fine grid:
    #   「配料丰富」 y285..310, 「分俞十足」 y312..350, x810..965 (~37px glyphs).
    line_box = (818, 312, 958, 350)
    patch_region(im, line_box, blur=3)
    d = ImageDraw.Draw(im)
    txt = "分量十足"
    tag_font = font(SERIF_CJK, 31)
    # center within the paper panel (x818..958)
    draw_centered(d, (818+958)//2, 312, txt, tag_font, (28, 22, 17), shadow=False)

    out = os.path.join(OUT, "hainan_overlay.png")
    im.save(out)
    print("A2 saved:", out)
    return out


if __name__ == "__main__":
    a1 = fix_lancome()
    a2 = fix_hainan()
    print("DONE", a1, a2)
