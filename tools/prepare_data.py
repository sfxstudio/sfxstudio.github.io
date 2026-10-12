#!/usr/bin/env python3
"""Turn the legacy WordPress dump into clean site data (data/site.json).

Input: a folder with the dump produced by tools/import_legacy.py
       (wp/*.json and raw/uploads/...).  Usage:
    python3 tools/prepare_data.py /path/to/legacy
Nothing is invented here: titles, dates, texts, effect lists and video links
come from the old site as-is; only markup noise is removed.
"""
import html
import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "legacy")

CAT = {  # WP category id -> (site key, label)
    3: ("snow", "Снег и лёд"),
    5: ("rain", "Дождь и вода"),
    19: ("wind", "Ветер"),
    20: ("smoke", "Дым, туман, пар"),
    30: ("fire", "Огонь"),
    43: ("special", "Оригинальные эффекты"),
    85: ("decor", "Декорирование"),
    23: ("trailers", "Трейлеры к фильмам"),
    25: ("clips", "Клипы и передачи"),
    17: ("backstage", "Фильмы о фильмах"),
    8: ("news", "Новости"),
}

posts = json.loads((SRC / "wp/posts.json").read_text())
tags = {t["id"]: {"slug": t["slug"], "name": html.unescape(t["name"])} for t in json.loads((SRC / "wp/tags.json").read_text())}
media = {m["id"]: m for m in json.loads((SRC / "wp/media.json").read_text())}


def text(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def upload_rel(url):
    return urllib.parse.unquote(url.split("/wp-content/uploads/")[1])


YT = re.compile(r"(?:youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=)|youtu\.be/)([A-Za-z0-9_-]{11})")
VK = re.compile(r"https?://vk\.com/video_ext\.php\?[^\"'\s<>]+")
VID = re.compile(r"https?://[^\"'\s<>]+/wp-content/uploads/[^\"'\s<>]+\.(?:mp4|mkv|webm|mov)", re.I)


def clean_paragraphs(h):
    """Paragraph texts with internal links kept as (text, href) runs."""
    h = re.sub(r"<iframe.*?</iframe>", "", h, flags=re.S | re.I)
    h = re.sub(r"<(video|figure)[^>]*>.*?</\1>", "", h, flags=re.S | re.I)
    h = re.sub(r"<a[^>]*savefrom[^>]*>.*?</a>", "", h, flags=re.S | re.I)
    out = []
    for block in re.findall(r"<p[^>]*>(.*?)</p>|<li[^>]*>(.*?)</li>", h, flags=re.S | re.I):
        b = block[0] or block[1]
        b = re.sub(r"<br\s*/?>", " ", b)
        runs, pos = [], 0
        for m in re.finditer(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", b, flags=re.S | re.I):
            before = text(b[pos:m.start()])
            if before:
                runs.append([before, None])
            label = text(m.group(2))
            href = html.unescape(m.group(1))
            if label:
                runs.append([label, href])
            pos = m.end()
        tail = text(b[pos:])
        if tail:
            runs.append([tail, None])
        joined = " ".join(r[0] for r in runs).strip()
        if joined:
            out.append(runs)
    return out


def split_title(t):
    t = html.unescape(t).replace(" ", " ").strip()
    m = re.match(r"^(.*?)\s+[—–-]\s+(.+)$", t)
    if m:
        return t, m.group(1).strip(), m.group(2).strip()
    return t, t, ""


items = []
for p in posts:
    c = p["content"]["rendered"]
    cats = [CAT[i][0] for i in p["categories"] if i in CAT]
    full, project, subtitle = split_title(p["title"]["rendered"])
    paras = clean_paragraphs(c)
    effects = ""
    body = []
    for runs in paras:
        line = " ".join(r[0] for r in runs)
        m = re.match(r"^\s*[CС]пецэффекты\s*:\s*(.+)$", line, flags=re.I)
        if m and not effects:
            effects = m.group(1).strip().rstrip(".")
            continue
        body.append(runs)
    video = None
    yt = YT.findall(c)
    vk = VK.findall(c)
    mp = VID.findall(c)
    if mp:
        video = {"type": "mp4", "src": upload_rel(mp[0])}
    elif vk:
        video = {"type": "vk", "src": html.unescape(vk[0]).replace("&#038;", "&")}
    elif yt:
        video = {"type": "yt", "src": yt[0]}
    feat = None
    try:
        fm = p["_embedded"]["wp:featuredmedia"][0]
        feat = upload_rel(fm["source_url"])
    except (KeyError, IndexError):
        pass
    items.append({
        "id": p["id"],
        "slug": urllib.parse.unquote(p["slug"]),
        "date": p["date"][:10],
        "title": full,
        "project": project,
        "subtitle": subtitle,
        "kind": "news" if cats == ["news"] or (cats and set(cats) <= {"news"}) else "work",
        "cats": [c for c in cats if c != "news"],
        "tags": [tags[t] for t in p["tags"] if t in tags],
        "effects": effects,
        "body": body,
        "video": video,
        "image": feat,
    })

# Map news -> the work they point to ("Посмотреть" links)
by_slug = {i["slug"]: i for i in items}
for i in items:
    if i["kind"] != "news":
        continue
    for runs in i["body"]:
        for t, href in runs:
            if href:
                path = urllib.parse.urlparse(href).path.strip("/")
                if path in by_slug and by_slug[path]["kind"] == "work":
                    i.setdefault("links_to", path)

items.sort(key=lambda x: (x["date"], x["id"]), reverse=True)
(ROOT / "data").mkdir(exist_ok=True)
(ROOT / "data/site.json").write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1))
w = [i for i in items if i["kind"] == "work"]
print("works", len(w), "news", len(items) - len(w),
      "video:", {k: sum(1 for i in items if i["video"] and i["video"]["type"] == k) for k in ("mp4", "vk", "yt")},
      "no video", sum(1 for i in w if not i["video"]), "no effects line", sum(1 for i in w if not i["effects"]))
