#!/usr/bin/env python3
"""Build the public snake catalogue from the source site's current pages."""
from __future__ import annotations

import json
import re
import hashlib
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
PHOTO_INDEX = OUTPUT.parent / "photo_index.json"
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


def load_photo_index() -> list[dict]:
    if not PHOTO_INDEX.exists():
        return []
    try:
        return json.loads(PHOTO_INDEX.read_text(encoding="utf-8")).get("photos", [])
    except (OSError, json.JSONDecodeError):
        return []


def archive_new_images(species: list[dict]) -> None:
    """Append new source photos to the cloud archive; never remove old ones."""
    PHOTO_ROOT.mkdir(parents=True, exist_ok=True)
    saved = [entry for entry in load_photo_index() if (OUTPUT.parent / entry.get("path", "")).is_file()]
    known_urls = {entry["url"] for entry in saved if entry.get("url")}
    for position, item in enumerate(species, start=1):
        folder = PHOTO_ROOT / item["site_id"]
        folder.mkdir(exist_ok=True)
        added = 0
        for url in item.pop("_source_images"):
            if url in known_urls:
                continue
            content, mime = fetch_bytes(url)
            filename = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20] + extension(mime)
            path = folder / filename
            if not path.exists():
                path.write_bytes(content)
            saved.append({"url": url, "site_id": item["site_id"], "path": str(path.relative_to(OUTPUT.parent)), "captured_at": datetime.now(timezone.utc).isoformat()})
            known_urls.add(url)
            added += 1
        # Show every historical photo for this species, including photos no longer
        # displayed by the source website.
        item["images"] = [entry["path"] for entry in saved if entry.get("site_id") == item["site_id"]]
        item["image_count"] = len(item["images"])
        print(f"Archived {position}/{len(species)}: {item['chinese_name']} (+{added}, total {item['image_count']})")
    PHOTO_INDEX.write_text(json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "photos": saved}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> None:
    species = [detail(site_id, toxicity) for site_id, toxicity in list_species().items()]
    species.sort(key=lambda item: item["chinese_name"])
    archive_new_images(species)
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
