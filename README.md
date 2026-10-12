# SFX Studio — sfxstudio.github.io

Сайт студии практических спецэффектов: снег, дождь, ветер, дым, огонь и оригинальные эффекты для кино, сериалов, рекламы и клипов.

Сайт статический: GitHub Pages публикует содержимое ветки `main` как есть, без сборки на сервере. HTML генерируется локально скриптом и коммитится вместе с исходниками.

## Структура

| Путь | Что это |
|---|---|
| `index.html`, `works/`, `effects/`, `news/`, `about-us/`, `contacts/`, `showreel/`, `katok/`, `404.html`, `sitemap.xml`, `robots.txt`, `feed.xml` | Сгенерированные страницы. Руками не править — перезапишутся |
| `assets/css/site.css` | Дизайн-система: токены цвета, типографики, отступов, движения |
| `assets/js/site.js` | Взаимодействия: синхронизация первого экрана с видео, главы стихий, фильтры архива, плеер, форма |
| `assets/js/vendor/` | GSAP 3.15 + ScrollTrigger |
| `assets/fonts/` | Fira Sans Extra Condensed, Golos Text, IBM Plex Mono (кириллица + латиница, лицензия OFL — файлы `*-LICENSE.txt`) |
| `assets/img/p/` | Обложки работ и новостей в WebP (480/960/1440) |
| `assets/video/` | Монтаж первого экрана, петли стихий, шоурил, ролики работ |
| `data/site.json` | Все работы и новости со старого сайта (тексты, даты, эффекты, видео) |
| `tools/` | Импорт, подготовка данных, медиа и генератор страниц + шаблоны Jinja |

## Как обновить сайт

Нужны Python 3 с `jinja2` и `Pillow`, для видео — `ffmpeg`.

```bash
# правка шаблонов, текстов разделов (tools/build.py: EFFECTS, FEATURED) или стилей
python3 tools/build.py
```

Добавить работу: дописать объект в `data/site.json` (по образцу соседних: `slug`, `date`, `title`, `project`, `subtitle`, `kind: "work"`, `cats`, `effects`, `video`, `image`), положить обложку в `assets/img/p/<id>-960.webp` и пересобрать.

Полный перенос со старого WordPress (уже выполнен):

```bash
python3 tools/import_legacy.py                  # дамп REST API и файлов uploads -> legacy/
python3 tools/prepare_data.py legacy            # -> data/site.json
python3 tools/media.py legacy                   # -> assets/img, assets/video
python3 tools/build.py                          # -> HTML
```

Исходные файлы старого сайта (фото, видео, JSON) лежат в ветке `legacy-import`. Шоурил там разбит на части по 90 МБ: `cat showreel.mp4.part* > showreel.mp4`.

## Домен

Сейчас сайт публикуется на https://sfxstudio.github.io. Чтобы перевести на sfxstudio.ru:

1. Поменять `SITE_URL` в `tools/build.py` и пересобрать (canonical, sitemap, Open Graph).
2. Добавить файл `CNAME` с `sfxstudio.ru`.
3. Настроить DNS у регистратора по инструкции GitHub Pages.

Старые адреса WordPress (`/otpechatki-treyler/`, `/category/snow/`, `/tag/…`, `/feed/`) обрабатывает `404.html`: он перенаправляет на новые страницы.

## Форма

Бэкенда нет, поэтому форма собирает письмо и открывает почтовую программу посетителя с готовым текстом на info@sfxstudio.ru. Чтобы заявки приходили без почтовой программы, нужен внешний сервис форм (например, Formspree или свой обработчик). Его адрес подставляется в `action` в `tools/templates/_form.html`. Ключи в код не класть.
