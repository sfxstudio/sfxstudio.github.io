#!/usr/bin/env python3
"""Static site generator for sfxstudio.github.io.

    python3 tools/build.py

Reads data/site.json (+ images.json, hero.json) and renders HTML with the
Jinja templates in tools/templates. Output goes straight into the repository
root, so GitHub Pages serves it without any build step.
"""
import hashlib
import json
from email.utils import format_datetime
from datetime import datetime, timezone
import re
import shutil
from collections import Counter
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = "https://sfxstudio.github.io"
PHONE = "+7 (925) 543-51-60"
PHONE_HREF = "tel:+79255435160"
EMAIL = "info@sfxstudio.ru"
YOUTUBE = "https://www.youtube.com/channel/UCW2VbMPanQ_vsbCBq9C0hIA"
GENERATED = ["index.html", "404.html", "sitemap.xml", "robots.txt", "feed.xml", "works", "effects", "news",
             "about-us", "contacts", "showreel", "katok"]

data = json.loads((ROOT / "data/site.json").read_text())
images = json.loads((ROOT / "data/images.json").read_text())
hero = json.loads((ROOT / "data/hero.json").read_text()) if (ROOT / "data/hero.json").exists() else []
items = data["items"]
works = [i for i in items if i["kind"] == "work"]
news = [i for i in items if i["kind"] == "news"]
by_slug = {i["slug"]: i for i in items}

# --- Effect chapters. Texts follow the studio's own "О нас" page; lists use
#     effect names that appear as tags on real projects of the archive.
EFFECTS = [
    {
        "key": "snow", "name": "Снег и лёд", "short": "Снег", "num": "01",
        "lead": "Зима в любое время года — в павильоне и на натуре.",
        "text": "Декорируем помещения, отдельные предметы и открытые пространства искусственным снегом. "
                "Наметаем сугробы и снежные наносы, запускаем падающий снег с хлопьями разного объёма. "
                "Покрываем инеем окна и поверхности, развешиваем сосульки, создаём ледяные поверхности "
                "и имитируем проваливание под лёд. Отдельно — эффект обморожения лица и рук.",
        "list": ["Декорирование искусственным снегом", "Падающий снег", "Сугробы и наносы", "Метель и пурга",
                 "Иней на стекле", "Сосульки", "Ледяные поверхности", "Прорубь на льду", "Обморожение", "Снежки"],
        "loop": "snow", "loop_credit": "«Орда», 2013",
    },
    {
        "key": "rain", "name": "Дождь и вода", "short": "Дождь", "num": "02",
        "lead": "Полная иллюзия дождя — от мороси до ливня.",
        "text": "Дождевые стойки и «Hollywood system» дают полную иллюзию дождя на площадке и в помещении. "
                "Делаем водяной пар и взвесь, фонтаны и водопады, капель, течь с потолка и из труб, "
                "выброс воды.",
        "list": ["Дождь на площадке", "«Hollywood system»", "Дождь в помещении", "Водяной пар", "Водяная взвесь",
                 "Фонтаны и водопады", "Капель", "Течь с потолка", "Выброс воды"],
        "loop": "rain", "loop_credit": "«Самый лучший день», 2016",
    },
    {
        "key": "wind", "name": "Ветер", "short": "Ветер", "num": "03",
        "lead": "От развевающихся волос до урагана.",
        "text": "Ветродуи нужной мощности справляются с простыми задачами вроде развевающихся волос. "
                "В связке с другим оборудованием и эффектами они создают иллюзию практически любого "
                "погодного явления: метель, пургу, непогоду, ураган.",
        "list": ["Ветер на площадке", "Ветродуи разной мощности", "Метель", "Непогода", "Ураган"],
        "loop": "wind", "loop_credit": "«Две женщины», 2015",
    },
    {
        "key": "smoke", "name": "Дым, туман, пар", "short": "Дым", "num": "04",
        "lead": "Атмосфера нужной текстуры и плотности.",
        "text": "Дым-машины и генераторы тяжёлого дыма создают атмосферные дымы нужной текстуры и плотности. "
                "Делаем натурные дымы, туман, пар и цветной дым — атмосферу, которую задаёт оператор-постановщик.",
        "list": ["Атмосферные дымы", "Натурные дымы", "Тяжёлый дым", "Туман", "Пар", "Цветной дым",
                 "Источники дыма"],
        "loop": "smoke", "loop_credit": "«Майские ленты», 2015",
    },
    {
        "key": "fire", "name": "Огонь", "short": "Огонь", "num": "05",
        "lead": "Пламя в кадре — под контролем.",
        "text": "Костры и факелы, взрывы и ревущее пламя, а также их последствия: вылетающие двери, окна "
                "и оконные проёмы, ожоги тела, клубы густого разноцветного дыма, падающий пепел. "
                "Имитируем пожар, горящий лес, автомобиль, свечи и чаши, безопасные искры.",
        "list": ["Имитация пожара", "Костёр", "Факелы", "Горящий лес", "Горящий автомобиль", "Горящие чаши",
                 "Горящие свечи", "Безопасные искры", "Пепел", "Короткое замыкание"],
        "loop": "fire", "loop_credit": "«Последний богатырь», 2018",
    },
    {
        "key": "special", "name": "Оригинальные эффекты", "short": "Особое", "num": "06",
        "lead": "Всё, что не помещается в одну стихию.",
        "text": "Бутафорское бьющееся стекло — бутылки и оконное стекло, которое ни при каких условиях не "
                "травмирует актёров и группу. Пух, разноцветная пыль и пепел, пневмооборудование и "
                "пневмовыброс объектов, попадание пуль, выброс крови и краски, конфетти, пена и мыльные пузыри.",
        "list": ["Безопасное стекло", "Пух", "Пыль", "Пневмовыброс объектов", "Попадание пуль", "Выброс крови",
                 "Конфетти", "Пена", "Мыльные пузыри", "Имитация дракона"],
        "loop": "special", "loop_credit": "«Банк Точка», 2019",
    },
]
EFFECT_BY_KEY = {e["key"]: e for e in EFFECTS}
DECOR = {"key": "decor", "name": "Декорирование", "num": "07",
         "lead": "Декорирование зданий и помещений, оформление витрин и фотосессий.",
         "text": "Те же материалы и оборудование, что и на съёмочной площадке, работают для оформления "
                 "зданий, помещений, витрин и фотосессий — прежде всего искусственный снег и иней.",
         "list": ["Декорирование искусственным снегом", "Иней на стекле", "Снег за окном", "Снеговик"]}
