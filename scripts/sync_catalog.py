#!/usr/bin/env python3
"""Build the public snake catalogue from the source site's current pages."""
from __future__ import annotations

import json
import re
import shutil
import time
from collections import Counter
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

SITE = "https://snake.pictureknow.com"
GROUPS = ("剧毒蛇", "微毒蛇", "无毒蛇")
OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "catalog.json"
PHOTO_ROOT = OUTPUT.parent / "photos"
HEADERS = {"User-Agent": "SnakeLibraryCloud/1.0 (public educational catalogue)"}


def fetch(url: str) -> str:
    for attempt in range(3):
        try:
            request = Request(url, headers=HEADERS)
            with urlopen(request, timeout=45) as response:
                return response.read().decode("utf-8")
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def fetch_bytes(url: str) -> tuple[bytes, str]:
    """Download an image with a small retry budget and return its content type."""
    for attempt in range(3):
        try:
            request = Request(url, headers=HEADERS)
            with urlopen(request, timeout=60) as response:
                return response.read(), response.headers.get_content_type()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def next_data(html: str) -> dict:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        raise ValueError("The source page no longer exposes its page data")
    return json.loads(unescape(match.group(1)))


def list_species() -> dict[str, str]:
    result: dict[str, str] = {}
    pattern = re.compile(r'<a href="/snake\?id=([^"]+)" class="template"><img[^>]*><div class="name">([^<]+)</div>')
    for toxicity in GROUPS:
        html = fetch(f"{SITE}/snakes?type={quote(toxicity)}")
        for site_id, _name in pattern.findall(html):
            result[site_id] = toxicity
    return result


def detail(site_id: str, fallback_toxicity: str) -> dict:
    raw = next_data(fetch(f"{SITE}/snake?id={site_id}"))
    data = raw["props"]["pageProps"]["result"]["data"]
    images = data.get("images", [])
    if isinstance(images, str):
        images = json.loads(images)
    image_urls = [item["img"] for item in images if item.get("img")]
    return {
        "site_id": site_id,
        "chinese_name": data.get("cnName", ""),
        "scientific_name": data.get("sciName", ""),
        "english_name": data.get("enName", ""),
        "toxicity": data.get("toxicity") or fallback_toxicity,
        "image_count": len(image_urls),
        # Kept only during collection.  The public catalogue gets local paths
        # after the image mirror has completed successfully.
        "_source_images": image_urls,
        "images": [],
        "source_url": f"{SITE}/snake?id={site_id}",
    }


def extension(content_type: str) -> str:
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(content_type, ".jpg")


def mirror_images(species: list[dict]) -> None:
    """Create a fresh, source-owned mirror; only swap it in if all downloads work."""
    staging = PHOTO_ROOT.with_name(".photos-staging")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        for position, item in enumerate(species, start=1):
            folder = staging / item["site_id"]
            folder.mkdir()
            paths: list[str] = []
            for index, url in enumerate(item.pop("_source_images"), start=1):
                content, mime = fetch_bytes(url)
                filename = f"{index:03d}{extension(mime)}"
                (folder / filename).write_bytes(content)
                paths.append(f"photos/{item['site_id']}/{filename}")
            item["images"] = paths
            item["image_count"] = len(paths)
            print(f"Mirrored {position}/{len(species)}: {item['chinese_name']} ({len(paths)} images)")
        shutil.rmtree(PHOTO_ROOT, ignore_errors=True)
        staging.replace(PHOTO_ROOT)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> None:
    species = [detail(site_id, toxicity) for site_id, toxicity in list_species().items()]
    species.sort(key=lambda item: item["chinese_name"])
    mirror_images(species)
    totals = Counter(item["toxicity"] for item in species)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SITE,
        "total_species": len(species),
        "toxicity_summary": [
            {"toxicity": toxicity, "species_count": totals[toxicity]}
            for toxicity in GROUPS
        ],
        "species": species,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Updated {len(species)} species in {OUTPUT}")


if __name__ == "__main__":
    main()
