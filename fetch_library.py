#!/usr/bin/env python3
"""Fetch all movies and TV series from Jellyfin and save to library.json + posters/."""

import json
import os
import sys
import time
import argparse
from datetime import datetime

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LIBRARY_PATH = os.path.join(BASE_DIR, "library.json")

FIELDS = "Genres,Overview,CommunityRating,OfficialRating,RunTimeTicks,ProductionYear"


def load_config():
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    if cfg.get("api_key", "").startswith("YOUR_API_KEY"):
        print("[ERROR] API key not configured in config.json", file=sys.stderr)
        sys.exit(1)
    return cfg


def api_get(cfg, path, params=None):
    if params is None:
        params = {}
    params["api_key"] = cfg["api_key"]
    url = cfg["server_url"] + path
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def item_to_record(cfg, item, item_type):
    rec = {
        "id": item["Id"],
        "name": item.get("Name", "Unknown"),
        "year": item.get("ProductionYear"),
        "official_rating": item.get("OfficialRating"),
        "community_rating": item.get("CommunityRating"),
        "genres": item.get("Genres") or [],
        "overview": item.get("Overview", ""),
        "poster_file": "",
    }
    runtime_ticks = item.get("RunTimeTicks")
    if runtime_ticks:
        rec["runtime_minutes"] = runtime_ticks // 600000000
    else:
        rec["runtime_minutes"] = None

    if item_type == "Series":
        rec["season_count"] = item.get("ChildCount") or 0

    # Only set poster_file if a primary image exists
    tags = item.get("ImageTags") or {}
    if "Primary" in tags:
        rec["poster_file"] = f"posters/{rec['id']}.jpg"
    return rec


def download_poster(cfg, item_id, dest_path):
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        return True
    url = f"{cfg['server_url']}/Items/{item_id}/Images/Primary"
    params = {"api_key": cfg["api_key"], "maxWidth": cfg.get("poster_width", 500)}
    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 200 and r.content:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(r.content)
            return True
    except Exception as e:
        print(f"  [warn] Poster download failed for {item_id}: {e}")
    return False


def paginate(cfg, item_type):
    """Yield all items of a type, paginated."""
    items = []
    start_index = 0
    limit = 100
    while True:
        data = api_get(cfg, "/Items", {
            "IncludeItemTypes": item_type,
            "Recursive": "true",
            "StartIndex": start_index,
            "Limit": limit,
            "Fields": FIELDS,
        })
        page = data.get("Items", [])
        items.extend(page)
        total = data.get("TotalRecordCount", 0)
        start_index += len(page)
        if start_index >= total or not page:
            break
    return items


def fetch_movies(cfg, force):
    items = paginate(cfg, "Movie")
    records = [item_to_record(cfg, it, "Movie") for it in items]
    print(f"  Movies: {len(records)}")
    return records


def fetch_series(cfg, force):
    items = paginate(cfg, "Series")
    records = [item_to_record(cfg, it, "Series") for it in items]
    print(f"  TV Series: {len(records)}")
    return records


def download_all_posters(cfg, records):
    ok = 0
    missing = 0
    for rec in records:
        if rec["poster_file"]:
            dest = os.path.join(BASE_DIR, rec["poster_file"])
            if download_poster(cfg, rec["id"], dest):
                ok += 1
            else:
                missing += 1
    print(f"  Posters downloaded: {ok}, missing: {missing}")


def main():
    parser = argparse.ArgumentParser(description="Fetch Jellyfin library to library.json")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if library.json exists")
    parser.add_argument("--movies-only", action="store_true", help="Only fetch movies")
    parser.add_argument("--tv-only", action="store_true", help="Only fetch TV series")
    args = parser.parse_args()

    cfg = load_config()

    # Resume capability: load existing library.json if present (unless --force)
    library = {}
    if os.path.exists(LIBRARY_PATH) and not args.force:
        with open(LIBRARY_PATH) as f:
            library = json.load(f)
        print(f"[info] Loaded existing library.json ({len(library.get('movies', []))} movies, {len(library.get('tv_series', []))} series)")

    do_movies = not args.tv_only
    do_tv = not args.movies_only

    if do_movies:
        print("Fetching movies...")
        library["movies"] = fetch_movies(cfg, args.force)
    if do_tv:
        print("Fetching TV series...")
        library["tv_series"] = fetch_series(cfg, args.force)

    library["generated_at"] = datetime.now().isoformat()
    library["server_url"] = cfg["server_url"]

    with open(LIBRARY_PATH, "w") as f:
        json.dump(library, f, indent=2, ensure_ascii=False)
    print(f"[ok] library.json saved")

    # Download posters
    print("Downloading posters...")
    all_records = library.get("movies", []) + library.get("tv_series", [])
    download_all_posters(cfg, all_records)

    print("Done.")


if __name__ == "__main__":
    main()