SECTIONS = {"trailers": "Трейлеры к фильмам", "clips": "Клипы и передачи", "backstage": "Фильмы о фильмах"}
CAT_LABEL = {**{e["key"]: e["name"] for e in EFFECTS}, "decor": "Декорирование", **SECTIONS}

FEATURED = [
    ("a", "otpechatki-treyler"),
    ("b", "treiler-2-cheburashki-2"),
    ("c", "posledniy-bogatyr-ogon-goryashchiye-chashi"),
    ("d", "moskva-slezam-ne-verit-vse-tol_ko-nachinayetsya-treyler"),
    ("e", "orda-sneg"),
    ("f", "vtb-ottsy-i-deti"),
    ("f", "finist-pervyy-bogatyr-treyler"),
    ("f", "vklyuchay-nashu-denis-maydanov-oleg-gazmanov-vlada-maydanova-rodion-gazmanov"),
]

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
          "ноября", "декабря"]


def ru_date(d):
    y, m, dd = d.split("-")
    return f"{int(dd)} {MONTHS[int(m) - 1]} {y}"


def plural(n, one, few, many):
    n = abs(n) % 100
    if 10 < n < 20:
        return many
    n %= 10
    return one if n == 1 else few if 2 <= n <= 4 else many


def img(item, size=960):
    m = images.get(str(item["id"]))
    if not m:
        return None
    sizes = m["sizes"]
    pick = min((s for s in sizes if s >= size), default=max(sizes))
    return f"/assets/img/p/{item['id']}-{pick}.webp"


def srcset(item):
    m = images.get(str(item["id"]))
    if not m:
        return ""
    out = []
    for s in m["sizes"]:
        real = min(s, m["w"])
        out.append(f"/assets/img/p/{item['id']}-{s}.webp {real}w")
    return ", ".join(out)


def dims(item):
    m = images.get(str(item["id"]))
    return (m["w"], m["h"]) if m else (1280, 720)


def url(item):
    return f"/works/{item['slug']}/" if item["kind"] == "work" else f"/news/{item['slug']}/"


