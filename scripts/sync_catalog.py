#!/usr/bin/env python3
"""Incrementally archive only snake images published in the site's Topics section."""
from __future__ import annotations

import json
import hashlib
import tempfile
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

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


def request_bytes(url: str, token: str, *, timeout: int = 30) -> tuple[bytes, str]:
    headers = dict(HEADERS)
    if token:
        headers["Cookie"] = f"token={token}"
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers), timeout=timeout) as response:
                return response.read(), response.headers.get_content_type()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def fetch_page(page: int, token: str) -> dict:
    url = f"{API}?{urlencode({'page': page, 'size': PAGE_SIZE})}"
    raw, _mime = request_bytes(url, token)
    payload = json.loads(raw.decode("utf-8"))
    base = payload.get("base_resp", {})
    if base.get("ret") not in (None, 0):
        raise RuntimeError(f"Topics API rejected the request: {base.get('msg', 'unknown error')}")
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        raise RuntimeError("Topics API response format has changed")
    return data


def collect_topics(token: str) -> list[dict]:
    topics: list[dict] = []
    page = 1
    while len(topics) < MAX_TOPICS:
        data = fetch_page(page, token)
        batch = data["pages"]
        topics.extend(batch[: MAX_TOPICS - len(topics)])
        total = min(int(data.get("total", len(topics))), MAX_TOPICS)
        if not batch or len(topics) >= total:
            break
        page += 1
    return topics


def scheduled_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return the unprocessed [start, end) window bounded by 09:00 China time."""
    china = timezone(timedelta(hours=8))
    current = (now or datetime.now(timezone.utc)).astimezone(china)
    end = current.replace(hour=9, minute=0, second=0, microsecond=0)
    if current < end:
        end -= timedelta(days=1)
    default_start = end - timedelta(days=1)
    if not STATE.exists():
        return default_start, end
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if not state.get("last_successful_cutoff"):
            return default_start, end
        previous = datetime.fromisoformat(state["last_successful_cutoff"])
        if previous.tzinfo is None:
            raise ValueError("cutoff has no timezone")
        start = previous.astimezone(china)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Sync state is invalid; refusing to risk a gap: {STATE}") from error
    if start > end:
        raise RuntimeError("Sync state cutoff is later than the current 09:00 boundary")
    return start, end


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
    snake_id = _species_key(topic.get("snakeId"))
    scientific = _species_key(topic.get("sciName"))
    chinese = _species_key(topic.get("cnName"))
    if snake_id:
        matches = [item for item in species_catalog if _species_key(item.get("site_id")) == snake_id]
        if len(matches) == 1:
            return matches[0]
    for field, value in (("scientific_name", scientific), ("chinese_name", chinese)):
        if value:
            matches = [item for item in species_catalog if _species_key(item.get(field)) == value]
            if len(matches) == 1:
                return matches[0]
    return None


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
    for topic in topics:
        species = match_species(topic, species_catalog)
        if species is None:
            continue
        url = str(topic.get("img", "")).split("?x-oss-process=", 1)[0].strip()
        topic_id = str(topic.get("uniqueId", "")).strip()
        normalized = normalize_url(url) if url else ""
        if not url or not topic_id:
            continue
        if normalized in known:
            for record in records:
                aliases = [record.get("url"), *record.get("urls", [])]
                if normalized in {normalize_url(alias) for alias in aliases if alias}:
                    if topic_id not in record.setdefault("topic_ids", []):
                        record["topic_ids"].append(topic_id)
                    break
            continue
        content, mime = request_bytes(url, token)
        stored = store.put(species["folder"], content, image_suffix(url, mime))
        candidate = {
            "url": url,
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
    token = os.environ.get("SNAKE_TOPIC_TOKEN", "").strip()
    pending = load_pending_topics()
    pending_added = 0
    total = len(load_index(INDEX)["photos"])
    if pending:
        pending_added, total = archive_topics(pending, token)
        print(f"Verified pending topics: {len(pending)}; new unique photos: {pending_added}; archived total: {total}")
    if not token:
        print("SNAKE_TOPIC_TOKEN is not configured; API discovery skipped after importing verified public Topics images.")
        return
    start, end = scheduled_window()
    discovered = collect_topics(token)
    topics = topics_in_window(discovered, start, end)
    added, total = archive_topics(topics, token)
    # Advance only after every image and the index have been committed locally.
    atomic_write_json(STATE, {"last_successful_cutoff": end.isoformat(), "updated_at": utc_now()})
    print(f"Window: {start.isoformat()} to {end.isoformat()}; matching topics: {len(topics)}; new unique photos: {added}; archived total: {total}")


if __name__ == "__main__":
    main()

