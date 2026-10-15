#!/usr/bin/env python3
"""Собирает EPUB 3 книги «Неспящие. Книга первая: Мёртвый час» из глав book-1/NN-*.md.

Запуск из корня репозитория:
    python3 tools/build_epub.py                      # без автора
    python3 tools/build_epub.py --author "Имя Фамилия"

Результат: epub/Nespyashchie_1_Myortvyy_chas.epub
"""
import argparse
import datetime
import html
import pathlib
import re
import shutil
import sys
import uuid
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOK_DIR = ROOT / "book-1"
BUILD_DIR = ROOT / "build" / "epub"
OUT_DIR = ROOT / "epub"
OUT_NAME = "Nespyashchie_1_Myortvyy_chas.epub"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import make_cover  # noqa: E402

TITLE = "Мёртвый час"
SERIES = "Неспящие"
SERIES_INDEX = 1
LANG = "ru"
BOOK_ID = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "nespyashchie/book-1/myortvyy-chas"))

PARTS = [
    ("Часть первая", "Наследник", range(1, 6)),
    ("Часть вторая", "Смотритель", range(6, 13)),
    ("Часть третья", "Охота", range(13, 18)),
    ("Часть четвёртая", "Мёртвый час", range(18, 23)),
]

ANNOTATION = [
    "Каждую ночь ровно в три Петербург останавливается. Дождь повисает в воздухе, люди замирают "
    "на полуслове, у застывших нет пульса. Но несколько десятков человек в это время не спят. "
    "У каждого из них — свой завод: у кого-то четыре минуты ночи, у кого-то час. А когда неспящий "
    "умирает, вся его ночь уходит к тому, кто стоит ближе всех.",
    "Фельдшер скорой Глеб Савельев держал за руку умирающего старика-часовщика. Теперь у него самая "
    "длинная ночь в городе — девять часов сорок семь минут. И весь город, который не спит, хочет "
    "его смерти.",
    "Мистический триллер о времени, которое нельзя отдать, не умерев, о человеке, чья работа — "
    "возвращать, и о городе, у которого есть час, которого нет ни на одних часах.",
]

EPIGRAPH = [
    "И во всю ночь безумец бедный,",
    "Куда стопы ни обращал,",
    "За ним повсюду Всадник Медный",
    "С тяжёлым топотом скакал.",
]
EPIGRAPH_SOURCE = "А. С. Пушкин. «Медный всадник»"

NBSP = " "

# Короткие слова, которые не должны висеть в конце строки.
SHORT_WORDS = (
    "в к с у о я и а "
    "на за по до из от об во со ко не ни но да же бы"
).split()
SHORT_RE = re.compile(
    r"(?<![\w\-])(" + "|".join(w + "|" + w.capitalize() for w in SHORT_WORDS) + r") (?=\S)"
)


# ---------------------------------------------------------------- типографика

def typo(text: str) -> str:
    """Неразрывные пробелы по правилам русского набора. Работает по уже экранированному тексту."""
    text = text.replace(" — ", NBSP + "— ")          # тире не начинает строку
    text = re.sub(r"^— ", "—" + NBSP, text)          # реплика в начале абзаца
    text = re.sub(r"(<(?:em|strong)>)— ", r"\1—" + NBSP, text)
    text = text.replace("№ ", "№" + NBSP)
    text = SHORT_RE.sub(lambda m: m.group(1) + NBSP, text)
    return text


