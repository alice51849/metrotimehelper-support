#!/usr/bin/env python3
"""Generate the deterministic 50-locale Metro Time Helper support, privacy and home pages.

Usage:
  python3 scripts/generate_site.py          # write every page, sitemap.xml and robots.txt
  python3 scripts/generate_site.py --check  # fail if any generated file is missing or stale
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import pathlib
import urllib.parse
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE_ROOT = ROOT / "source"
LOCALE_ROOT = SOURCE_ROOT / "locales"
SITE_PATH = SOURCE_ROOT / "site.json"

PAGES = ("index", "support", "privacy")
PAGE_FILES = {"index": "index.html", "support": "support.html", "privacy": "privacy.html"}
OFFICIAL_LOCALES = (
    "ar-SA", "bn-BD", "ca", "zh-Hans", "zh-Hant", "hr", "cs", "da", "nl-NL", "en-AU",
    "en-CA", "en-GB", "en-US", "fi", "fr-CA", "fr-FR", "de-DE", "el", "gu-IN", "he",
    "hi", "hu", "id", "it", "ja", "kn-IN", "ko", "ms", "ml-IN", "mr-IN", "no", "or-IN",
    "pl", "pt-BR", "pt-PT", "pa-IN", "ro", "ru", "sk", "sl-SI", "es-MX", "es-ES", "sv",
    "ta-IN", "te-IN", "th", "tr", "uk", "ur-PK", "vi",
)
RTL = {"ar-SA", "he", "ur-PK"}
# BCP 47 tag used for the html lang attribute (ASC "no" is Norwegian Bokmal).
HTML_LANG = {"no": "nb"}
OG_LOCALES = {
    "ar-SA": "ar_SA", "bn-BD": "bn_BD", "ca": "ca_ES", "zh-Hans": "zh_CN", "zh-Hant": "zh_TW",
    "hr": "hr_HR", "cs": "cs_CZ", "da": "da_DK", "nl-NL": "nl_NL", "en-AU": "en_AU",
    "en-CA": "en_CA", "en-GB": "en_GB", "en-US": "en_US", "fi": "fi_FI", "fr-CA": "fr_CA",
    "fr-FR": "fr_FR", "de-DE": "de_DE", "el": "el_GR", "gu-IN": "gu_IN", "he": "he_IL",
    "hi": "hi_IN", "hu": "hu_HU", "id": "id_ID", "it": "it_IT", "ja": "ja_JP", "kn-IN": "kn_IN",
    "ko": "ko_KR", "ms": "ms_MY", "ml-IN": "ml_IN", "mr-IN": "mr_IN", "no": "nb_NO",
    "or-IN": "or_IN", "pl": "pl_PL", "pt-BR": "pt_BR", "pt-PT": "pt_PT", "pa-IN": "pa_IN",
    "ro": "ro_RO", "ru": "ru_RU", "sk": "sk_SK", "sl-SI": "sl_SI", "es-MX": "es_MX",
    "es-ES": "es_ES", "sv": "sv_SE", "ta-IN": "ta_IN", "te-IN": "te_IN", "th": "th_TH",
    "tr": "tr_TR", "uk": "uk_UA", "ur-PK": "ur_PK", "vi": "vi_VN",
}
SECTION_IDS = {
    ("home", "sections"): ("reverse_planner", "xiaobitan", "xinbeitou", "map_widget", "privacy_first", "trial"),
    ("support", "howto"): ("three_modes", "switch_mode", "plan_trip", "branch_reminders", "default_page", "language"),
    ("support", "faq"): ("why_estimate", "branch_timetable", "notifications", "restore", "trial_unlock", "coverage", "independence"),
    ("privacy", "sections"): (
        "no_account", "data_collection", "on_device", "notifications", "storekit",
        "no_ads_analytics", "data_sources", "contact_requests", "policy_changes",
    ),
}
SITE_KEYS = {"brand", "email", "updated", "canonical_base_url", "locales", "brands"}
LOCALE_KEYS = {"language_name", "language_label", "navigation_label", "skip_link", "nav", "footer", "contact", "home", "support", "privacy"}
BLOCK_KEYS = {
    "home": {"title", "summary", "section_title", "sections", "links_title", "support_card", "privacy_card"},
    "support": {"title", "summary", "howto_title", "howto", "faq_title", "faq"},
    "privacy": {"title", "summary", "updated_label", "section_title", "sections"},
}
EMAIL = "hourstag.app@gmail.com"
X_DEFAULT_CONTENT = "en-US"


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def need_text(value: object, ctx: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"FAIL: {ctx}: expected non-empty text")
    return value


def exact_keys(value: object, keys: set[str], ctx: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise SystemExit(f"FAIL: {ctx}: keys are not exact")
    return value


def load_site() -> dict[str, Any]:
    try:
        site = json.loads(SITE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"FAIL: cannot read source/site.json: {error}") from error
    exact_keys(site, SITE_KEYS, "site")
    if tuple(site["locales"]) != OFFICIAL_LOCALES:
        raise SystemExit("FAIL: site.locales is not the official ordered 50-locale list")
    if site["email"] != EMAIL:
        raise SystemExit("FAIL: public contact email is not the authorized address")
    if site["brand"] != "Metro Time Helper":
        raise SystemExit("FAIL: site.brand does not match the product")
    datetime.date.fromisoformat(site["updated"])
    base = urllib.parse.urlparse(site["canonical_base_url"])
    if base.scheme != "https" or not base.netloc or not site["canonical_base_url"].endswith("/") or base.query or base.fragment:
        raise SystemExit("FAIL: canonical_base_url must be an absolute https URL ending in /")
    exact_keys(site["brands"], set(OFFICIAL_LOCALES), "site.brands")
    for locale, brand in site["brands"].items():
        need_text(brand, f"site.brands.{locale}")
    return site


SITE = load_site()
LOCALES: tuple[str, ...] = tuple(SITE["locales"])
BASE_URL: str = SITE["canonical_base_url"]
UPDATED: str = SITE["updated"]
BRANDS: dict[str, str] = SITE["brands"]


def check_sections(value: object, ids: tuple[str, ...], ctx: str) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) != len(ids):
        raise SystemExit(f"FAIL: {ctx}: wrong section count")
    out = []
    for index, raw in enumerate(value):
        section = exact_keys(raw, {"id", "title", "body"}, f"{ctx}[{index}]")
        for key in ("id", "title", "body"):
            need_text(section[key], f"{ctx}[{index}].{key}")
        out.append(section)
    if tuple(s["id"] for s in out) != ids:
        raise SystemExit(f"FAIL: {ctx}: section ids are not exact or ordered")
    return out


def load_translations() -> dict[str, dict[str, Any]]:
    files = {path.stem: path for path in LOCALE_ROOT.glob("*.json")}
    if set(files) != set(LOCALES):
        missing = ", ".join(sorted(set(LOCALES) - set(files))) or "none"
        extra = ", ".join(sorted(set(files) - set(LOCALES))) or "none"
        raise SystemExit(f"FAIL: locale files mismatch; missing: {missing}; extra: {extra}")
    result: dict[str, dict[str, Any]] = {}
    for locale in LOCALES:
        try:
            item = json.loads(files[locale].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"FAIL: {locale}: cannot read locale source: {error}") from error
        exact_keys(item, LOCALE_KEYS, locale)
        for key in ("language_name", "language_label", "navigation_label", "skip_link", "footer"):
            need_text(item[key], f"{locale}.{key}")
        for key in PAGES:
            need_text(exact_keys(item["nav"], set(PAGES), f"{locale}.nav")[key], f"{locale}.nav.{key}")
        for key in ("title", "body", "button"):
            need_text(exact_keys(item["contact"], {"title", "body", "button"}, f"{locale}.contact")[key], f"{locale}.contact.{key}")
        for block_name, keys in BLOCK_KEYS.items():
            block = exact_keys(item[block_name], keys, f"{locale}.{block_name}")
            for key in keys:
                ids = SECTION_IDS.get((block_name, key))
                if ids:
                    block[key] = check_sections(block[key], ids, f"{locale}.{block_name}.{key}")
                elif key in ("support_card", "privacy_card"):
                    card = exact_keys(block[key], {"title", "body"}, f"{locale}.{block_name}.{key}")
                    need_text(card["title"], f"{locale}.{block_name}.{key}.title")
                    need_text(card["body"], f"{locale}.{block_name}.{key}.body")
                else:
                    need_text(block[key], f"{locale}.{block_name}.{key}")
        result[locale] = item
    return result


def page_url(locale: str | None, page: str) -> str:
    prefix = f"{locale}/" if locale else ""
    return f"{BASE_URL}{prefix}{PAGE_FILES[page]}"


def output_path(locale: str | None, page: str) -> pathlib.Path:
    return ROOT / PAGE_FILES[page] if locale is None else ROOT / locale / PAGE_FILES[page]


def rel_href(current: str | None, target: str | None, page: str) -> str:
    name = PAGE_FILES[page]
    if current == target:
        return name
    if current is None:
        return f"{target}/{name}"
    if target is None:
        return f"../{name}"
    return f"../{target}/{name}"


def asset(locale: str | None, filename: str) -> str:
    return f"{'../' if locale else ''}assets/{filename}"


def alternates(page: str) -> str:
    rows = [f'<link rel="alternate" hreflang="{l}" href="{esc(page_url(l, page))}">' for l in LOCALES]
    rows.append(f'<link rel="alternate" hreflang="x-default" href="{esc(page_url(None, page))}">')
    return "\n  ".join(rows)


def nav_markup(locale: str | None, page: str, labels: dict[str, str]) -> str:
    rows = []
    for candidate in PAGES:
        current = ' aria-current="page"' if candidate == page else ""
        rows.append(f'<a href="{esc(rel_href(locale, locale, candidate))}"{current}>{esc(labels[candidate])}</a>')
    return "\n        ".join(rows)


def language_markup(tr: dict[str, dict[str, Any]], locale: str | None, page: str) -> str:
    rows = []
    for candidate in LOCALES:
        current = ' aria-current="page"' if candidate == locale else ""
        lang = HTML_LANG.get(candidate, candidate)
        direction = "rtl" if candidate in RTL else "ltr"
        rows.append(
            f'<li><a lang="{lang}" hreflang="{candidate}" dir="{direction}" '
            f'href="{esc(rel_href(locale, candidate, page))}"{current}>'
            f'{esc(tr[candidate]["language_name"])}</a></li>'
        )
    return "\n          ".join(rows)


def cards(sections: list[dict[str, str]], heading_id: str, heading: str, extra_class: str = "", numbered: bool = False) -> str:
    tag = "ol" if numbered else "ul"
    items = "\n".join(
        f'      <li><article class="card" id="{esc(s["id"])}"><h3>{esc(s["title"])}</h3><p>{esc(s["body"])}</p></article></li>'
        for s in sections
    )
    return (
        f'<section class="block" aria-labelledby="{heading_id}">\n'
        f'    <h2 class="section-heading" id="{heading_id}">{esc(heading)}</h2>\n'
        f'    <{tag} class="grid{extra_class}" role="list">\n{items}\n    </{tag}>\n'
        "  </section>"
    )


def contact_markup(item: dict[str, Any]) -> str:
    c = item["contact"]
    return (
        '<section class="card contact" aria-labelledby="contact-heading">\n'
        f'    <h2 id="contact-heading">{esc(c["title"])}</h2>\n'
        f'    <p>{esc(c["body"])}</p>\n'
        f'    <address><a class="mail" href="mailto:{EMAIL}" aria-label="{esc(c["button"])}: {EMAIL}">'
        f'<span class="mail-label">{esc(c["button"])}</span> <span dir="ltr">{EMAIL}</span></a></address>\n'
        "  </section>"
    )


def body_markup(item: dict[str, Any], locale: str | None, page: str) -> str:
    if page == "index":
        home = item["home"]
        links = (
            '<section class="block" aria-labelledby="links-heading">\n'
            f'    <h2 class="section-heading" id="links-heading">{esc(home["links_title"])}</h2>\n'
            '    <div class="grid links">\n'
            f'      <a class="card link-card" href="{esc(rel_href(locale, locale, "support"))}"><h3>{esc(home["support_card"]["title"])}</h3><p>{esc(home["support_card"]["body"])}</p></a>\n'
            f'      <a class="card link-card" href="{esc(rel_href(locale, locale, "privacy"))}"><h3>{esc(home["privacy_card"]["title"])}</h3><p>{esc(home["privacy_card"]["body"])}</p></a>\n'
            "    </div>\n"
            "  </section>"
        )
        return "\n  ".join([cards(home["sections"], "features-heading", home["section_title"]), links])
    if page == "support":
        sup = item["support"]
        return "\n  ".join([
            cards(sup["howto"], "howto-heading", sup["howto_title"], numbered=True),
            cards(sup["faq"], "faq-heading", sup["faq_title"], " faq"),
        ])
    pri = item["privacy"]
    return cards(pri["sections"], "policy-heading", pri["section_title"], " policy")


def render(tr: dict[str, dict[str, Any]], locale: str | None, page: str) -> str:
    content_locale = locale or X_DEFAULT_CONTENT
    item = tr[content_locale]
    block = item["home" if page == "index" else page]
    brand = BRANDS[content_locale]
    direction = "rtl" if content_locale in RTL else "ltr"
    lang = HTML_LANG.get(content_locale, content_locale)
    canonical = page_url(locale, page)
    title = block["title"] if page == "index" else f'{block["title"]} | {brand}'
    if page == "index":
        title = f"{brand} | {block['title']}"
    router = locale is None and page == "index"
    script_src = "'self'" if router else "'none'"
    router_tag = f'\n  <script src="{asset(locale, "locale-redirect.js")}" defer></script>' if router else ""
    updated = (
        f'\n      <p class="updated">{esc(block["updated_label"])}: <time datetime="{UPDATED}" dir="ltr">{UPDATED}</time></p>'
        if page == "privacy" else ""
    )
    return f"""<!doctype html>
