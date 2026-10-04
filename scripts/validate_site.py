#!/usr/bin/env python3
"""Fail-closed validator for the Metro Time Helper support site.

Exit code is non-zero on any problem. Checks source content, every generated page,
links, hreflang/canonical, RTL direction, contact address, privacy date, external
resources, sitemap and robots.
"""

from __future__ import annotations

import html.parser
import json
import pathlib
import re
import subprocess
import sys
import unicodedata
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import generate_site as gen  # noqa: E402  (load_site runs and fails closed on bad site.json)

ERRORS: list[str] = []


def fail(message: str) -> None:
    ERRORS.append(message)


EMAIL = gen.EMAIL
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
CURRENCY_RE = re.compile(r"[$€£¥₹₩₫฿₪₺₽₴₱₦]|NT\$|\bTWD\b|\bUSD\b|\bEUR\b|新臺幣|新台幣|台幣|臺幣|\d+\s*元")
FORBIDDEN_WORDS = ("hotmail", "outlook.com", "live.com", "yahoo.", "gmail.com>")
INVISIBLE = {"​", "﻿", "‎", "‏", "‪", "‫", "‬", "‭", "‮", "⁦", "⁧", "⁨", "⁩"}
NO_ZWNJ = {"te-IN", "kn-IN", "ml-IN"}
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")
DECOR_RE = re.compile("[★☆→←⇒•●▶►✓✔︎]")

# Expected dominant script per locale (Unicode name prefix of letters).
SCRIPTS = {
    "ar-SA": "ARABIC", "ur-PK": "ARABIC", "he": "HEBREW", "hi": "DEVANAGARI", "mr-IN": "DEVANAGARI",
    "bn-BD": "BENGALI", "gu-IN": "GUJARATI", "pa-IN": "GURMUKHI", "or-IN": "ORIYA", "ta-IN": "TAMIL",
    "te-IN": "TELUGU", "kn-IN": "KANNADA", "ml-IN": "MALAYALAM", "th": "THAI", "el": "GREEK",
    "ru": "CYRILLIC", "uk": "CYRILLIC", "ko": "HANGUL", "ja": "CJK|HIRAGANA|KATAKANA",
    "zh-Hans": "CJK", "zh-Hant": "CJK",
}
SIMPLIFIED_ONLY = set("这们为时间设页发车线览关数据门开个对说没从选择")
TRADITIONAL_ONLY = set("這們為時間設頁發車線覽關數據門開個對說沒從選擇")
ENGLISH = {"en-US", "en-GB", "en-AU", "en-CA"}
# Sections whose body must state these numbers (digits in any script are normalized).
REQUIRED_NUMBERS = {
    ("home", "sections", "xiaobitan"): {"12", "16", "1", "30"},
    ("home", "sections", "trial"): {"24"},
    ("support", "howto", "plan_trip"): {"15"},
    ("support", "howto", "branch_reminders"): {"1", "30"},
    ("support", "howto", "language"): {"50"},
    ("support", "faq", "trial_unlock"): {"24"},
}


def normalize_digits(text: str) -> str:
    return "".join(str(unicodedata.digit(ch)) if ch.isdigit() and unicodedata.digit(ch, None) is not None else ch for ch in text)