def inline(src: str) -> str:
    s = html.escape(src, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return typo(s)


def plain(src: str) -> str:
    """Текст без разметки — для оглавлений и метаданных."""
    return re.sub(r"\*+", "", src)


# ---------------------------------------------------------------- разбор глав

class Chapter:
    def __init__(self, num, title, blocks, fname):
        self.num = num
        self.title = title
        self.blocks = blocks
        self.fname = fname

    @property
    def label(self):
        return f"Глава {self.num}"


HEAD_RE = re.compile(r"^##\s+Глава\s+(\d+)\.\s+(.+?)\s*$")


def read_chapters():
    chapters = []
    for path in sorted(BOOK_DIR.glob("[0-9][0-9]-*.md")):
        if path.name.startswith("00-"):
            continue
        raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        num = title = None
        body_lines = []
        for line in raw.split("\n"):
            if line.startswith("# "):            # заголовок части — свои страницы
                continue
            m = HEAD_RE.match(line)
            if m and num is None:
                num, title = int(m.group(1)), m.group(2)
                continue
            body_lines.append(line)
        if num is None:
            raise SystemExit(f"Нет заголовка главы в {path}")
        blocks = [b.strip("\n") for b in re.split(r"\n[ \t]*\n", "\n".join(body_lines))]
        blocks = [b for b in blocks if b.strip()]
        chapters.append(Chapter(num, title, blocks, f"ch{num:02d}.xhtml"))
    nums = [c.num for c in chapters]
    if nums != list(range(1, len(nums) + 1)):
        raise SystemExit(f"Главы идут не по порядку: {nums}")
    return chapters


def render_blocks(blocks):
    out = []
    first = True
    the_end = False
    for b in blocks:
        s = b.strip()
        if s == "---":
            out.append('<p class="scene-break" role="separator">* * *</p>')
            first = True
            continue
        if s == "&nbsp;":
            out.append('<div class="spacer"></div>')
            the_end = True
            continue
        lines = [ln.strip() for ln in s.split("\n")]
        all_bold = all(re.fullmatch(r"\*\*.+\*\*", ln) for ln in lines)
        if the_end:
            cls = "center the-end"
        elif all_bold:
            cls = "center"
        elif first:
            cls = "first"
        else:
            cls = None
        content = "<br/>".join(inline(ln) for ln in lines)
        attr = f' class="{cls}"' if cls else ""
        out.append(f"<p{attr}>{content}</p>")
        first = False
    return "\n".join(out)


# ---------------------------------------------------------------- XHTML

def xhtml(title, body, body_type=None, body_class=None):
    attrs = ""
    if body_type:
        attrs += f' epub:type="{body_type}"'
    if body_class:
        attrs += f' class="{body_class}"'
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{LANG}" lang="{LANG}">
<head>
<meta charset="utf-8"/>
<title>{html.escape(title)}</title>
<link rel="stylesheet" type="text/css" href="../styles/book.css"/>
</head>
<body{attrs}>
{body}
</body>
</html>
"""


def chapter_page(ch):
    head = (
        f'<header class="chapter-head">\n'
        f'<p class="chapter-num">{ch.label}</p>\n'
        f'<h2 class="chapter-title" id="title">{inline(ch.title)}</h2>\n'
        f"</header>"
    )
    body = (
        f'<section epub:type="chapter" role="doc-chapter" aria-labelledby="title">\n'
        f"{head}\n{render_blocks(ch.blocks)}\n</section>"
    )
    return xhtml(f"{ch.label}. {plain(ch.title)}", body, body_type="bodymatter")


def part_page(idx, num_label, name):
    body = (
        f'<section epub:type="part" role="doc-part" class="part-page" aria-labelledby="title">\n'
        f'<p class="part-num">{num_label}</p>\n'
        f'<h1 class="part-title" id="title">{inline(name)}</h1>\n'
        f'<p class="ornament" aria-hidden="true">✶</p>\n'
        f"</section>"
    )
    return xhtml(f"{num_label}. {name}", body, body_type="bodymatter")


def cover_page():
    w, h = make_cover.W, make_cover.H
    body = (
        '<section epub:type="cover" class="cover">\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'version="1.1" width="100%" height="100%" viewBox="0 0 {w} {h}" '
        f'preserveAspectRatio="xMidYMid meet">\n'
        f'<image width="{w}" height="{h}" xlink:href="../images/cover.jpg"/>\n'
        "</svg>\n</section>"
    )
    return xhtml(f"{SERIES}. {TITLE}", body, body_type="frontmatter", body_class="cover-body")


def title_page(author):
    author_html = f'<p class="tp-author">{inline(author)}</p>\n' if author else ""
    body = (
        '<section epub:type="titlepage" class="title-page" aria-label="Титульный лист">\n'
        f"{author_html}"
        f'<p class="tp-series">{SERIES}</p>\n'
        '<p class="tp-rule" aria-hidden="true">— ✶ —</p>\n'
        f'<h1 class="tp-title">{TITLE}</h1>\n'
        '<p class="tp-book">Книга первая</p>\n'
        '<p class="tp-genre">Роман</p>\n'
        "</section>"
    )
    return xhtml(TITLE, body, body_type="frontmatter")


def epigraph_page():
    verses = "<br/>".join(inline(v) for v in EPIGRAPH)
    body = (
        '<section epub:type="epigraph" role="doc-epigraph" class="epigraph-page" aria-label="Эпиграф">\n'
        f'<blockquote class="epigraph">\n<p class="verse">{verses}</p>\n'
        f'<p class="source">{inline(EPIGRAPH_SOURCE)}</p>\n</blockquote>\n'
        "</section>"
    )
    return xhtml("Эпиграф", body, body_type="frontmatter")


def annotation_page():
    paras = "\n".join(
        f'<p{" class=\"first\"" if i == 0 else ""}>{inline(p)}</p>' for i, p in enumerate(ANNOTATION)
    )
    body = (
        '<section epub:type="abstract" class="annotation" aria-labelledby="title">\n'
        '<h2 class="annotation-title" id="title">Аннотация</h2>\n'
        f"{paras}\n</section>"
    )
    return xhtml("Аннотация", body, body_type="frontmatter")


def nav_page(chapters):
    by_num = {c.num: c for c in chapters}
    items = []
    for i, (num_label, name, rng) in enumerate(PARTS, start=1):
        sub = "\n".join(
            f'<li><a href="text/{by_num[n].fname}">{by_num[n].label}. {inline(by_num[n].title)}</a></li>'
            for n in rng
        )
        items.append(
            f'<li><a href="text/part{i}.xhtml">{num_label}. {inline(name)}</a>\n<ol>\n{sub}\n</ol>\n</li>'
        )
    toc = "\n".join(items)
    body = f"""<nav epub:type="toc" id="toc" role="doc-toc" aria-labelledby="toc-title">
<h2 class="toc-title" id="toc-title">Содержание</h2>
<ol>
<li><a href="text/annotation.xhtml">Аннотация</a></li>
{toc}
</ol>
</nav>
<nav epub:type="landmarks" id="landmarks" hidden="hidden">
<h2>Ориентиры</h2>
<ol>
<li><a epub:type="cover" href="text/cover.xhtml">Обложка</a></li>
<li><a epub:type="titlepage" href="text/title.xhtml">Титульный лист</a></li>
<li><a epub:type="toc" href="nav.xhtml">Содержание</a></li>
<li><a epub:type="bodymatter" href="text/part1.xhtml">Начало книги</a></li>
</ol>
</nav>"""
    page = xhtml("Содержание", body, body_type="frontmatter")
    return page.replace('href="../styles/book.css"', 'href="styles/book.css"')


def ncx(chapters):
    by_num = {c.num: c for c in chapters}
    order = 0
    points = []

    def nav_point(pid, label, src, children=""):
        nonlocal order
        order += 1
        return (
            f'<navPoint id="{pid}" playOrder="{order}">'
            f"<navLabel><text>{html.escape(label)}</text></navLabel>"
            f'<content src="{src}"/>{children}</navPoint>'
        )

    points.append(nav_point("np-annotation", "Аннотация", "text/annotation.xhtml"))
    for i, (num_label, name, rng) in enumerate(PARTS, start=1):
        # playOrder идёт по порядку чтения: сначала страница части, потом её главы
        order += 1
        part_order = order
        kids = "".join(
            nav_point(f"np-ch{n:02d}", f"{by_num[n].label}. {plain(by_num[n].title)}",
                      f"text/{by_num[n].fname}")
            for n in rng
        )
        points.append(
            f'<navPoint id="np-part{i}" playOrder="{part_order}">'
            f"<navLabel><text>{html.escape(num_label + '. ' + name)}</text></navLabel>"
            f'<content src="text/part{i}.xhtml"/>{kids}</navPoint>'
        )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="{LANG}">
<head>
<meta name="dtb:uid" content="{BOOK_ID}"/>
<meta name="dtb:depth" content="2"/>
<meta name="dtb:totalPageCount" content="0"/>
<meta name="dtb:maxPageNumber" content="0"/>
</head>
<docTitle><text>{html.escape(SERIES + ". " + TITLE)}</text></docTitle>
<navMap>
{chr(10).join(points)}
</navMap>
</ncx>
"""


def opf(chapters, author, modified):
    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="css" href="styles/book.css" media-type="text/css"/>',
        '<item id="cover-image" href="images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>',
        '<item id="cover" href="text/cover.xhtml" media-type="application/xhtml+xml" properties="svg"/>',
        '<item id="title" href="text/title.xhtml" media-type="application/xhtml+xml"/>',
        '<item id="epigraph" href="text/epigraph.xhtml" media-type="application/xhtml+xml"/>',
        '<item id="annotation" href="text/annotation.xhtml" media-type="application/xhtml+xml"/>',
    ]
    spine = [
        '<itemref idref="cover"/>',
        '<itemref idref="title"/>',
        '<itemref idref="epigraph"/>',
        '<itemref idref="annotation"/>',
        '<itemref idref="nav"/>',
    ]
    by_num = {c.num: c for c in chapters}
    for i, (_, _, rng) in enumerate(PARTS, start=1):
        manifest.append(f'<item id="part{i}" href="text/part{i}.xhtml" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="part{i}"/>')
        for n in rng:
            manifest.append(
                f'<item id="ch{n:02d}" href="text/{by_num[n].fname}" media-type="application/xhtml+xml"/>'
            )
            spine.append(f'<itemref idref="ch{n:02d}"/>')

    creator = ""
    if author:
        creator = (
            f'<dc:creator id="creator">{html.escape(author)}</dc:creator>\n'
            '<meta refines="#creator" property="role" scheme="marc:relators">aut</meta>\n'
        )
    description = html.escape(" ".join(ANNOTATION))
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="{LANG}">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">{BOOK_ID}</dc:identifier>
<dc:title id="maintitle">{html.escape(TITLE)}</dc:title>
<meta refines="#maintitle" property="title-type">main</meta>
<dc:language>{LANG}</dc:language>
{creator}<dc:description>{description}</dc:description>
<dc:subject>Мистический триллер</dc:subject>
<dc:subject>Городское фэнтези</dc:subject>
<dc:date>{modified[:10]}</dc:date>
<meta property="dcterms:modified">{modified}</meta>
<meta property="belongs-to-collection" id="series">{html.escape(SERIES)}</meta>
<meta refines="#series" property="collection-type">series</meta>
<meta refines="#series" property="group-position">{SERIES_INDEX}</meta>
<meta name="cover" content="cover-image"/>
<meta name="calibre:series" content="{html.escape(SERIES)}"/>
<meta name="calibre:series_index" content="{SERIES_INDEX}"/>
</metadata>
<manifest>
{chr(10).join(manifest)}
</manifest>
<spine toc="ncx">
{chr(10).join(spine)}
</spine>
</package>
"""


CONTAINER = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles>
<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
</rootfiles>
</container>
"""

