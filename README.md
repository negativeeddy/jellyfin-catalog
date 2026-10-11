# Jellyfin Catalog

Print a physical binder catalog of your Jellyfin movie library. Every movie and
TV series gets a **2.5" x 3.5" card**, laid out 3x3 per letter page to fit
standard 9-pocket trading-card binder sleeves — so you can flip through your
whole collection without turning on a screen.

## Features

- One printable card per movie and per TV series, alphabetically ordered
- Cards are color-coded by genre border (`genre_colors` in `config.json`)
- **Indexes are alphabetical only and carry no page numbers** — new movies
  never make existing references go stale, so the indexes stay correct forever
- Cover page is a fresh collage of your top-rated movies, regenerable endlessly
- Update workflow re-prints only the new cards; existing pages are untouched

## Requirements

- Python 3.8+ with `pip3`
- A Jellyfin server and an API key (Dashboard → Advanced → API Keys)
- For the physical build: a printer (65lb cover cardstock max), 9-pocket sleeve
  pages, a 2-3" D-ring binder, and a guillotine paper trimmer

## Setup

```bash
# 1. Install dependencies
pip3 install -r requirements.txt

# 2. Create your config from the template (contains your API key - not committed)
cp config.example.json config.json
#    then edit config.json: set server_url and api_key

# 3. Full build: fetch library + generate all PDFs (~4 min the first time)
python3 build_all.py
```

The build output lands in `output/`. Open the PDFs, glance at
`output/previews/` to confirm layout before printing anything.

## config.json

| Key | What it does |
|---|---|
| `server_url` | Jellyfin base URL, e.g. `http://10.0.0.2:8096`. Use the LAN IP — the hostname often won't resolve |
| `api_key` | Jellyfin API key (keep this file out of git; the example file has placeholders) |
| `poster_width` | Poster resolution pulled from Jellyfin (px wide; 500 is fine) |
| `output_dir` / `poster_dir` | Where PDFs and poster images go |
| `card_*`, `page_*`, `dpi` | Card/page geometry (2.5x3.5 cards in a 3x3 grid at 300 DPI) |
| `genre_colors` | Border color per genre; unknown genres fall back to `default` |
| `cover_exclude_ids` | Movie IDs to keep off the cover collage (e.g. limited TV-series adaptations); find IDs in `library.json` |

## How the build works

```
fetch_library.py ──> library.json + posters/   (Jellyfin API → metadata + art)
generate_cards.py ──> movies.pdf, tv_series.pdf  (the 3x3 card pages)
generate_index.py ──> title_index.pdf, genre_index.pdf  (text indexes)
generate_cover.py ──> cover-<seed>.pdf          (cover collage, seeded)
build_all.py          runs all of the above in order
```

- `library.json` is a cache (`source of truth`) — posters already downloaded are
  skipped on re-runs; use `--force` to re-fetch.