def map_href(href):
    """Old absolute/relative links -> new structure (internal only)."""
    if not href:
        return href
    h = re.sub(r"^https?://(www\.)?sfxstudio\.ru", "", href)
    if h.startswith("http") or h.startswith("mailto:") or h.startswith("tel:"):
        return href
    path = h.split("?")[0].strip("/")
    if path in by_slug:
        return url(by_slug[path])
    if path in ("contacts", "about-us", "showreel", "katok"):
        return f"/{path}/"
    m = re.match(r"category/([^/]+)", path)
    if m:
        return OLD_CAT.get(m.group(1), "/works/")
    return href


OLD_CAT = {"snow": "/effects/snow/", "rain": "/effects/rain/", "wind": "/effects/wind/",
           "smoke": "/effects/smoke/", "fire": "/effects/fire/", "original-special-effects": "/effects/special/",
           "dekorirovaniye-pomeshcheniy": "/effects/decor/", "video-clips": "/works/?cat=clips",
           "treyler-film": "/works/?cat=trailers", "backstage": "/works/?cat=backstage", "news": "/news/"}


def video_info(item):
    v = item.get("video")
    if not v:
        return None
    if v["type"] == "mp4":
        return {"type": "mp4", "src": f"/assets/video/clips/{item['slug']}.mp4", "label": "Видео на сайте студии"}
    if v["type"] == "yt":
        return {"type": "yt", "src": f"https://www.youtube-nocookie.com/embed/{v['src']}?autoplay=1&rel=0",
                "ext": f"https://www.youtube.com/watch?v={v['src']}", "label": "YouTube"}
    if v["type"] == "vk":
        s = v["src"]
        oid = re.search(r"oid=(-?\d+)", s)
        vid = re.search(r"[?&]id=(\d+)", s)
        ext = f"https://vk.com/video{oid.group(1)}_{vid.group(1)}" if oid and vid else None
        return {"type": "vk", "src": s + ("&autoplay=1" if "autoplay" not in s else ""), "ext": ext,
                "label": "VK Видео"}
    return None


def effect_count(key):
    return sum(1 for w in works if key in w["cats"])


tag_counter = Counter()
tag_names = {}
for it in items:
    for t in it["tags"]:
        tag_names[t["slug"]] = t["name"]
for it in works:  # counts must match what the archive filter shows
    for t in it["tags"]:
        tag_counter[t["slug"]] += 1
TOP_TAGS = [(s, tag_names[s], c) for s, c in tag_counter.most_common(30)]

env = Environment(loader=FileSystemLoader(ROOT / "tools/templates"), autoescape=select_autoescape(["html", "xml"]),
                  trim_blocks=True, lstrip_blocks=True)
env.globals.update(PHONE=PHONE, PHONE_HREF=PHONE_HREF, EMAIL=EMAIL, YOUTUBE=YOUTUBE, SITE_URL=SITE_URL,
                   EFFECTS=EFFECTS, DECOR=DECOR, CAT_LABEL=CAT_LABEL, SECTIONS=SECTIONS, img=img, srcset=srcset,
                   dims=dims, url=url, ru_date=ru_date, plural=plural, map_href=map_href, video_info=video_info,
                   effect_count=effect_count, YEAR=date.today().year, N_WORKS=len(works), N_NEWS=len(news),
                   FIRST_YEAR=min(i["date"][:4] for i in items))
env.filters["labels"] = lambda cats: [CAT_LABEL[c] for c in cats if c in CAT_LABEL]
env.globals["VERSION"] = hashlib.sha1(b"".join((ROOT / p).read_bytes() for p in (
    "assets/css/site.css", "assets/js/site.js") if (ROOT / p).exists())).hexdigest()[:8]


SHORT = re.compile(r"(?<![\w\-])([А-Яа-яЁёA-Za-z]{1,2}|[0-9]{1,3})\s+(?=[\w«(\"№0-9])", re.U)
DASH = re.compile(r"\s+(—|–)\s")
SKIP = re.compile(r"(<script\b.*?</script>|<style\b.*?</style>|<[^>]+>)", re.S | re.I)


_ALL = "[а-яё]"
_V = "[аеёиоуыэюя]"
_C = "[бвгджзклмнпрстфхцчшщ]"
_X = "[йъь]"
HYPH = [re.compile(p, re.I) for p in (
    f"({_X})({_ALL}{_ALL})", f"({_V})({_V}{_ALL})", f"({_V}{_C})({_C}{_V})",
    f"({_C}{_V})({_C}{_V})", f"({_V}{_C})({_C}{_C}{_V})", f"({_V}{_C}{_C})({_C}{_C}{_V})")]