CSS = """@charset "utf-8";

html { font-size: 100%; }

body {
  margin: 0;
  padding: 0 2%;
  font-family: serif;
  line-height: 1.45;
  orphans: 2;
  widows: 2;
  -webkit-hyphens: auto;
  -epub-hyphens: auto;
  adobe-hyphenate: auto;
  hyphens: auto;
}

p {
  margin: 0;
  text-indent: 1.5em;
  text-align: justify;
}

p.first { text-indent: 0; }

p.center {
  text-indent: 0;
  text-align: center;
  margin: 0.8em 0;
  -webkit-hyphens: none;
  hyphens: none;
}

p.the-end { margin: 0.4em 0; }

p.scene-break {
  text-indent: 0;
  text-align: center;
  margin: 1.3em 0;
}

.spacer { height: 3em; }

em { font-style: italic; }
strong { font-weight: bold; }

h1, h2 {
  font-weight: normal;
  -webkit-hyphens: none;
  hyphens: none;
  page-break-after: avoid;
  break-after: avoid;
}

/* Главы */
.chapter-head {
  margin: 3em 0 2.4em;
  text-align: center;
  page-break-inside: avoid;
  break-inside: avoid;
}

.chapter-num {
  text-indent: 0;
  text-align: center;
  font-size: 0.8em;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  margin: 0 0 0.9em;
}

h2.chapter-title {
  font-size: 1.55em;
  line-height: 1.25;
  margin: 0;
}

/* Части */
.part-page {
  text-align: center;
  padding-top: 30%;
}

.part-num {
  text-indent: 0;
  text-align: center;
  font-size: 0.85em;
  letter-spacing: 0.25em;
  text-transform: uppercase;
  margin: 0 0 1em;
}

h1.part-title {
  font-size: 2em;
  line-height: 1.2;
  margin: 0;
}

p.ornament {
  text-indent: 0;
  text-align: center;
  margin-top: 1.5em;
}

/* Титул */
.title-page {
  text-align: center;
  padding-top: 22%;
}

.title-page p { text-indent: 0; text-align: center; }

.tp-author { font-size: 1.1em; margin-bottom: 2.5em; }

.tp-series {
  letter-spacing: 0.35em;
  text-transform: uppercase;
  font-size: 0.95em;
}

.tp-rule { margin: 0.8em 0; }

h1.tp-title {
  font-size: 2.4em;
  line-height: 1.15;
  letter-spacing: 0.04em;
  margin: 0.3em 0 0.5em;
}

.tp-book { font-size: 1em; margin-bottom: 3em; }

.tp-genre {
  font-size: 0.85em;
  letter-spacing: 0.2em;
  text-transform: uppercase;
}

/* Эпиграф */
.epigraph-page { padding-top: 35%; }

blockquote.epigraph {
  margin: 0 0 0 35%;
}

blockquote.epigraph p {
  text-indent: 0;
  text-align: left;
}

blockquote.epigraph p.verse { font-style: italic; }

blockquote.epigraph p.source {
  margin-top: 1em;
  text-align: right;
  font-size: 0.9em;
}

/* Аннотация */
.annotation { padding-top: 10%; }

h2.annotation-title,
h2.toc-title {
  text-align: center;
  font-size: 1.3em;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  margin: 1em 0 1.6em;
}

/* Содержание */
nav#toc ol {
  list-style-type: none;
  margin: 0;
  padding: 0;
}

nav#toc ol ol { padding-left: 1.6em; margin: 0.3em 0 0.9em; }

nav#toc li { margin: 0.35em 0; }

nav#toc a { text-decoration: none; color: inherit; }

/* Обложка */
body.cover-body { margin: 0; padding: 0; text-align: center; }

section.cover { margin: 0; padding: 0; height: 100%; }

section.cover svg { display: block; margin: 0; padding: 0; height: 100vh; width: 100%; }
"""