def strings(value: object, path: str = ""):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from strings(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from strings(child, f"{path}[{index}]")


def check_text(locale: str, where: str, text: str) -> None:
    lowered = text.lower()
    for word in FORBIDDEN_WORDS:
        if word in lowered:
            fail(f"{locale} {where}: forbidden contact/vendor text {word!r}")
    for address in EMAIL_RE.findall(text):
        if address != EMAIL:
            fail(f"{locale} {where}: unauthorized email {address}")
    if CURRENCY_RE.search(text):
        fail(f"{locale} {where}: price or currency text {CURRENCY_RE.search(text).group(0)!r}")
    if EMOJI_RE.search(text) or DECOR_RE.search(text):
        fail(f"{locale} {where}: emoji or decorative symbol")
    bad = INVISIBLE & set(text)
    if bad:
        fail(f"{locale} {where}: invisible control characters {sorted(hex(ord(c)) for c in bad)}")
    if locale in NO_ZWNJ and "‌" in text:
        fail(f"{locale} {where}: ZWNJ is not allowed")
    if re.search(r"https?://", text):
        fail(f"{locale} {where}: URL in content text")


def script_share(text: str, prefixes: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    wanted = tuple(prefixes.split("|"))
    hits = sum(1 for ch in letters if unicodedata.name(ch, "").startswith(wanted))
    return hits / len(letters)


def check_sources(tr: dict) -> None:
    english = tr["en-US"]
    english_values = dict(strings(english))
    for locale, item in tr.items():
        values = dict(strings(item))
        if set(values) != set(english_values):
            fail(f"{locale}: string paths differ from en-US")
        for path, text in values.items():
            check_text(locale, path, text)
        if locale not in ENGLISH:
            for path, text in values.items():
                if path.endswith(".id"):
                    continue
                if text == english_values.get(path) and len(text) > 12:
                    fail(f"{locale} {path}: still identical to English")
            if locale in SCRIPTS:
                prose = " ".join(t for p, t in values.items() if p.endswith(".body"))
                share = script_share(prose, SCRIPTS[locale])
                if share < 0.75:
                    fail(f"{locale}: only {share:.0%} of letters are in the expected script")
        if locale == "zh-Hant" and SIMPLIFIED_ONLY & set("".join(values.values())):
            fail(f"zh-Hant: simplified characters {sorted(SIMPLIFIED_ONLY & set(''.join(values.values())))}")
        if locale == "zh-Hans" and TRADITIONAL_ONLY & set("".join(values.values())):
            fail(f"zh-Hans: traditional characters {sorted(TRADITIONAL_ONLY & set(''.join(values.values())))}")
        for (block, key, sid), numbers in REQUIRED_NUMBERS.items():
            section = next(s for s in item[block][key] if s["id"] == sid)
            found = set(re.findall(r"\d+", normalize_digits(section["body"])))
            if not numbers <= found:
                fail(f"{locale} {block}.{key}.{sid}: missing numbers {sorted(numbers - found)}")
    names = [item["language_name"] for item in tr.values()]
    if len(set(names)) != len(names):
        fail("language_name values are not unique")


class PageParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_attrs: dict[str, str] = {}
        self.links: list[dict[str, str]] = []
        self.refs: list[tuple[str, str, str]] = []
        self.scripts: list[dict[str, str]] = []
        self.h1 = 0
        self.title = ""
        self._in_title = False
        self.text: list[str] = []
        self.ids: list[str] = []
        self.styles_inline = 0
        self.meta: list[dict[str, str]] = []
        self.time_values: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "html":
            self.html_attrs = a
        if tag == "link":
            self.links.append(a)
        if tag == "meta":
            self.meta.append(a)
        if tag == "script":
            self.scripts.append(a)
        if tag == "style" or "style" in a:
            self.styles_inline += 1
        if any(k.startswith("on") for k in a):
            self.styles_inline += 1
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self._in_title = True
        if tag == "time":
            self.time_values.append(a.get("datetime", ""))
        if "id" in a:
            self.ids.append(a["id"])
        for attr in ("href", "src"):
            if attr in a:
                self.refs.append((tag, attr, a[attr]))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        self.text.append(data)


def check_page(tr: dict, locale: str | None, page: str) -> None:
    path = gen.output_path(locale, page)
    label = str(path.relative_to(ROOT))
    if not path.is_file():
        fail(f"{label}: missing")
        return
    source = path.read_text(encoding="utf-8")
    parser = PageParser()
    parser.feed(source)
    content_locale = locale or gen.X_DEFAULT_CONTENT
    want_lang = gen.HTML_LANG.get(content_locale, content_locale)
    want_dir = "rtl" if content_locale in gen.RTL else "ltr"
    if parser.html_attrs.get("lang") != want_lang:
        fail(f"{label}: lang={parser.html_attrs.get('lang')} expected {want_lang}")
    if parser.html_attrs.get("dir") != want_dir:
        fail(f"{label}: dir={parser.html_attrs.get('dir')} expected {want_dir}")
    canon = [l["href"] for l in parser.links if l.get("rel") == "canonical"]
    if canon != [gen.page_url(locale, page)]:
        fail(f"{label}: canonical {canon} is not self")
    alts = {(l.get("hreflang"), l.get("href")) for l in parser.links if l.get("rel") == "alternate"}
    want_alts = {(l, gen.page_url(l, page)) for l in gen.LOCALES} | {("x-default", gen.page_url(None, page))}
    if alts != want_alts or len([l for l in parser.links if l.get("rel") == "alternate"]) != 51:
        fail(f"{label}: hreflang set is not the exact 50 locales plus x-default")
    if not parser.title.strip() or parser.h1 != 1:
        fail(f"{label}: needs a title and exactly one h1")
    if not any(m.get("name") == "description" and m.get("content", "").strip() for m in parser.meta):
        fail(f"{label}: missing meta description")
    if parser.styles_inline:
        fail(f"{label}: inline style or event handler found")
    if len(parser.ids) != len(set(parser.ids)):
        fail(f"{label}: duplicate element ids")
    is_router = locale is None and page == "index"
    want_scripts = [{"src": "assets/locale-redirect.js", "defer": ""}] if is_router else []
    if parser.scripts != want_scripts:
        fail(f"{label}: unexpected scripts {parser.scripts}")
    mailtos = [r[2] for r in parser.refs if r[2].startswith("mailto:")]
    if mailtos != [f"mailto:{EMAIL}"]:
        fail(f"{label}: contact link must be exactly one mailto:{EMAIL}, got {mailtos}")
    for tag, attr, ref in parser.refs:
        if ref.startswith("mailto:"):
            continue
        parsed = urllib.parse.urlparse(ref)
        if parsed.scheme or parsed.netloc:
            allowed = tag == "link" and ref.startswith(gen.BASE_URL)
            if not allowed:
                fail(f"{label}: external resource {ref}")
            continue
        if ref.startswith("#"):
            if ref[1:] not in parser.ids:
                fail(f"{label}: broken fragment {ref}")
            continue
        target = (path.parent / parsed.path).resolve()
        if not target.is_file():
            fail(f"{label}: broken link {ref}")
        elif ROOT.resolve() not in target.parents:
            fail(f"{label}: link escapes site root {ref}")
    text = " ".join(parser.text)
    check_text(content_locale, label, text)
    lowered = source.lower()
    for word in FORBIDDEN_WORDS:
        if word in lowered:
            fail(f"{label}: forbidden text {word}")
    item = tr[content_locale]
    if page == "privacy":
        if gen.UPDATED != "2026-10-04" or "2026-10-04" not in parser.time_values:
            fail(f"{label}: Last Updated must be 2026-10-04")
        if item["privacy"]["updated_label"] not in text:
            fail(f"{label}: Last Updated label missing")
        needed = gen.SECTION_IDS[("privacy", "sections")]
    elif page == "support":
        needed = gen.SECTION_IDS[("support", "howto")] + gen.SECTION_IDS[("support", "faq")]
    else:
        needed = gen.SECTION_IDS[("home", "sections")]
    missing = [sid for sid in needed if sid not in parser.ids]
    if missing:
        fail(f"{label}: missing sections {missing}")
    if "contact-heading" not in parser.ids:
        fail(f"{label}: missing contact section")


def main() -> int:
    try:
        tr = gen.load_translations()
    except SystemExit as error:
        print(error)
        return 1
    check_sources(tr)
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_site.py"), "--check"], capture_output=True, text=True)
    if result.returncode != 0:
        fail("generator check failed:\n" + (result.stdout + result.stderr).strip())
    pages = 0
    for locale in (None, *gen.LOCALES):
        for page in gen.PAGES:
            check_page(tr, locale, page)
            pages += 1
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8") if (ROOT / "sitemap.xml").is_file() else ""
    locs = re.findall(r"<loc>([^<]+)</loc>", sitemap)
    want = [gen.page_url(None, p) for p in gen.PAGES] + [gen.page_url(l, p) for l in gen.LOCALES for p in gen.PAGES]
    if locs != want:
        fail(f"sitemap.xml: expected {len(want)} URLs, found {len(locs)}")
    robots = (ROOT / "robots.txt").read_text(encoding="utf-8") if (ROOT / "robots.txt").is_file() else ""
    if f"Sitemap: {gen.BASE_URL}sitemap.xml" not in robots:
        fail("robots.txt: sitemap line missing")
    for asset in ("site.css", "locale-redirect.js", "app-icon-256.png", "app-icon-512.png", "apple-touch-icon.png"):
        if not (ROOT / "assets" / asset).is_file():
            fail(f"assets/{asset}: missing")
    css = (ROOT / "assets" / "site.css").read_text(encoding="utf-8")
    if re.search(r"@import|url\(\s*['\"]?https?:", css):
        fail("site.css: external resource")
    if ERRORS:
        for error in ERRORS[:200]:
            print(f"FAIL: {error}")
        print(f"FAILED: {len(ERRORS)} problem(s).")
        return 1
    print(f"PASS: {pages} pages ({len(gen.LOCALES)} locales x 3 + x-default x 3), sources, links, hreflang, RTL, contact, sitemap.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
