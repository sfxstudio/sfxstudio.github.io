#!/usr/bin/env python3
"""Build web media from the legacy uploads.

    python3 tools/media.py /path/to/legacy [images|video|all]

- Post cover photos -> assets/img/p/<id>-<w>.webp (480/960/1440, never upscaled)
- Effect clips hosted on the old site -> assets/video/clips/<slug>.mp4 (720p H.264)
- Hero montage (five real shots, one per element) -> assets/video/hero-*.mp4
- Short muted loops for the element chapters -> assets/video/loops/<key>.mp4
- Showreel -> assets/video/showreel.mp4
Photos keep their original framing and colour; only size and format change.
"""
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "legacy") / "raw/uploads"
MODE = sys.argv[2] if len(sys.argv) > 2 else "all"
IMG = ROOT / "assets/img/p"
VID = ROOT / "assets/video"

# Real shots from the studio's own clips: (element, file, start, duration, credit)
HERO = [
    ("snow", "2023/03/lod-iskusstvennyy-sneg.mp4", 120.4, 3.4, "Лёд 2"),
    ("rain", "2023/10/Legenda-№17.mkv", 5.0, 3.4, "Легенда №17"),
    ("wind", "2024/02/dve-zhenshchiny-veter.mkv", 30.6, 3.4, "Две женщины"),
    ("smoke", "2022/04/the_last_bogatyr_smoke.mp4", 1.3, 3.4, "Последний богатырь"),
    ("fire", "2023/12/Чернобыль_огонь.mp4", 11.8, 3.6, "Чернобыль: Зона отчуждения"),
]
LOOPS = {
    "snow": ("2023/03/horde_snow.mp4", 15.0, 6),
    "rain": ("2024/02/best_day_rain.mp4", 40.5, 6),
    "wind": ("2024/02/dve-zhenshchiny-veter.mkv", 35.0, 6),
    "smoke": ("2022/02/mayskiye-lenty-tyazhelyy-dym.mp4", 4.5, 6),
    "fire": ("2022/04/the_last_bogatyr_fire.mp4", 12.0, 6),
    "special": ("2022/02/Bank-Point-Love-can-not-be-copied.mp4", 45.7, 3.2),
}


def content_crop(src, ss, d):
    """ffmpeg cropdetect over the segment -> 'crop=w:h:x:y' without letterbox bars."""
    out = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(ss), "-t", str(d), "-i", str(src), "-vf",
                          "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    found = [l.split("crop=")[-1].strip() for l in out.splitlines() if "crop=" in l]
    return "crop=" + found[-1] if found else "null"


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def trim_letterbox(im):
    """Cut baked-in black bars (video stills often have them). Framing of the
    picture itself is untouched."""
    g = im.convert("L")
    w, h = g.size
    small = g.resize((64, h)) if w > 64 else g
    rows = [max(small.crop((0, y, small.width, y + 1)).getdata()) for y in range(h)]
    top = 0
    while top < h // 3 and rows[top] < 28:
        top += 1
    bottom = h
    while bottom > h * 2 // 3 and rows[bottom - 1] < 28:
        bottom -= 1
    if (top + (h - bottom)) > h * 0.04 and bottom - top > h * 0.4:
        return im.crop((0, top, w, bottom))
    return im


def image_job(item):
    pid, rel, sizes = item
    src = SRC / rel
    if not src.exists():
        return pid, None
    im = Image.open(src)
    im = im.convert("RGB")
    im = trim_letterbox(im)
    out = []
    for w in sizes:
        if w > im.width and out:
            continue
        tw = min(w, im.width)
        th = round(im.height * tw / im.width)
        dst = IMG / f"{pid}-{w}.webp"
        if not dst.exists():
            im.resize((tw, th), Image.LANCZOS).save(dst, "WEBP", quality=74, method=6)
        out.append(w)
    return pid, {"w": im.width, "h": im.height, "sizes": out}