- Before each fetch, `build_all.py` snapshots the current library to
  `library.prev.json` and then generates `output/new_cards_YYYYMMDD_NN.pdf`
  (date-stamped, per-day run number) containing only the newly added movies
  (see [Updating](#updating-the-catalog)).

## Output files (current library size)

| File | Contents | Sheets |
|---|---|---|
| `cover-<seed>.pdf` | Cover collage, top-rated movies | 1 |
| `movies.pdf` | Movie cards, alphabetical | 90 |
| `tv_series.pdf` | Series cards, alphabetical | 3 |
| `title_index.pdf` | A-Z title index | 10 |
| `genre_index.pdf` | Genre cross-reference | 23 |

Printable page counts scale with your library; the pipeline never needs editing
to handle more movies.

## Command reference

```bash
# Fetch
python3 fetch_library.py                      # fetch what's missing (resumes)
python3 fetch_library.py --force              # re-fetch everything
python3 fetch_library.py --movies-only        # --tv-only: fetch one kind

# Cards
python3 generate_cards.py                     # movies.pdf + tv_series.pdf
python3 generate_cards.py --preview 2         # first 2 pages (sanity check)
python3 generate_cards.py --new-only          # only new_cards_* delta PDF
python3 generate_cards.py --movies-only       # --tv-only: cards for one kind

# Indexes
python3 generate_index.py                     # title + genre indexes
python3 generate_index.py --genre-only        # --title-only: one index
python3 generate_index.py --preview 20        # first 20 movies (iteration)

# Cover
python3 generate_cover.py                           # fresh random layout
python3 generate_cover.py --seed 42                 # reproducible layout
python3 generate_cover.py --count 5 --seed 50       # seeds 50..54 → 5 covers
python3 generate_cover.py --posters 36              # more posters per cover

# Whole pipeline
python3 build_all.py                          # fetch + everything
python3 build_all.py --skip-fetch             # reuse library.json
python3 build_all.py --preview 2              # quick iteration build
```

## The cover generator

The cover is a white, ink-friendly collage of top-rated movie posters scattered
and rotated as if dropped from above. Useful options:

- **Randomize**: run without `--seed` for a brand-new layout each time.
- **Batch**: `--count N` generates N covers with incremental seeds
  (`--seed 50 --count 5` → seeds 50–54). Nothing is overwritten — every cover
  keeps its seed in the filename — so you can generate a pile of candidates and
  pick your favorite.
- **Density**: `--posters N` controls how many posters fill the page (default 30).
- **Exclusions**: add movie IDs to `cover_exclude_ids` in `config.json` to keep
  them off the cover.
- A small preview PNG is saved next to each cover for quick browsing without
  opening the PDF.

## Printing

Printed on **Letter (8.5 x 11)**, at **100% / actual size** (never "fit to
page"). Card pages and indexes go on **65lb cover cardstock (176 gsm) max**
fed through the manual/bypass tray; your laser printer's cardstock/heavyweight
setting helps avoid jams.

Print order (print in page order):

```
cover-<seed>.pdf   (1 sheet)
movies.pdf         (90 sheets)
tv_series.pdf      (3 sheets)
title_index.pdf    (10 sheets)
genre_index.pdf    (23 sheets)
```

### Materials

| Item | Qty | Notes |
|---|---|---|
| 9-pocket binder pages | 90+ | ~93 for a full library, *or half that* if you load two cards back-to-back in each pocket (both fronts stay visible) |
| 65lb cover cardstock, Letter | ~125 sheets | everything prints on this |
| 2-3" D-ring binder | 1 | |
| Tab dividers | 1 pack | one per section (Movies, Series, Title index, Genre index) |
| Guillotine paper trimmer | 1 | scissors don't stay square |

### Cutting the cards

1. Cut each sheet into 3 strips along the card-row boundaries, then cut each
   strip into 3 cards (4 cuts per sheet).
2. Stack at most ~5 sheets when cutting so the stack stays square.
3. Go in batches — ~360 cuts total for a full library.

### Assembly order

Cover → movie cards (A→Z) → series cards → title index → genre index, with a
tab divider between sections, all into the binder.

## Updating the catalog

When your library changes (new movies added, ratings updated):

```bash
python3 build_all.py
```

This re-fetches, rebuilds the pages, and produces a delta sheet
(`new_cards_YYYYMMDD_NN.pdf`) containing only the newly added movies. Print the
new cards, cut them, and slot them into their alphabetical positions — you never
reprint pages that have shifted. The indexes stay accurate without any
page-number updates. Cover aficionados can generate a fresh cover with
`python3 generate_cover.py` and pick the seed they like best.

## Project layout

```
jellyfin-catalog/
├── build_all.py            # master script: fetch → cards → index → cover → delta
├── fetch_library.py        # Jellyfin API → library.json + posters/
├── generate_cards.py       # library.json → movies.pdf, tv_series.pdf, new_cards_*.pdf
├── generate_index.py       # library.json → title_index.pdf, genre_index.pdf
├── generate_cover.py       # library.json → cover-<seed>.pdf
├── config.json             # server URL, API key, genre colors, cover exclusions
├── config.example.json     # template (no secrets) for new setups
├── requirements.txt        # requests, Pillow, reportlab
├── library.json            # generated metadata cache (source of truth)
├── library.prev.json       # snapshot from the previous build (delta diff)
├── posters/                # generated poster images (git-ignored)
└── output/                 # generated PDFs + previews (git-ignored)
```

## Design notes (for tweaking)

**Cards** (2.5" x 3.5"): 0.1" white gutters between cards (borders must not
touch), 0.4" side / 0.15" top-bottom page margins, title in bold 10pt with
meta lines below (star rating, runtime, official rating, first genres). Genre
color = first listed genre. Missing artwork renders a gray placeholder card
with the title.

**Indexes**: two columns read *down the left column first, then the right*
(column-major), sections get a full-width colored divider with a count, and
continuation pages use a lighter italic "(cont)" header. Genres are sorted by
count (most popular first). Typography is plain Helvetica so the PDFs stay
tiny and generation is fast.

**Performance gotchas** (if you touch the code): card pages are rasterized at
300 DPI then streamed into the PDF with Pillow — do **not** cache all ~800
posters in memory at once (~1.2 GB). Keep the lazy generator; it must skip the
first page image or page 1 duplicates.

## Troubleshooting

| Problem | Fix |
|---|---|
| API returns 404 for `/Library/Movies` | Jellyfin 10.11+ removed it. The fetcher uses `/Items?IncludeItemTypes=Movie&Recursive=true` |
| Posters missing | Check `poster_file` in `library.json`; re-run `fetch_library.py --force` |
| Cards off-center in print | Print at 100% / actual size; disable "fit to page" |
| Cardstock jams | Use the manual/bypass tray, fan the paper, stay at 65lb cover |
| Build seems slow | ~4 min full build is normal (800+ posters). Use `--preview 2` for iteration |
| Cover has movies I don't want | Add their IDs to `cover_exclude_ids` in `config.json` |
| Index text overlap at genre boundaries | Fine-tune `SECTION_GAP` in `generate_index.py` |