WORD = re.compile(r"[А-Яа-яЁё]{5,}")


def hyphenate_word(w):
    """Soft hyphens by Russian syllable rules (Khmelev); never leaves <2 letters on a line."""
    for _ in range(2):
        for rx in HYPH:
            w = rx.sub("\\1\u00ad\\2", w)
    parts = w.split("\u00ad")
    if len(parts) > 1:  # glue too-short head/tail pieces back
        if len(parts[0]) < 2:
            parts[0:2] = [parts[0] + parts[1]]
        if len(parts) > 1 and len(parts[-1]) < 2:
            parts[-2:] = [parts[-2] + parts[-1]]
    return "\u00ad".join(parts)


P_BLOCK = re.compile(r"(<p\b[^>]*>)(.*?)(</p>)", re.S)


def hyphenate_paragraphs(html_text):
    def fix(m):
        inner = SKIP.split(m.group(2))
        for i in range(0, len(inner), 2):
            inner[i] = WORD.sub(lambda w: hyphenate_word(w.group(0)), inner[i])
        return m.group(1) + "".join(inner) + m.group(3)
    return P_BLOCK.sub(fix, html_text)


def typograph(html_text):
    """Tie prepositions/short words to the next word and dashes to the previous one,
    only in visible text (tags, attributes and scripts are left untouched)."""
    parts = SKIP.split(html_text)
    for i in range(0, len(parts), 2):
        t = parts[i]
        if not t.strip():
            continue
        t = DASH.sub("\u00a0\\1 ", t)
        t = SHORT.sub("\\1\u00a0", t)
        t = SHORT.sub("\\1\u00a0", t)  # chains like «и в»
        parts[i] = t
    return "".join(parts)  # no hyphenation: words never break across lines


def write(path, template, **ctx):
    out = ROOT / path
    out.parent.mkdir(parents=True, exist_ok=True)
    self_url = "/" + path[: -len("index.html")] if path.endswith("index.html") else "/" + path
    ctx.setdefault("self_url", self_url)
    out.write_text(typograph(env.get_template(template).render(**ctx)))
    return path


def clean():
    for name in GENERATED:
        p = ROOT / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()


def related(item, n=3):
    pool = [w for w in works if w["id"] != item["id"] and set(w["cats"]) & set(item["cats"])]
    same_proj = [w for w in works if w["id"] != item["id"] and w["project"] == item["project"]]
    seen, out = set(), []
    for w in same_proj + pool:
        if w["id"] not in seen:
            seen.add(w["id"])
            out.append(w)
        if len(out) >= n:
            break
    return out


