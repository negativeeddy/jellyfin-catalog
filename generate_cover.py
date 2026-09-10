#!/usr/bin/env python3
"""Generate a cover page for the catalog binder.

White background (ink-friendly) with top-rated movie posters placed in an
even, jittered grid and rotated as if dropped from above.

Usage:
    python generate_cover.py                 # one new random layout
    python generate_cover.py --seed 1234     # one reproducible layout
    python generate_cover.py --seed 50 --count 5   # covers with seeds 50,51,52,53,54
    python generate_cover.py --posters 36    # more posters per cover
"""

import argparse
import json
import math
import os
import random
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LIBRARY_PATH = os.path.join(BASE_DIR, "library.json")

DPI = 300
PAGE_W_IN = 8.5
PAGE_H_IN = 11.0
WHITE = (255, 255, 255)
TITLE_COLOR = (20, 20, 20)
SUB_COLOR = (95, 95, 100)
DATE_COLOR = (125, 125, 130)
ACCENT = (217, 70, 239)  # #D946EF magenta accent

SCATTER_COUNT = 30
POSTER_TARGET_H = 2.7  # base display height of each poster, inches
MAX_ANGLE_DEG = 30
MIN_SCALE = 0.85
MAX_SCALE = 1.15
# Vertical space reserved for the title block / date footer
TITLE_RESERVE_IN = 2.0
FOOTER_RESERVE_IN = 1.0
MARGIN_IN = 0.35


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_library():
    with open(LIBRARY_PATH) as f:
        return json.load(f)