def build(author):
    chapters = read_chapters()
    by_num = {c.num: c for c in chapters}
    for _, _, rng in PARTS:
        for n in rng:
            if n not in by_num:
                raise SystemExit(f"Нет главы {n}")

    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    oebps = BUILD_DIR / "OEBPS"
    (oebps / "text").mkdir(parents=True)
    (oebps / "styles").mkdir()
    (oebps / "images").mkdir()
    (BUILD_DIR / "META-INF").mkdir()

    (BUILD_DIR / "mimetype").write_text("application/epub+zip", encoding="ascii")
    (BUILD_DIR / "META-INF" / "container.xml").write_text(CONTAINER, encoding="utf-8")
    (oebps / "styles" / "book.css").write_text(CSS, encoding="utf-8")
    make_cover.main(str(oebps / "images" / "cover.jpg"))

    text = oebps / "text"
    (text / "cover.xhtml").write_text(cover_page(), encoding="utf-8")
    (text / "title.xhtml").write_text(title_page(author), encoding="utf-8")
    (text / "epigraph.xhtml").write_text(epigraph_page(), encoding="utf-8")
    (text / "annotation.xhtml").write_text(annotation_page(), encoding="utf-8")
    for i, (num_label, name, _) in enumerate(PARTS, start=1):
        (text / f"part{i}.xhtml").write_text(part_page(i, num_label, name), encoding="utf-8")
    for ch in chapters:
        (text / ch.fname).write_text(chapter_page(ch), encoding="utf-8")

    (oebps / "nav.xhtml").write_text(nav_page(chapters), encoding="utf-8")
    (oebps / "toc.ncx").write_text(ncx(chapters), encoding="utf-8")
    modified = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (oebps / "content.opf").write_text(opf(chapters, author, modified), encoding="utf-8")

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / OUT_NAME
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w") as z:
        # mimetype — первым и без сжатия, как требует стандарт
        z.write(BUILD_DIR / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
        for path in sorted(BUILD_DIR.rglob("*")):
            if path.is_dir() or path.name == "mimetype":
                continue
            arc = path.relative_to(BUILD_DIR).as_posix()
            z.write(path, arc, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    words = sum(len(" ".join(c.blocks).split()) for c in chapters)
    chars = sum(len("\n\n".join(c.blocks)) for c in chapters)
    print(f"{out}  —  {len(chapters)} глав, ~{chars:,} знаков, ~{words:,} слов".replace(",", " "))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--author", default="", help="имя автора для метаданных и титула (по умолчанию пусто)")
    args = ap.parse_args()
    build(args.author.strip())


if __name__ == "__main__":
    main()