def main():
    clean()
    pages = []
    featured = [(cls, by_slug[s]) for cls, s in FEATURED if s in by_slug]
    backstage = [w for w in works if "backstage" in w["cats"]]
    pages.append(("/", write("index.html", "index.html", page="home", featured=featured, backstage=backstage,
                             hero=hero, top_tags=TOP_TAGS[:24], latest_news=news[:3],
                             title=None,
                             description="Студия практических спецэффектов: снег, дождь, ветер, дым и огонь на "
                                         "съёмочной площадке для кино, сериалов, рекламы и клипов.")))
    # Archive
    archive_tags = sorted({(t["slug"], t["name"]) for w in works for t in w["tags"]}, key=lambda x: x[1])
    pages.append(("/works/", write("works/index.html", "works.html", page="works", works=works,
                                   tags=archive_tags, title="Работы",
                                   description=f"Архив проектов SFX Studio: {len(works)} работ — фильмы, сериалы, "
                                               "реклама и клипы со спецэффектами на площадке.")))
    for idx, w in enumerate(works):
        prev_w = works[idx - 1] if idx > 0 else None
        next_w = works[idx + 1] if idx + 1 < len(works) else None
        mentions = [n for n in news if n.get("links_to") == w["slug"]]
        desc = (f"{w['title']}. Спецэффекты: {w['effects']}." if w["effects"] else
                f"{w['title']} — спецэффекты на съёмочной площадке от SFX Studio.")
        pages.append((url(w), write(f"works/{w['slug']}/index.html", "work.html", page="works", item=w,
                                    prev_item=prev_w, next_item=next_w, related=related(w), mentions=mentions,
                                    title=w["title"], description=desc, og_image=img(w, 1440))))
    # Effects
    for e in EFFECTS + [DECOR]:
        ws = [w for w in works if e["key"] in w["cats"]]
        pages.append((f"/effects/{e['key']}/", write(f"effects/{e['key']}/index.html", "effect.html", page="effects",
                                                    fx=e, works=ws, title=e["name"],
                                                    description=f"{e['name']}: {e['lead']} Спецэффекты на съёмочной "
                                                                f"площадке от SFX Studio.",
                                                    og_image=img(ws[0], 1440) if ws else None)))
    pages.append(("/effects/", write("effects/index.html", "effects.html", page="effects", title="Эффекты",
                                     description="Снег и лёд, дождь, ветер, дым, огонь и оригинальные спецэффекты "
                                                 "для кино и рекламы.")))
    # News
    pages.append(("/news/", write("news/index.html", "news.html", page="news", news=news, title="Новости",
                                  description="Новости SFX Studio: премьеры и трейлеры проектов со спецэффектами "
                                              "студии.")))
    for n in news:
        target = by_slug.get(n.get("links_to"))
        pages.append((url(n), write(f"news/{n['slug']}/index.html", "news_item.html", page="news", item=n,
                                    target=target, title=n["title"],
                                    description=" ".join(r[0] for r in n["body"][0])[:180] if n["body"] else n["title"],
                                    og_image=img(n, 960))))
    # Static pages
    pages.append(("/about-us/", write("about-us/index.html", "about.html", page="about", title="О студии",
                                      description="SfxStudio.ru — студия спецэффектов для кино, рекламы и клипов: "
                                                  "зимние эффекты, дождь, ветер, дым, пиротехника, стекло, каток.",
                                      og_image="/assets/img/pages/lada-fire-960.webp")))
    pages.append(("/contacts/", write("contacts/index.html", "contacts.html", page="contacts", title="Контакты",
                                      description=f"Связаться с SFX Studio: {PHONE}, {EMAIL}.")))
    pages.append(("/showreel/", write("showreel/index.html", "showreel.html", page="showreel", title="Шоурил",
                                      description="Шоурил SFX Studio — спецэффекты на съёмочной площадке.",
                                      og_image="/assets/video/showreel.webp")))
    pages.append(("/katok/", write("katok/index.html", "katok.html", page="katok", title="Каток",
                                   description="Аренда катка с пластиковым льдом площадью до 220 м².",
                                   og_image="/assets/img/pages/rink-960.webp")))
    # 404 with redirects for every old URL
    redirects = {i["slug"]: url(i) for i in items}
    redirects.update({f"category/{k}": v for k, v in OLD_CAT.items()})
    redirects.update({f"tag/{s}": f"/works/?tag={s}" for s in tag_names})
    redirects.update({"feed": "/feed.xml", "page": "/works/"})
    write("404.html", "404.html", page="404", title="Страница не найдена", redirects=redirects,
          description="Страница не найдена.", noindex=True)
    # robots, sitemap, feed
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n")
    lastmod = {url(i): i["date"] for i in items}
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p, _ in pages:
        lm = lastmod.get(p, str(date.today()))
        sm.append(f"  <url><loc>{SITE_URL}{escape(p)}</loc><lastmod>{lm}</lastmod></url>")
    sm.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(sm) + "\n")
    rss = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
           "<title>SFX Studio — новости</title>", f"<link>{SITE_URL}/news/</link>",
           "<description>Новости студии спецэффектов SFX Studio</description>", "<language>ru</language>"]
    for n in news[:30]:
        body = " ".join(" ".join(r[0] for r in b) for b in n["body"])
        rss.append(f"<item><title>{escape(n['title'])}</title><link>{SITE_URL}{url(n)}</link>"
                   f"<guid>{SITE_URL}{url(n)}</guid>"
                   f"<pubDate>{format_datetime(datetime.fromisoformat(n['date']).replace(tzinfo=timezone.utc))}</pubDate>"
                   f"<description>{escape(body[:400])}</description></item>")
    rss.append("</channel></rss>")
    (ROOT / "feed.xml").write_text("\n".join(rss) + "\n")
    print("pages", len(pages))


if __name__ == "__main__":
    main()
