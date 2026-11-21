#!/usr/bin/env python3
"""Fetch RSS/Atom news and video feeds; publish summaries and media metadata only."""
import json, re, html, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
SOURCES_FILE = ROOT / "sources.json"
OUTPUT = ROOT / "news.json"
MAX_PER_SOURCE = 30
MAX_TOTAL = 240

def local(tag):
    return tag.rsplit("}", 1)[-1].split(":")[-1].lower()

def clean(value):
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", str(value))
    return re.sub(r"\s+", " ", html.unescape(value)).strip()

def child_text(entry, names):
    wanted = {name.lower() for name in names}
    for node in entry:
        if local(node.tag) in wanted:
            value = clean(" ".join(part for part in node.itertext() if part))
            if value:
                return value
    return ""

def parse_date(entry):
    for node in entry.iter():
        if local(node.tag) in ("pubdate", "published", "updated", "date") and node.text:
            value = node.text.strip()
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except Exception:
                try:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.astimezone(timezone.utc).isoformat()
                except Exception:
                    pass
    return ""

def get_link(entry):
    for node in entry.iter():
        if local(node.tag) == "link":
            value = node.attrib.get("href") or (node.text or "").strip()
            rel = node.attrib.get("rel", "alternate")
            if value and rel in ("alternate", "") and urlparse(value).scheme in ("http", "https"):
                return value
    return ""

def get_media(entry, link, description):
    image = ""
    video = ""
    video_id = ""
    raw_description = ""
    for node in entry.iter():
        tag = local(node.tag)
        if tag in ("description", "summary", "encoded", "content") and not raw_description:
            raw_description = "".join(node.itertext())
        url = node.attrib.get("url") or node.attrib.get("href") or ""
        mime = node.attrib.get("type", "").lower()
        medium = node.attrib.get("medium", "").lower()
        if tag in ("thumbnail", "image") and url and not image:
            image = url
        elif tag in ("content", "enclosure") and url:
            if medium == "image" or mime.startswith("image/") or re.search(r"\.(jpg|jpeg|png|webp|gif)(?:\?|$)", url, re.I):
                if not image:
                    image = url
            elif medium == "video" or mime.startswith("video/") or re.search(r"\.(mp4|webm|m3u8)(?:\?|$)", url, re.I):
                if not video:
                    video = url
        if tag == "videoid" and node.text:
            video_id = node.text.strip()
    if not image:
        match = re.search("<img[^>]+src=[\\\"']([^\\\"']+)[\\\"']", raw_description or description or "", re.I)
        if match:
            image = html.unescape(match.group(1))
    if not video_id and link:
        parsed = urlparse(link)
        if "youtube.com" in parsed.netloc:
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif "youtu.be" in parsed.netloc:
            video_id = parsed.path.strip("/").split("/")[0]
    embed = "https://www.youtube-nocookie.com/embed/" + video_id if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id or "") else ""
    return image, video, embed

def fetch_feed(source):
    feed_url = quote(source["url"], safe=":/?&=%#[]@!$'()*+,;")
    request = urllib.request.Request(feed_url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AkhbarBlaharaa/2.0)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"
    })
    with urllib.request.urlopen(request, timeout=14) as response:
        raw = response.read(2500000)
    root = ET.fromstring(raw)
    entries = [node for node in root.iter() if local(node.tag) in ("item", "entry")]
    results = []
    for entry in entries[:MAX_PER_SOURCE]:
        title = child_text(entry, ("title",))
        description = child_text(entry, ("description", "summary", "encoded", "content"))
        link = get_link(entry)
        if not title or not link or urlparse(link).scheme not in ("http", "https"):
            continue
        image, video, embed = get_media(entry, link, description)
        uid = hashlib.sha256((title + link).encode("utf-8")).hexdigest()[:16]
        results.append({
            "id": uid, "title": title, "description": description[:500],
            "url": link, "source": source["name"], "date": parse_date(entry),
            "category": source.get("category", "العالم"),
            "image": image, "video_url": video, "video_embed": embed,
            "media_type": "video" if video or embed else ("image" if image else "")
        })
    return results

def main():
    sources = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    previous_ids = set()
    previous_sources = set()
    if OUTPUT.exists():
        try:
            previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
            previous_ids = {article.get("id") for article in previous.get("articles", []) if article.get("id")}
            previous_sources = set(previous.get("source_names") or [
                article.get("source") for article in previous.get("articles", []) if article.get("source")
            ])
        except Exception:
            pass
    all_articles = []
    failed = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        jobs = {pool.submit(fetch_feed, source): source for source in sources}
        for future in as_completed(jobs):
            source = jobs[future]
            try:
                found = future.result()
                all_articles.extend(found)
                print(f"OK {source['name']}: {len(found)}")
            except Exception as exc:
                failed.append(source["name"])
                print(f"SKIP {source['name']}: {exc}")
    unique = []
    seen = set()
    for article in all_articles:
        key = article["url"].split("#")[0].rstrip("/") or article["title"].strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(article)
    unique.sort(key=lambda article: article.get("date") or "", reverse=True)
    latest = unique[:MAX_TOTAL]
    # New sources are added silently on their first fetch to prevent a notification flood.
    new_articles = [
        article for article in latest
        if article.get("id") not in previous_ids and article.get("source") in previous_sources
    ]
    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "sources_total": len(sources),
        "source_names": [source["name"] for source in sources],
        "sources_failed": sorted(failed),
        "articles": latest,
        "new_articles": new_articles
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(latest)} stories; {len(new_articles)} new stories. Failed feeds: {len(failed)}")

if __name__ == "__main__":
    main()