<!-- Generated by scripts/generate_site.py. Do not edit by hand. -->
<html lang="{lang}" dir="{direction}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" content="#fbf7ff" media="(prefers-color-scheme: light)">
  <meta name="theme-color" content="#120d2b" media="(prefers-color-scheme: dark)">
  <meta name="robots" content="index,follow">
  <meta name="referrer" content="no-referrer">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src {script_src}; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(block["summary"])}">
  <link rel="canonical" href="{esc(canonical)}">
  {alternates(page)}
  <link rel="icon" href="{asset(locale, "app-icon-256.png")}" type="image/png">
  <link rel="apple-touch-icon" href="{asset(locale, "apple-touch-icon.png")}">
  <link rel="stylesheet" href="{asset(locale, "site.css")}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{esc(brand)}">
  <meta property="og:locale" content="{OG_LOCALES[content_locale]}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(block["summary"])}">
  <meta property="og:url" content="{esc(canonical)}">{router_tag}
</head>
<body>
  <a class="skip-link" href="#main">{esc(item["skip_link"])}</a>
  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="{esc(rel_href(locale, locale, "index"))}">
        <img src="{asset(locale, "app-icon-256.png")}" width="40" height="40" alt="">
        <span>{esc(brand)}</span>
      </a>
      <nav class="primary-nav" aria-label="{esc(item["navigation_label"])}">
        {nav_markup(locale, page, item["nav"])}
      </nav>
      <details class="language-picker">
        <summary>{esc(item["language_label"])}</summary>
        <ul class="language-list" role="list">
          {language_markup(tr, locale, page)}
        </ul>
      </details>
    </div>
  </header>
  <main class="page" id="main" tabindex="-1">
  <header class="hero hero-{page}">
    <div class="hero-text">
      <p class="eyebrow">{esc(brand)}</p>
      <h1>{esc(block["title"])}</h1>
      <p class="lead">{esc(block["summary"])}</p>{updated}
    </div>
    <div class="hero-art" aria-hidden="true">
      <img src="{asset(locale, "app-icon-512.png")}" width="512" height="512" alt="">
    </div>
  </header>
  {body_markup(item, locale, page)}
  {contact_markup(item)}
  </main>
  <footer class="site-footer">
    <div class="footer-inner">
      <p>{esc(item["footer"])}</p>
      <p class="footer-links"><a href="{esc(rel_href(locale, locale, "support"))}">{esc(item["nav"]["support"])}</a> <a href="{esc(rel_href(locale, locale, "privacy"))}">{esc(item["nav"]["privacy"])}</a> <span dir="ltr">&copy; 2026 Metro Time Helper</span></p>
    </div>
  </footer>
