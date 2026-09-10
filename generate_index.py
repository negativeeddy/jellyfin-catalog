#!/usr/bin/env python3
"""Generate genre and title index PDFs.

- Alphabetical lists, NO page numbers (they'd drift as movies are added).
- Row-based two-column layout: entries pair up per row
  (left cell, right cell) so both columns descend together.
- Each section header is a FULL-WIDTH divider. The previous section's
  entries always fill both columns above the divider (no empty right column).
- Page breaks happen at row boundaries only.
"""

import argparse
import json
import os
from collections import defaultdict

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LIBRARY_PATH = os.path.join(BASE_DIR, "library.json")

PAGE_W, PAGE_H = letter  # points, 612x792
MARGIN = 54  # 0.75"
TOP = PAGE_H - MARGIN
BOTTOM = MARGIN

TITLE_FONT = "Helvetica-Bold"
BODY_FONT = "Helvetica"

COL_GAP = 24  # 0.33"
COL_W = (PAGE_W - 2 * MARGIN - COL_GAP) / 2   # 240pt
COL2_X = MARGIN + COL_W + COL_GAP

ENTRY_LINE_H = 13
HEADER_H = 26
SECTION_GAP = 8  # extra whitespace between previous section's entries and a divider
FOOTER_KEEP = 22


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_library():
    with open(LIBRARY_PATH) as f:
        return json.load(f)


class IndexWriter:
    def __init__(self, output_path, title):
        self.c = canvas.Canvas(output_path, pagesize=letter)
        self.c.setTitle(title)
        self.row_y = TOP
        self.page_num = 1
        self.footer()

    def footer(self):
        self.c.setFont(BODY_FONT, 7)
        self.c.setFillColor(HexColor("#999999"))
        self.c.drawCentredString(PAGE_W / 2, 0.14 * 72, f"Page {self.page_num}")

    def new_page(self):
        self.c.showPage()
        self.page_num += 1
        self.row_y = TOP
        self.footer()

    def ensure(self, pts):
        """Start a fresh page if `pts` points don't fit below the current row."""
        if self.row_y - pts < BOTTOM + FOOTER_KEEP:
            self.new_page()

    def fit(self, pts):
        return self.row_y - pts >= BOTTOM + FOOTER_KEEP

    def draw_header(self, header, color):
        """Full-width section divider on its own row."""
        # Keep at least 2 entry rows below the divider
        while not self.fit(HEADER_H + 2 * ENTRY_LINE_H + SECTION_GAP):
            self.new_page()
        self.row_y -= SECTION_GAP
        y = self.row_y
        self.c.setFont(TITLE_FONT, 12)
        self.c.setFillColor(HexColor(color))
        self.c.drawString(MARGIN, y - 2, header)
        self.c.setStrokeColor(HexColor("#bbbbbb"))
        self.c.setLineWidth(0.8)
        self.c.line(MARGIN, y - 14, PAGE_W - MARGIN, y - 14)
        self.row_y -= HEADER_H

    def draw_cont_header(self, header, color):
        """Lighter '(cont)' divider for the top of a follow-on page mid-section."""
        import re
        clean = re.sub(r"\s*\(\d+\)\s*$", "", header)
        self.row_y -= SECTION_GAP
        y = self.row_y
        self.c.setFont("Helvetica-BoldOblique", 10)
        self.c.setFillColor(HexColor(color))
        self.c.drawString(MARGIN, y - 2, f"{clean} (cont)")
        self.c.setStrokeColor(HexColor("#dddddd"))
        self.c.setLineWidth(0.6)
        self.c.line(MARGIN, y - 12, PAGE_W - MARGIN, y - 12)
        self.row_y -= HEADER_H

    def draw_entry(self, name, year, x):
        label = f"{name} ({year})" if year else name
        lw = stringWidth(label, BODY_FONT, 9)
        if lw > COL_W:
            while lw > COL_W and len(label) > 4:
                label = label[:-1]
                lw = stringWidth(label, BODY_FONT, 9)
            label = label[:-1] + "\u2026"
        self.c.setFont(BODY_FONT, 9)
        self.c.setFillColor(HexColor("#1a1a1a"))
        self.c.drawString(x, self.row_y, label)

    def draw_section(self, header, color, entries):
        """Full-width header, then entries in column-major order.

        Alphabetical order flows DOWN the left column first, then DOWN the
        right column (first half of the section on the left, second half on
        the right). Crosses pages mid-section; each follow-on page gets a
        '(cont)' header.
        """
        self.draw_header(header, color)
        n = len(entries)
        if n == 0:
            return
        mid = (n + 1) // 2  # left column gets entries[0:mid], right gets entries[mid:]
        for k in range(mid):
            if not self.fit(ENTRY_LINE_H + 2):
                self.new_page()
                self.draw_cont_header(header, color)
            self.draw_entry(entries[k][0], entries[k][1], MARGIN)
            right_idx = mid + k
            if right_idx < n:
                self.draw_entry(entries[right_idx][0], entries[right_idx][1], COL2_X)
            self.row_y -= ENTRY_LINE_H

    def finish(self):
        self.footer()
        self.c.save()
        return self.page_num


def build_title_index(cfg, movies, out_path):
    sorted_movies = sorted(movies, key=lambda m: m["name"].lower())

    groups = defaultdict(list)
    for m in sorted_movies:
        name = m["name"]
        first = name[0].upper() if name and name[0].isalpha() else "#"
        groups[first].append(m)

    w = IndexWriter(out_path, "Title Index")
    for letter in sorted(groups.keys(), key=lambda L: (L == "#", L)):
        entries = sorted(((m["name"], m["year"]) for m in groups[letter]),
                         key=lambda e: e[0].lower())
        w.draw_section(f"{letter}", "#1a1a1a", entries)
    return w.finish()


def build_genre_index(cfg, movies, series, out_path):
    sorted_movies = sorted(movies, key=lambda m: m["name"].lower())

    genre_movies = defaultdict(list)
    for m in movies:
        for g in m.get("genres", []):
            genre_movies[g].append(m)

    genre_order = sorted(genre_movies.keys(), key=lambda g: (-len(genre_movies[g]), g))

    colors = cfg.get("genre_colors", {})
    w = IndexWriter(out_path, "Genre Index")
    for g in genre_order:
        color = colors.get(g, colors.get("default", "#94A3B8"))
        entries = sorted(((m["name"], m["year"]) for m in genre_movies[g]),
                         key=lambda e: e[0].lower())
        w.draw_section(f"{g} ({len(entries)})", color, entries)
    return w.finish()


def main():
    parser = argparse.ArgumentParser(description="Generate index PDFs")
    parser.add_argument("--genre-only", action="store_true")
    parser.add_argument("--title-only", action="store_true")
    parser.add_argument("--preview", type=int, metavar="N", help="Only include first N movies")
    args = parser.parse_args()

    cfg = load_config()
    library = load_library()
    movies = library["movies"]
    series = library["tv_series"]

    outdir = os.path.join(BASE_DIR, cfg["output_dir"])
    os.makedirs(outdir, exist_ok=True)

    if args.preview:
        movies = movies[:args.preview]

    do_title = not args.genre_only
    do_genre = not args.title_only

    if do_title:
        pages = build_title_index(cfg, movies, os.path.join(outdir, "title_index.pdf"))
        print(f"[ok] title_index.pdf ({pages} pages)")

    if do_genre:
        if args.preview:
            series = []
        pages = build_genre_index(cfg, movies, series, os.path.join(outdir, "genre_index.pdf"))
        print(f"[ok] genre_index.pdf ({pages} pages)")


if __name__ == "__main__":
    main()