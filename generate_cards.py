#!/usr/bin/env python3
"""Generate movie/series cards as PDFs from library.json.

Layout: 3x3 grid of cards on 8.5x11 pages, each card 2.5"x3.5"
to fit 9-pocket trading card binder sleeves.

Pipeline (fast, memory-safe):
  - Compose each page into a single PIL image (300 DPI)
  - Save page PNG to a temp dir (fast filesystem)
  - Stream pages into one multi-page PDF via Pillow (lazy generator)
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LIBRARY_PATH = os.path.join(BASE_DIR, "library.json")

# Physical layout (inches)
CARD_W = 2.5
CARD_H = 3.5
PAGE_W = 8.5
PAGE_H = 11.0
GUTTER_X = 0.1   # white gap between card columns
GUTTER_Y = 0.1   # white gap between card rows
GRID_W = CARD_W * 3 + GUTTER_X * 2   # 7.7"
GRID_H = CARD_H * 3 + GUTTER_Y * 2   # 10.7"
MARGIN_X = (PAGE_W - GRID_W) / 2     # 0.4"
MARGIN_Y = (PAGE_H - GRID_H) / 2     # 0.15"
POSTER_AREA_H = 2.3     # poster image area height on card
DPI = 300


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_library():
    with open(LIBRARY_PATH) as f:
        return json.load(f)


def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i:i + 2], 16) for i in (0, 2, 4))


def get_font(bold, size):
    if bold:
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    else:
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def format_runtime(minutes):
    if minutes is None:
        return None
    if minutes >= 60:
        return f"{minutes // 60}h {minutes % 60:02d}m"
    return f"{minutes}m"


class CardRenderer:
    def __init__(self, cfg, poster_dir):
        self.cfg = cfg
        self.poster_dir = poster_dir
        self.genres = cfg.get("genre_colors", {})

    def genre_color(self, rec):
        for g in rec.get("genres", []):
            if g in self.genres:
                return self.genres[g]
        return self.genres.get("default", "#94A3B8")

    def load_poster(self, rec, target_px):
        poster_file = rec.get("poster_file")
        if not poster_file:
            return None
        if not os.path.isabs(poster_file):
            path = os.path.join(BASE_DIR, poster_file)
        else:
            path = poster_file
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return None
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((target_px, target_px), Image.LANCZOS)
            return img
        except Exception:
            return None

    def render_card(self, rec):
        """Render a single card as an RGB PIL image at DPI resolution."""
        card_px = int(CARD_W * DPI)   # 750
        card_ph = int(CARD_H * DPI)   # 1050
        card = Image.new("RGB", (card_px, card_ph), (255, 255, 255))
        draw = ImageDraw.Draw(card)

        # Genre border (colored band on edges)
        border_px = max(2, int(0.05 * DPI))
        rgb = hex_to_rgb(self.genre_color(rec))
        draw.rectangle([0, 0, card_px - 1, card_ph - 1], outline=rgb, width=border_px)

        # Poster image area: 0.15" inset, height POSTER_AREA_H
        pad = int(0.15 * DPI)
        poster_area = (pad, pad, card_px - pad, pad + int(POSTER_AREA_H * DPI))

        poster_img = self.load_poster(rec, int(CARD_W * DPI))
        if poster_img:
            iw, ih = poster_img.size
            area_w = poster_area[2] - poster_area[0]
            area_h = poster_area[3] - poster_area[1]
            scale = min(area_w / iw, area_h / ih)
            new_w, new_h = int(iw * scale), int(ih * scale)
            img = poster_img.resize((new_w, new_h), Image.LANCZOS)
            x = poster_area[0] + (area_w - new_w) // 2
            y = poster_area[1] + (area_h - new_h) // 2
            card.paste(img, (x, y), img)
        else:
            fill = hex_to_rgb(self.genres.get("default", "#94A3B8"))
            draw.rectangle(poster_area, fill=(*fill, 255))
            f = get_font(True, 16 * DPI // 72)
            placeholder_text = rec.get("name", "No Poster")[:22]
            bbox = draw.textbbox((0, 0), placeholder_text, font=f)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            cx = poster_area[0] + (poster_area[2] - poster_area[0] - tw) // 2
            cy = poster_area[1] + (poster_area[3] - poster_area[1] - th) // 2
            draw.text((cx, cy), placeholder_text, font=f, fill=(50, 50, 50))

        # Metadata text below poster
        text_x = int(0.12 * DPI)
        text_y = poster_area[3] + int(4 * DPI / 72)
        max_text_w = card_px - 2 * text_x
        black = (20, 20, 20)
        gray = (90, 90, 90)

        # Title (bold), possibly with year - prominent
        title = rec.get("name", "Unknown")
        suffix = f" ({rec['year']})" if rec.get("year") else ""
        f_title = get_font(True, 10 * DPI // 72)
        bbox = draw.textbbox((0, 0), title + suffix, font=f_title)
        while (bbox[2] - bbox[0]) > max_text_w and f_title.size > 8 * DPI // 72:
            f_title = get_font(True, f_title.size - 2)
            bbox = draw.textbbox((0, 0), title + suffix, font=f_title)
        draw.text((text_x, text_y), title + suffix, font=f_title, fill=black)
        text_y += f_title.size + int(4 * DPI / 72)

        # Meta line: rating + runtime
        meta_parts = []
        if rec.get("community_rating"):
            meta_parts.append(f"\u2605 {rec['community_rating']:.1f}")
        runtime = format_runtime(rec.get("runtime_minutes"))
        if runtime:
            meta_parts.append(runtime)
        if meta_parts:
            f_meta = get_font(False, int(7 * DPI / 72))
            draw.text((text_x, text_y), "  ".join(meta_parts), font=f_meta, fill=gray)
            text_y += f_meta.size + int(3 * DPI / 72)

        # Second line: rating cert + genres
        second_parts = []
        if rec.get("official_rating"):
            second_parts.append(rec["official_rating"])
        genres = rec.get("genres", [])[:2]
        if genres:
            second_parts.append(", ".join(genres))
        if second_parts:
            s = "  \u2022  ".join(second_parts)
            f_small = get_font(False, int(6.5 * DPI / 72))
            bbox = draw.textbbox((0, 0), s, font=f_small)
            while (bbox[2] - bbox[0]) > max_text_w and f_small.size > 4 * DPI // 72:
                f_small = get_font(False, f_small.size - 2)
                bbox = draw.textbbox((0, 0), s, font=f_small)
            draw.text((text_x, text_y), s, font=f_small, fill=gray)

        return card


def compose_page(renderer, page_records, page_idx, total_pages):
    """Build one 8.5x11 page image with a 3x3 grid of cards."""
    page_px_w = int(PAGE_W * DPI)
    page_px_h = int(PAGE_H * DPI)
    margin_x_px = int(MARGIN_X * DPI)
    margin_y_px = int(MARGIN_Y * DPI)
    card_px = int(CARD_W * DPI)
    card_ph = int(CARD_H * DPI)
    gutter_x_px = int(GUTTER_X * DPI)
    gutter_y_px = int(GUTTER_Y * DPI)

    page_img = Image.new("RGB", (page_px_w, page_px_h), (255, 255, 255))
    for i, rec in enumerate(page_records):
        row, col = i // 3, i % 3
        card = renderer.render_card(rec)
        x = margin_x_px + col * (card_px + gutter_x_px)
        y = margin_y_px + row * (card_ph + gutter_y_px)
        page_img.paste(card, (x, y))

    # Page footer
    draw = ImageDraw.Draw(page_img)
    f_footer = get_font(False, int(7 * DPI / 72))
    footer = f"Page {page_idx + 1} of {total_pages}"
    bbox = draw.textbbox((0, 0), footer, font=f_footer)
    fw = bbox[2] - bbox[0]
    draw.text(((page_px_w - fw) // 2, page_px_h - int(0.22 * DPI)), footer,
              font=f_footer, fill=(150, 150, 150))
    return page_img


def build_pages(cfg, renderer, records, output_path, preview_pages=None, label="cards"):
    """Render records to a multi-page PDF via Pillow (lazy streaming)."""
    total = len(records)
    pages = (total + 8) // 9
    if preview_pages:
        pages = min(pages, preview_pages)

    print(f"[{label}] {total} records -> {pages} pages")

    tmpdir = tempfile.mkdtemp(prefix="jf_cards_")
    png_paths = []
    try:
        for page_idx in range(pages):
            start = page_idx * 9
            page_records = records[start:start + 9]
            page_img = compose_page(renderer, page_records, page_idx, pages)
            p = os.path.join(tmpdir, f"{label}_{page_idx + 1:03d}.png")
            page_img.save(p)
            png_paths.append(p)
            last = page_records[-1]["name"] if page_records else ""
            print(f"  page {page_idx + 1}/{pages} done ({last})")

        # Stream PNGs into a single PDF (skip first; it's the 'first' image)
        def gen():
            for p in png_paths[1:]:
                yield Image.open(p)

        first = Image.open(png_paths[0])
        first.save(output_path, save_all=True, append_images=gen(), resolution=DPI)
        print(f"[ok] Wrote {output_path}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def new_records_since_baseline(library):
    """Return (new_movies, new_series) records added since library.prev.json."""
    prev_path = os.path.join(BASE_DIR, "library.prev.json")
    if not os.path.exists(prev_path):
        print("[ERROR] library.prev.json not found. Run build_all.py (full build) first.",
              file=sys.stderr)
        sys.exit(1)
    with open(prev_path) as f:
        prev = json.load(f)
    prev_ids = set(m["id"] for m in prev.get("movies", []))
    prev_ids.update(s["id"] for s in prev.get("tv_series", []))
    new_movies = [m for m in library["movies"] if m["id"] not in prev_ids]
    new_series = [s for s in library["tv_series"] if s["id"] not in prev_ids]
    return new_movies, new_series


def main():
    parser = argparse.ArgumentParser(description="Generate card PDFs from library.json")
    parser.add_argument("--movies-only", action="store_true")
    parser.add_argument("--tv-only", action="store_true")
    parser.add_argument("--preview", type=int, metavar="N", help="Generate first N pages (test)")
    parser.add_argument("--new-only", action="store_true",
                        help="Only render cards for movies/series added since the last build")
    args = parser.parse_args()

    cfg = load_config()
    library = load_library()
    renderer = CardRenderer(cfg, os.path.join(BASE_DIR, cfg.get("poster_dir", "posters")))

    outdir = os.path.join(BASE_DIR, cfg["output_dir"])
    os.makedirs(outdir, exist_ok=True)

    if args.new_only:
        new_movies, new_series = new_records_since_baseline(library)
        total_new = len(new_movies) + len(new_series)
        if total_new == 0:
            print("[ok] No new movies/series since last build.")
            return
        print(f"[info] {len(new_movies)} new movie(s), {len(new_series)} new series(s):")
        for m in new_movies:
            print(f"      - {m['name']} ({m['year']})")
        for s in new_series:
            print(f"      - [TV] {s['name']} ({s['year']})")
        records = sorted(new_movies, key=lambda m: m["name"].lower()) + \
                  sorted(new_series, key=lambda s: s["name"].lower())
        build_pages(cfg, renderer, records, os.path.join(outdir, "new_cards.pdf"),
                    label="new_cards")
        return

    do_movies = not args.tv_only
    do_tv = not args.movies_only

    if do_movies:
        movies = sorted(library["movies"], key=lambda m: m["name"].lower())
        build_pages(cfg, renderer, movies, os.path.join(outdir, "movies.pdf"),
                    preview_pages=args.preview, label="movies")

    if do_tv:
        series = sorted(library["tv_series"], key=lambda m: m["name"].lower())
        build_pages(cfg, renderer, series, os.path.join(outdir, "tv_series.pdf"),
                    preview_pages=args.preview, label="tv_series")


if __name__ == "__main__":
    main()