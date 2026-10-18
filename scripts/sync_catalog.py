#!/usr/bin/env python3
"""Incrementally archive only snake images published in the site's Topics section."""
from __future__ import annotations

import json
import argparse
import io
from PIL import Image
import hashlib
import tempfile
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler

TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_url(url: str) -> str:
    """Return a stable URL identity without changing content-bearing parameters."""
    value = url.strip()
    if value.startswith("local:"):
        return value
    parts = urlsplit(value)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    if parts.username:
        credentials = parts.username
        if parts.password:
            credentials += f":{parts.password}"
        host = f"{credentials}@{host}"
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if key.lower() not in TRACKING_QUERY_KEYS and not key.lower().startswith("utm_")]
    return urlunsplit((scheme, host, parts.path or "/", urlencode(sorted(query), doseq=True), ""))


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def atomic_write_bytes(path: Path, content: bytes, *, exclusive: bool = False) -> bool:
    """Atomically create/replace a file; exclusive mode never changes an existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive and path.exists():
        return False
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            try:
                os.link(temp_path, path)
            except FileExistsError:
                return False
            except OSError:
                if path.exists():
                    return False
                os.replace(temp_path, path)
                return True
            return True
        os.replace(temp_path, path)
        return True
    finally:
        temp_path.unlink(missing_ok=True)


def atomic_write_json(path: Path, payload: dict) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    atomic_write_bytes(path, encoded)


def load_index(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 2, "updated_at": utc_now(), "photos": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Photo index is unreadable; refusing a destructive rebuild: {path}") from error
    if not isinstance(payload.get("photos"), list):
        raise RuntimeError(f"Photo index has an invalid format: {path}")
    payload.setdefault("schema_version", 1)
    return payload


class ImageStore:
    """Store one immutable blob in the repository and optional external local mirror."""

    def __init__(self, docs_root: Path, local_root: Path | None = None):
        self.docs_root = docs_root
        self.cloud_root = docs_root / "photos"
        self.local_root = local_root

    @staticmethod
    def relative_path(site_id: str, digest: str, suffix: str) -> Path:
        clean_suffix = suffix.lower() if suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"} else ".img"
        return Path(site_id) / f"{digest}{clean_suffix}"

    def put(self, site_id: str, content: bytes, suffix: str) -> dict:
        digest = content_sha256(content)
        relative = self.relative_path(site_id, digest, suffix)
        cloud_path = self.cloud_root / relative
        atomic_write_bytes(cloud_path, content, exclusive=True)
        if content_sha256(cloud_path.read_bytes()) != digest:
            raise RuntimeError(f"Existing repository image conflicts with its content hash: {cloud_path}")

        local_ok = self.local_root is None
        local_path = None
        if self.local_root is not None:
            local_path = self.local_root / relative
            atomic_write_bytes(local_path, content, exclusive=True)
            local_ok = content_sha256(local_path.read_bytes()) == digest
            if not local_ok:
                raise RuntimeError(f"Existing local image conflicts with its content hash: {local_path}")
        return {
            "sha256": digest,
            "path": str((Path("photos") / relative).as_posix()),
            "cloud_saved": True,
            "local_saved": local_ok,
            "local_path": str(local_path) if local_path else None,
        }


def merge_record(records: list[dict], candidate: dict) -> tuple[dict, bool]:
    """Append a new blob or attach a new URL alias without duplicating content."""
    normalized = candidate["normalized_url"]
    digest = candidate["sha256"]
    for record in records:
        aliases = set(record.get("urls", []))
        if record.get("url"):
            aliases.add(record["url"])
        normalized_aliases = {normalize_url(item) for item in aliases}
        same_content = bool(record.get("sha256")) and record.get("sha256") == digest
        legacy_url_match = not record.get("sha256") and normalized in normalized_aliases
        if same_content or legacy_url_match:
            urls = list(dict.fromkeys([*record.get("urls", []), record.get("url"), candidate["url"]]))
            record["urls"] = [item for item in urls if item]
            record.setdefault("url", candidate["url"])
            if not record.get("sha256"):
                record["sha256"] = digest
                record["path"] = candidate["path"]
            site_ids = list(dict.fromkeys([*record.get("site_ids", []), record.get("site_id"), candidate.get("site_id")]))
            record["site_ids"] = [item for item in site_ids if item]
            record["cloud_saved"] = record.get("cloud_saved", False) or candidate.get("cloud_saved", False)
            record["local_saved"] = record.get("local_saved", False) or candidate.get("local_saved", False)
            if candidate.get("local_path"):
                record["local_path"] = candidate["local_path"]
            return record, False
    records.append(candidate)
    return candidate, True


SITE = "https://snake.pictureknow.com"
API = f"{SITE}/api/v2/snake/share/topics"
ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX = DOCS / "topic_photo_index.json"
STATE = DOCS / "topic_sync_state.json"
SPECIES_CATALOG = DOCS / "species_catalog.json"
PENDING_TOPICS = ROOT / "scripts" / "pending_topic_photos.json"
MAX_TOPICS = 500  # The web client applies the same upper bound.
PAGE_SIZE = 50
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SnakeTopicArchiver/2.0)",
    "Referer": f"{SITE}/topics",
    "Accept": "application/json, text/plain, */*",
}


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and urlsplit(req.full_url).netloc != urlsplit(newurl).netloc:
            redirected.remove_header("Cookie")
        return redirected


def request_bytes(url: str, token: str, *, timeout: int = 30) -> tuple[bytes, str]:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in {"snake.pictureknow.com", "xstatic.pictureknow.com", "static.pictureknow.com"} or parts.username or parts.password:
        raise RuntimeError("Unexpected source URL")
    headers = dict(HEADERS)
    if token and urlsplit(url).hostname == "snake.pictureknow.com":
        headers["Cookie"] = f"token={token}"
    for attempt in range(3):
        try:
            with build_opener(SameOriginRedirect()).open(Request(url, headers=headers), timeout=timeout) as response:
                return response.read(), response.headers.get_content_type()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def fetch_page(page: int, token: str) -> dict:
    # Public client request prefix; not an account credential or login token.
    prefix = 'kyR3Q77sBlhMgeUhSGxYbAdtIIKpLCyMHUnmms+8q5EyBkybMReXPbt5wrAa95J5:'
    timestamp = int(time.time() * 1000)
    signature = hashlib.md5(f"{prefix}{page}&{timestamp}".encode()).hexdigest()
    url = f"{API}?{urlencode(dict(page=page, size=PAGE_SIZE, timestamp=timestamp, signature=signature))}"
    raw, _mime = request_bytes(url, token)
    payload = json.loads(raw.decode("utf-8"))
    base = payload.get("base_resp", {})
    if base.get("ret") not in (None, 0):
        raise RuntimeError(f"Topics API rejected the request: {base.get('msg', 'unknown error')}")
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        raise RuntimeError("Topics API response format has changed")
    return data


def collect_topics(token: str, start: datetime) -> list[dict]:
    topics, seen = [], set()
    for page in range(1, MAX_TOPICS // PAGE_SIZE + 1):
        data = fetch_page(page, token)
        batch = data["pages"]
        ids = {str(t.get("uniqueId")) for t in batch}
        if batch and ids <= seen:
            raise RuntimeError("Pagination repeated; coverage incomplete")
        seen.update(ids)
        topics.extend(batch)
        if any(topic_time(t) < start for t in batch):
            return topics
        if not batch or len(topics) >= int(data.get("total", MAX_TOPICS + 1)):
            return topics
    raise RuntimeError("500-item boundary reached before requested start; coverage incomplete")


def parse_cutoff(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone missing")
        return parsed.astimezone(timezone.utc)
    except (TypeError, AttributeError, ValueError) as error:
        raise RuntimeError("Cutoff must be an ISO-8601 timestamp with timezone") from error


def load_sync_state() -> dict:
    if not STATE.exists():
        raise RuntimeError("No verified checkpoint. Recover it from a verified publication; do not silently default to yesterday or three days ago. Explicit --since/--days can be used for an authorized backfill.")
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError("Sync state unreadable; cutoff unchanged") from error
    if not isinstance(state, dict) or not state.get("last_successful_cutoff"):
        raise RuntimeError("Sync state missing last_successful_cutoff")
    parse_cutoff(state["last_successful_cutoff"])
    if not isinstance(state.get("retry_topics", []), list) or not isinstance(state.get("excluded_topic_ids", []), list):
        raise RuntimeError("Sync retry/exclusion state malformed")
    return state


def incremental_window(now: datetime | None = None, *, since: str | None = None, days: float | None = None) -> tuple[datetime, datetime]:
    end = now or datetime.now(timezone.utc)
    if end.tzinfo is None:
        raise RuntimeError("Current time must carry a timezone")
    end = end.astimezone(timezone.utc)
    if since is not None and days is not None:
        raise RuntimeError("Choose either --since or --days")
    if since is not None:
        start = parse_cutoff(since)
    elif days is not None:
        if days <= 0:
            raise RuntimeError("--days must be positive")
        start = end - timedelta(days=days)
    else:
        start = parse_cutoff(load_sync_state()["last_successful_cutoff"])
    if start > end:
        raise RuntimeError("Verified checkpoint is in the future; refusing to skip content")
    return start, end


def review_candidates(discovered: list[dict], start: datetime, end: datetime, state: dict) -> list[dict]:
    known_urls = {normalize_url(url) for record in load_index(INDEX)["photos"]
                  for url in [record.get("url"), *record.get("urls", [])] if url}
    excluded = set(state.get("excluded_topic_ids", []))
    combined = [*state.get("retry_topics", []), *topics_in_window(discovered, start, end)]
    result, seen = [], set()
    for topic in combined:
        topic_id = str(topic.get("uniqueId", ""))
        url = normalize_url(str(topic.get("img", "")).split("?x-oss-process=", 1)[0])
        if not topic_id or topic_id in seen or topic_id in excluded or url in known_urls:
            continue
        seen.add(topic_id)
        # A previous approval is not inherited by an unresolved retry.
        item = dict(topic)
        item.pop("visual_verified", None)
        result.append(item)
    return result


def topic_time(topic: dict) -> datetime:
    raw = topic.get("createTime")
    if isinstance(raw, (int, float)):
        seconds = raw / 1000 if raw > 10_000_000_000 else raw
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    if isinstance(raw, str) and raw.strip():
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    raise RuntimeError(f"Topic {topic.get('uniqueId', '<unknown>')} has no valid createTime")


def topics_in_window(topics: list[dict], start: datetime, end: datetime) -> list[dict]:
    return [topic for topic in topics if start <= topic_time(topic) < end]


def image_suffix(url: str, mime: str) -> str:
    by_mime = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif", "image/avif": ".avif"}
    return by_mime.get(mime, Path(urlsplit(url).path).suffix or ".img")



def _species_key(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def load_species_catalog() -> list[dict]:
    payload = json.loads(SPECIES_CATALOG.read_text(encoding="utf-8"))
    species = payload.get("species")
    if not isinstance(species, list) or len(species) != 152:
        raise RuntimeError("Species catalog must contain exactly 152 species")
    return species


def match_species(topic: dict, species_catalog: list[dict]) -> dict | None:
    """Match a topic conservatively by site id, scientific name, or Chinese name."""
    resolved = []
    for source, field in (("snakeId", "site_id"), ("sciName", "scientific_name"), ("cnName", "chinese_name")):
        value = _species_key(topic.get(source))
        if not value:
            continue
        matches = [item for item in species_catalog if _species_key(item.get(field)) == value]
        if len(matches) > 1:
            return None
        if matches:
            resolved.append(matches[0])
    if not resolved or len({item["site_id"] for item in resolved}) != 1:
        return None
    return resolved[0]


def archive_topics(topics: list[dict], token: str) -> tuple[int, int]:
    index = load_index(INDEX)
    records = index["photos"]
    original_records = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    local_value = os.environ.get("SNAKE_LOCAL_PHOTO_ROOT", "").strip()
    store = ImageStore(DOCS, Path(local_value).expanduser() if local_value else None)
    species_catalog = load_species_catalog()
    for record in records:
        path = DOCS / record.get("path", "")
        if path.is_file():
            record.setdefault("sha256", content_sha256(path.read_bytes()))
            record["cloud_saved"] = True
    known = {
        normalize_url(url)
        for record in records if (DOCS / record.get("path", "")).is_file()
        for url in [record.get("url"), *record.get("urls", [])] if url
    }
    added = 0
    skipped = []
    for topic in topics:
        if topic.get("visual_verified") is not True:
            skipped.append({"topic_id": topic.get("uniqueId"), "reason": "visual_review_required"})
            continue
        species = match_species(topic, species_catalog)
        if species is None:
            skipped.append({"topic_id": topic.get("uniqueId"), "reason": "unmatched_or_conflicting_species"})
            continue
        url = str(topic.get("img", "")).split("?x-oss-process=", 1)[0].strip()
        topic_id = str(topic.get("uniqueId", "")).strip()
        normalized = normalize_url(url) if url else ""
        if not url or not topic_id:
            continue
        if normalized in known and not local_value:
            for record in records:
                aliases = [record.get("url"), *record.get("urls", [])]
                if normalized in {normalize_url(alias) for alias in aliases if alias}:
                    if topic_id not in record.setdefault("topic_ids", []):
                        record["topic_ids"].append(topic_id)
                    break
            continue
        download_url = topic.get("download_url") or url
        content, mime = request_bytes(download_url, token)
        try:
            with Image.open(io.BytesIO(content)) as image:
                image_format = image.format
                image.verify()
        except Exception as error:
            raise RuntimeError(f"Invalid image for topic {topic_id}") from error
        suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif", "AVIF": ".avif"}.get(image_format)
        if not suffix:
            raise RuntimeError(f"Unsupported image format for topic {topic_id}")
        digest = content_sha256(content)
        existing = next((r for r in records if r.get("sha256") == digest), None)
        if existing:
            canonical = Path(existing["path"])
            if canonical.is_absolute() or ".." in canonical.parts or canonical.parts[0] != "photos":
                raise RuntimeError("Unsafe canonical photo path")
            cloud_path = DOCS / canonical
            atomic_write_bytes(cloud_path, content, exclusive=True)
            if content_sha256(cloud_path.read_bytes()) != digest:
                raise RuntimeError("Existing image hash conflict")
            stored = {"path": existing["path"], "sha256": digest, "cloud_saved": True}
            if store.local_root:
                mirror = store.local_root / Path(*canonical.parts[1:])
                atomic_write_bytes(mirror, content, exclusive=True)
                if content_sha256(mirror.read_bytes()) != digest:
                    raise RuntimeError("Mirror image hash conflict")
                stored.update(local_saved=True, local_path=str(mirror))
        else:
            stored = store.put(species["folder"], content, suffix)
        candidate = {
            "url": url,
            "download_url": download_url,
            "original_unavailable": topic.get("original_unavailable"),
            "urls": [url],
            "normalized_url": normalized,
            "site_id": species["site_id"],
            "topic_ids": [topic_id],
            "source_url": f"{SITE}/topics",
            "snake_id": topic.get("snakeId"),
            "chinese_name": species["chinese_name"],
            "scientific_name": species["scientific_name"],
            "toxicity": species["toxicity"],
            "species_folder": species["folder"],
            "published_at": topic_time(topic).isoformat() if topic.get("createTime") else None,
            "visual_verified": True,
            "captured_at": utc_now(),
            **stored,
        }
        record, is_new = merge_record(records, candidate)
        if topic_id not in record.setdefault("topic_ids", []):
            record["topic_ids"].append(topic_id)
        known.add(candidate["normalized_url"])
        added += int(is_new)
    for record in records:
        record.pop("normalized_url", None)
    current_records = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if current_records != original_records:
        atomic_write_json(INDEX, {
            "schema_version": 2,
            "source": f"{SITE}/topics",
            "updated_at": utc_now(),
            "photos": records,
        })
    if added or skipped or not (DOCS / "topic_sync_report.json").exists():
        atomic_write_json(DOCS / "topic_sync_report.json", {"checked": len(topics), "added": added, "total": len(records), "skipped": skipped})
    return added, len(records)


def load_pending_topics() -> list[dict]:
    """Load manually verified Topics records. Keeping this file is safe: URL and SHA-256 checks make reruns idempotent."""
    if not PENDING_TOPICS.exists():
        return []
    payload = json.loads(PENDING_TOPICS.read_text(encoding="utf-8"))
    topics = payload.get("topics", [])
    if not isinstance(topics, list):
        raise RuntimeError(f"Pending topics file has an invalid format: {PENDING_TOPICS}")
    return topics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pending-only", action="store_true", help="Import verified records only; does not certify API discovery or advance cutoff")
    window = parser.add_mutually_exclusive_group()
    window.add_argument("--since", help="Explicit backfill start with timezone; default: last verified checkpoint")
    window.add_argument("--days", type=float, help="Explicit rolling-day override; never the default")
    args = parser.parse_args()
    if args.days is not None and args.days <= 0:
        parser.error("--days must be positive")
    token = os.environ.get("SNAKE_TOPIC_TOKEN", "").strip()
    if not token and not args.pending_only:
        raise SystemExit("SNAKE_TOPIC_TOKEN missing: discovery NOT completed. Log in or configure repository Secret; use --pending-only only for verified browser imports.")
    pending = load_pending_topics()
    pending_added = 0
    total = len(load_index(INDEX)["photos"])
    if pending:
        pending_added, total = archive_topics(pending, token)
        print(f"Verified pending topics: {len(pending)}; new unique photos: {pending_added}; archived total: {total}")
    if args.pending_only:
        print("Verified import completed; API discovery not performed; cutoff unchanged.")
        return
    start, end = incremental_window(since=args.since, days=args.days)
    state = load_sync_state() if STATE.exists() else {}
    discovered = collect_topics(token, start)
    topics = review_candidates(discovered, start, end, state)
    # Automated species labels do not prove an image contains a snake.
    # Discovery queues candidates; the Codex skill performs visual review before import.
    atomic_write_json(ROOT / "scripts" / "topic_review_queue.json", {
        "source": f"{SITE}/topics", "base_cutoff": state.get("last_successful_cutoff"), "window_start": start.isoformat(),
        "window_end": end.isoformat(), "scanned": len(discovered), "topics": topics,
    })
    print(f"Window: {start.isoformat()} to {end.isoformat()}; {len(topics)} candidates including unresolved retries; no cutoff advanced.")


if __name__ == "__main__":
    main()