</body>
</html>
"""


def sitemap() -> str:
    urls = [page_url(None, p) for p in PAGES] + [page_url(l, p) for l in LOCALES for p in PAGES]
    rows = "\n".join(f"  <url><loc>{esc(u)}</loc><lastmod>{UPDATED}</lastmod></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}\n</urlset>\n'


def expected_outputs(tr: dict[str, dict[str, Any]]) -> dict[pathlib.Path, str]:
    out = {output_path(l, p): render(tr, l, p) for l in (None, *LOCALES) for p in PAGES}
    out[ROOT / "sitemap.xml"] = sitemap()
    out[ROOT / "robots.txt"] = f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}sitemap.xml\n"
    out[ROOT / ".nojekyll"] = ""
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = expected_outputs(load_translations())
    if args.check:
        fails = [f"missing {p.relative_to(ROOT)}" for p in outputs if not p.is_file()]
        fails += [f"stale {p.relative_to(ROOT)}" for p, t in outputs.items() if p.is_file() and p.read_text(encoding="utf-8") != t]
        expected_html = {p.resolve() for p in outputs if p.suffix == ".html"}
        fails += [f"unexpected {p}" for p in sorted({p.resolve() for p in ROOT.rglob("*.html") if ".git" not in p.parts} - expected_html)]
        if fails:
            raise SystemExit("\n".join(f"FAIL: {f}" for f in fails))
        print(f"PASS generator check: {len(expected_html)} pages up to date.")
        return
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Generated {len(PAGES) * (len(LOCALES) + 1)} HTML pages for {len(LOCALES)} locales.")


if __name__ == "__main__":
    main()