def images():
    IMG.mkdir(parents=True, exist_ok=True)
    data = json.loads((ROOT / "data/site.json").read_text())
    jobs = []
    for it in data["items"]:
        if it["image"]:
            sizes = [480, 960, 1440] if it["kind"] == "work" else [480, 960]
            jobs.append((it["id"], it["image"], sizes))
    meta = {}
    with ProcessPoolExecutor() as ex:
        for pid, m in ex.map(image_job, jobs, chunksize=4):
            if m:
                meta[str(pid)] = m
    (ROOT / "data/images.json").write_text(json.dumps(meta, indent=0))
    print("images", len(meta), "of", len(jobs))


def video():
    (VID / "clips").mkdir(parents=True, exist_ok=True)
    (VID / "loops").mkdir(parents=True, exist_ok=True)
    data = json.loads((ROOT / "data/site.json").read_text())
    # Hero montage: hard cuts, no sound, two sizes
    for width, crf, name in ((1280, 26, "hero-1280"), (720, 28, "hero-720")):
        dst = VID / f"{name}.mp4"
        if dst.exists():
            continue
        parts = []
        for i, (_, f, ss, d, _) in enumerate(HERO):
            part = VID / f"_part{i}.mp4"
            ff("-ss", str(ss), "-t", str(d), "-i", str(SRC / f), "-an",
               "-vf", f"{content_crop(SRC / f, ss, d)},scale={width}:{width * 9 // 16}:force_original_aspect_ratio=increase:flags=lanczos,"
                     f"crop={width}:{width * 9 // 16},fps=25,setsar=1", "-c:v", "libx264", "-preset", "slow",
               "-crf", str(crf), "-pix_fmt", "yuv420p", str(part))
            parts.append(part)
        lst = VID / "_list.txt"
        lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
        ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(dst))
        for p in parts:
            p.unlink()
        lst.unlink()
    for name, crf in (("hero-1280", 38), ("hero-720", 40)):
        webm = VID / f"{name}.webm"
        if not webm.exists():
            ff("-i", str(VID / f"{name}.mp4"), "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", str(crf), "-row-mt", "1",
               "-deadline", "good", "-cpu-used", "4", "-an", str(webm))
    poster = VID / "hero-poster.webp"
    if not poster.exists():
        ff("-ss", "1.2", "-i", str(VID / "hero-1280.mp4"), "-frames:v", "1", "-quality", "70", str(poster))
    (ROOT / "data/hero.json").write_text(json.dumps(
        [{"key": k, "start": round(sum(h[3] for h in HERO[:i]), 2), "credit": c} for i, (k, _, _, _, c) in enumerate(HERO)],
        ensure_ascii=False))
    for key, (f, ss, d) in LOOPS.items():
        dst = VID / "loops" / f"{key}.mp4"
        if not dst.exists():
            ff("-ss", str(ss), "-t", str(d), "-i", str(SRC / f), "-an", "-vf",
               f"{content_crop(SRC / f, ss, d)},scale=960:600:force_original_aspect_ratio=increase:flags=lanczos,crop=960:600,fps=25",
               "-c:v", "libx264", "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst))
        p = VID / "loops" / f"{key}.webp"
        if not p.exists():
            ff("-ss", "1", "-i", str(dst), "-frames:v", "1", "-quality", "70", str(p))
    sr = VID / "showreel.mp4"
    if not sr.exists():
        ff("-i", str(SRC / "2022/09/showreel.mp4"), "-c:v", "libx264", "-preset", "slow", "-crf", "29",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "112k", "-movflags", "+faststart", str(sr))
        ff("-ss", "178", "-i", str(sr), "-frames:v", "1", "-quality", "72", str(VID / "showreel.webp"))
    # Clips that only lived on the old server
    for it in data["items"]:
        v = it["video"]
        if not v or v["type"] != "mp4":
            continue
        dst = VID / "clips" / f"{it['slug']}.mp4"
        poster = VID / "clips" / f"{it['slug']}.webp"
        if not dst.exists():
            ff("-i", str(SRC / v["src"]), "-vf", "scale=-2:'min(720,ih)'", "-c:v", "libx264", "-preset", "medium",
               "-crf", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(dst))
        if not poster.exists():
            ff("-ss", "3", "-i", str(dst), "-frames:v", "1", "-vf", "scale=960:-2", "-quality", "74", str(poster))
    print("video done")


if __name__ == "__main__":
    if MODE in ("images", "all"):
        images()
    if MODE in ("video", "all"):
        video()
