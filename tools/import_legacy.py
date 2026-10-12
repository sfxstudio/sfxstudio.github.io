#!/usr/bin/env python3
"""Import the legacy WordPress site (sfxstudio.ru) into a transport folder.

Runs on a GitHub Actions runner. Saves the WP REST API dumps (posts, pages,
categories, tags, media), every original file from wp-content/uploads that the
site references, and YouTube preview frames. Files above 95 MB are split into
chunks so they fit into git; they are reassembled locally.
"""
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests

BASE = "https://sfxstudio.ru"
OUT = Path("legacy")
RAW = OUT / "raw"
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (sfxstudio site migration)"
REPORT = {"downloaded": [], "failed": [], "split": []}


def get(url, **kw):
    for attempt in range(4):
        try:
            r = S.get(url, timeout=120, **kw)
            if r.status_code == 200:
                return r
            if r.status_code in (400, 404):
                return r
        except requests.RequestException as e:
            print("retry", url, e, file=sys.stderr)
        time.sleep(2 + attempt * 3)
    return None


def paged(endpoint, params):
    items, page = [], 1
    while True:
        p = dict(params, per_page=100, page=page)
        r = get(f"{BASE}/wp-json/wp/v2/{endpoint}", params=p)
        if r is None or r.status_code != 200:
            break
        batch = r.json()
        if not batch:
            break
        items.extend(batch)
        total = int(r.headers.get("X-WP-TotalPages", "1"))
        if page >= total:
            break
        page += 1
    return items


def save_json(name, data):
    (OUT / "wp").mkdir(parents=True, exist_ok=True)
    (OUT / "wp" / name).write_text(json.dumps(data, ensure_ascii=False, indent=1))


UPLOAD_RE = re.compile(r"https?://(?:www\.)?sfxstudio\.ru/wp-content/uploads/[^\"'\s)<>]+", re.I)
SIZE_SUFFIX = re.compile(r"-\d{2,5}x\d{2,5}(?=\.[a-z0-9]+$)", re.I)
YT_RE = re.compile(r"(?:youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})")
IFRAME_RE = re.compile(r"<iframe[^>]+src=[\"']([^\"']+)", re.I)


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return True
    r = get(url, stream=True)
    if r is None or r.status_code != 200:
        REPORT["failed"].append({"url": url, "status": getattr(r, "status_code", None)})
        return False
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)
    REPORT["downloaded"].append({"url": url, "path": str(dest), "bytes": dest.stat().st_size})
    return True


def main():
    OUT.mkdir(exist_ok=True)
    posts = paged("posts", {"_embed": "1"})
    pages = paged("pages", {})
    cats = paged("categories", {})
    tags = paged("tags", {})
    media = paged("media", {})
    for name, data in [("posts.json", posts), ("pages.json", pages), ("categories.json", cats),
                       ("tags.json", tags), ("media.json", media)]:
        save_json(name, data)

    # Raw HTML of key pages (menus, widgets, theme assets)
    html_dir = OUT / "html"
    html_dir.mkdir(exist_ok=True)
    key_pages = ["/", "/about-us/", "/contacts/", "/showreel/", "/katok/", "/?page_id=474", "/feed/"]
    key_pages += [f"/category/{c['slug']}/" for c in cats]
    for path in key_pages:
        r = get(BASE + path)
        if r is not None and r.status_code == 200:
            fn = re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_") or "home"
            (html_dir / f"{fn}.html").write_text(r.text)

    # Collect upload URLs
    urls = set()
    blobs = [json.dumps(posts), json.dumps(pages), json.dumps(media)]
    blobs += [p.read_text() for p in html_dir.glob("*.html")]
    for blob in blobs:
        for u in UPLOAD_RE.findall(blob.replace("\\/", "/")):
            u = u.split("?")[0].split("#")[0].rstrip("\\,.;")
            urls.add(u)
            urls.add(SIZE_SUFFIX.sub("", u))  # original, if the referenced one is a thumbnail
    for m in media:
        if m.get("source_url"):
            urls.add(m["source_url"])

    originals = sorted(u for u in urls if not SIZE_SUFFIX.search(u))
    for u in originals:
        rel = urllib.parse.unquote(u.split("/wp-content/uploads/")[1])
        download(u, RAW / "uploads" / rel)

    # Sized variants that have no original (rare): keep them too
    for u in sorted(urls):
        if SIZE_SUFFIX.search(u):
            orig = SIZE_SUFFIX.sub("", u)
            rel_o = urllib.parse.unquote(orig.split("/wp-content/uploads/")[1])
            if not (RAW / "uploads" / rel_o).exists():
                rel = urllib.parse.unquote(u.split("/wp-content/uploads/")[1])
                download(u, RAW / "uploads" / rel)

    # Embeds + YouTube thumbnails
    embeds = {}
    for p in posts + pages:
        html = (p.get("content") or {}).get("rendered", "")
        embeds[p["id"]] = {
            "slug": p.get("slug"),
            "iframes": IFRAME_RE.findall(html),
            "youtube": sorted(set(YT_RE.findall(html))),
        }
    save_json("embeds.json", embeds)
    yt_ids = sorted({i for e in embeds.values() for i in e["youtube"]})
    for vid in yt_ids:
        ok = False
        for q in ("maxresdefault", "sddefault", "hqdefault"):
            r = get(f"https://i.ytimg.com/vi/{vid}/{q}.jpg")
            if r is not None and r.status_code == 200 and len(r.content) > 5000:
                d = RAW / "yt" / f"{vid}.jpg"
                d.parent.mkdir(parents=True, exist_ok=True)
                d.write_bytes(r.content)
                REPORT["downloaded"].append({"url": r.url, "path": str(d), "bytes": len(r.content)})
                ok = True
                break
        if not ok:
            REPORT["failed"].append({"url": f"yt:{vid}"})
        # oEmbed title/author for the record
        r = get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"})
        if r is not None and r.status_code == 200:
            (RAW / "yt" / f"{vid}.json").write_text(r.text)

    # Split big files so git accepts them
    for f in sorted(RAW.rglob("*")):
        if f.is_file() and f.stat().st_size > 95 * 1024 * 1024:
            os.system(f"split -b 90m -d '{f}' '{f}.part'")
            f.unlink()
            REPORT["split"].append(str(f))

    REPORT["counts"] = {"posts": len(posts), "pages": len(pages), "categories": len(cats),
                        "tags": len(tags), "media": len(media), "youtube": len(yt_ids)}
    save_json("report.json", REPORT)
    print(json.dumps(REPORT["counts"]), "downloaded", len(REPORT["downloaded"]), "failed", len(REPORT["failed"]))


if __name__ == "__main__":
    main()