def get_font(bold, size):
    if bold:
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    else:
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def load_poster(rec):
    poster_file = rec.get("poster_file")
    if not poster_file:
        return None
    path = os.path.join(BASE_DIR, poster_file)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def build_cover_image(cfg, library, out_png, seed=None, posters=SCATTER_COUNT):
    rng = random.Random(seed)
    movies = library["movies"]
    series = library["tv_series"]

    # Top-rated movies with artwork for the scatter pile
    excluded = set(cfg.get("cover_exclude_ids", []))
    with_poster = []
    for m in movies:
        if m.get("community_rating") and m.get("poster_file") and m.get("id") not in excluded:
            poster = load_poster(m)
            if poster is not None:
                with_poster.append((m, poster))
    with_poster.sort(key=lambda mp: mp[0]["community_rating"], reverse=True)
    featured = with_poster[:posters]
    n = len(featured)

    page_px_w = int(PAGE_W_IN * DPI)
    page_px_h = int(PAGE_H_IN * DPI)
    img = Image.new("RGB", (page_px_w, page_px_h), WHITE)
    draw = ImageDraw.Draw(img)

    title = "MOVIE COLLECTION"
    f_title = get_font(True, int(34 * DPI / 72))
    subtitle = f"{len(movies)} Movies  \u2022  {len(series)} TV Series"
    f_sub = get_font(False, int(15 * DPI / 72))
    generated = f"Generated {datetime.now().strftime('%B %d, %Y')}"
    f_gen = get_font(False, int(11 * DPI / 72))

    bbox = draw.textbbox((0, 0), title, font=f_title)
    tw = bbox[2] - bbox[0]
    tx = (page_px_w - tw) // 2
    ty = int(0.55 * DPI)
    draw.text((tx, ty), title, font=f_title, fill=TITLE_COLOR)
    line_w = int(1.3 * DPI)
    draw.rectangle([(page_px_w - line_w) // 2 - tw // 2, ty + int(0.62 * DPI),
                    (page_px_w - line_w) // 2 + tw // 2, ty + int(0.62 * DPI) + int(4 * DPI / 72)],
                   fill=ACCENT)

    bbox = draw.textbbox((0, 0), subtitle, font=f_sub)
    sw = bbox[2] - bbox[0]
    draw.text(((page_px_w - sw) // 2, ty + int(0.82 * DPI)), subtitle, font=f_sub, fill=SUB_COLOR)

    # Scatter the posters over an even jittered grid <-> "dropped" feel
    margin = int(MARGIN_IN * DPI)
    body_x0, body_x1 = margin, page_px_w - margin
    body_y0 = int(TITLE_RESERVE_IN * DPI)
    body_y1 = page_px_h - int(FOOTER_RESERVE_IN * DPI)

    body_w = body_x1 - body_x0
    body_h = body_y1 - body_y0
    poster_ar = 2.0 / 3.0  # width : height
    cols = max(1, int(math.ceil(math.sqrt(n * body_w / (body_h * poster_ar)))))
    rows = max(1, int(math.ceil(n / cols)))
    cell_w = body_w / cols
    cell_h = body_h / rows

    cells = [(c, r) for r in range(rows) for c in range(cols)]
    rng.shuffle(cells)
    cells = cells[:n]

    featured = list(featured)
    rng.shuffle(featured)

    for (m, poster), (col, row) in zip(featured, cells):
        scale = rng.uniform(MIN_SCALE, MAX_SCALE) * (POSTER_TARGET_H * DPI) / poster.size[1]
        nw = int(poster.size[0] * scale)
        nh = int(poster.size[1] * scale)
        poster = poster.resize((nw, nh), Image.LANCZOS)
        angle = rng.uniform(-MAX_ANGLE_DEG, MAX_ANGLE_DEG)
        poster = poster.rotate(angle, expand=True, resample=Image.BICUBIC)

        pw, ph = poster.size
        # center of the cell plus a bit of inner jitter
        cx = body_x0 + int((col + 0.5 + rng.uniform(-0.35, 0.35)) * cell_w)
        cy = body_y0 + int((row + 0.5 + rng.uniform(-0.35, 0.35)) * cell_h)
        x0, x1 = body_x0 + pw // 2, body_x1 - pw // 2
        y0, y1 = body_y0 + ph // 2, body_y1 - ph // 2
        cx = min(max(cx, x0), x1) if x1 >= x0 else (x0 + x1) // 2
        cy = min(max(cy, y0), y1) if y1 >= y0 else (y0 + y1) // 2
        img.paste(poster, (cx - pw // 2, cy - ph // 2), poster)

    # Footer (drawn last so it always sits on top of the pile)
    bbox = draw.textbbox((0, 0), generated, font=f_gen)
    gw = bbox[2] - bbox[0]
    gy = page_px_h - int(0.62 * DPI)
    draw.text(((page_px_w - gw) // 2, gy), generated, font=f_gen, fill=DATE_COLOR)

    img.save(out_png)
    return out_png


def main():
    parser = argparse.ArgumentParser(description="Generate the binder cover PDF(s)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Base random seed. Omit for a new layout each run.")
    parser.add_argument("--count", type=int, default=1,
                        help="Number of cover variants to generate; seeds "
                             "increment from --seed (default 1)")
    parser.add_argument("--posters", type=int, default=SCATTER_COUNT,
                        help=f"Number of posters to scatter per cover (default {SCATTER_COUNT})")
    args = parser.parse_args()

    base_seed = args.seed if args.seed is not None else random.randint(0, 2 ** 31)

    cfg = load_config()
    library = load_library()
    outdir = os.path.join(BASE_DIR, cfg["output_dir"])
    os.makedirs(outdir, exist_ok=True)
    previewdir = os.path.join(outdir, "previews")
    os.makedirs(previewdir, exist_ok=True)

    for i in range(args.count):
        seed = base_seed + i
        tmp_png = os.path.join(BASE_DIR, f"_tmp_cover_{seed}.png")
        build_cover_image(cfg, library, tmp_png, seed=seed, posters=args.posters)

        img = Image.open(tmp_png)
        pdf_path = os.path.join(outdir, f"cover-{seed}.pdf")
        img.save(pdf_path, resolution=DPI)
        preview = img.copy()
        preview.thumbnail((900, 1200), Image.LANCZOS)
        preview_path = os.path.join(previewdir, f"cover-{seed}.png")
        preview.save(preview_path)
        os.remove(tmp_png)

        print(f"[ok] {os.path.basename(pdf_path)} (seed {seed}, {args.posters} posters)")
        print(f"     preview: {preview_path}")


if __name__ == "__main__":
    main()