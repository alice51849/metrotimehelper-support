# Metro Time Helper support site

Support, privacy and home pages for the iOS app Metro Time Helper (捷運時間助手), in the 50 App Store Connect locales.

Published with GitHub Pages from the `main` branch root:
`https://alice51849.github.io/metrotimehelper-support/<locale>/index.html`, `support.html`, `privacy.html`.
The root pages are the `x-default` versions (English); the root `index.html` sends visitors to their browser language.

## Edit and publish

1. Change text only in `source/locales/<locale>.json` (and `source/site.json` for shared values).
2. `python3 scripts/generate_site.py` to rebuild every page, `sitemap.xml` and `robots.txt`.
3. `python3 scripts/validate_site.py` must print `PASS` before committing.

No third-party fonts, scripts, analytics or trackers. Public contact: hourstag.app@gmail.com.
