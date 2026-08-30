"""Work out what the three news sources actually serve, before writing I-08.

Run: PYTHONIOENCODING=utf-8 python -m scratch.probe_news

Three things need establishing per source, and the existing scraper guesses at all
three:
  1. which element on the index page is a real headline link (it uses find_all('h3')
     blindly, which on these pages also collects nav labels and sidebar stubs);
  2. whether the article page carries a machine-readable publish date;
  3. which element on the article page is *this* story's body rather than a
     neighbouring story in a "recent stories" river -- economynext's article pages
     contain several stories, so "the longest block of <p>" picks the wrong one.
"""
import json
import re
import urllib.request
from urllib.parse import urljoin

from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# ft.lk is slow and drops connections; two attempts at 45s beats one at 90s
# because the failure mode is a hang, not a slow transfer.
ATTEMPTS = 3
TIMEOUT = 45


def get(url: str) -> bytes:
    last = None
    for _ in range(ATTEMPTS):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=TIMEOUT).read()
        except Exception as e:  # noqa: BLE001 - probe script, report and retry
            last = e
    raise last


def clean(t) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def links(soup, idx_url, selector):
    """(title, url) for every candidate the selector finds.

    Handles both nestings: the anchor inside the heading (ft.lk, economynext) and
    the anchor wrapping it (dailymirror).
    """
    out = []
    for c in soup.select(selector):
        a = c.find("a", href=True) or c.find_parent("a", href=True)
        if not a:
            continue
        title = clean(c.get_text())
        if not title:
            continue
        out.append((title, urljoin(idx_url, a["href"])))
    return out


def dates(art):
    found = []
    for m in art.find_all("meta"):
        p = (m.get("property") or m.get("name") or "").lower()
        if any(k in p for k in ("published", "modified", "date", "time")):
            found.append((f"meta[{p}]", clean(m.get("content"))))
    for sc in art.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(sc.string or "{}")
        except Exception:  # noqa: BLE001
            continue
        stack = [d]
        while stack:
            o = stack.pop()
            if isinstance(o, list):
                stack.extend(o)
            elif isinstance(o, dict):
                if o.get("datePublished"):
                    found.append((f"ld+json[{o.get('@type')}]", str(o["datePublished"])))
                stack.extend(v for v in o.values() if isinstance(v, (dict, list)))
    return found


CFG = [
    # (label, index url, candidate heading selector, body selector to test)
    ("ft.lk", "https://www.ft.lk/Financial-Services/42",
     "div.card-body.cbm h3", "div.inner-content, div.article-content, div#article-content"),
    ("dailymirror", "https://www.dailymirror.lk/business",
     "h3", "div.inner-content, div.article-content, div.news-content"),
    ("economynext", "https://economynext.com/markets/",
     "h3.recent-top-header", "div.story-page-text-main"),
]


def main():
    for label, idx, sel, bodysel in CFG:
        print("=" * 74)
        print(label)
        try:
            soup = BeautifulSoup(get(idx), "lxml")
        except Exception as e:  # noqa: BLE001
            print(f"  index unreachable: {type(e).__name__}: {e}")
            continue

        cand = links(soup, idx, sel)
        blind = len(soup.find_all("h3"))
        print(f"  selector {sel!r} -> {len(cand)} links "
              f"(blind find_all('h3') -> {blind})")
        for t, u in cand[:6]:
            print(f"     {t[:56]!r:60} {u.rsplit('/', 2)[-2][:26]}")

        if not cand:
            continue
        title, url = cand[0]
        print(f"  -- article: {url[:88]}")
        try:
            art = BeautifulSoup(get(url), "lxml")
        except Exception as e:  # noqa: BLE001
            print(f"     unreachable: {type(e).__name__}: {e}")
            continue

        d = dates(art)
        print("  -- dates --")
        for k, v in d[:6]:
            print(f"     {k:34} {v[:44]!r}")
        if not d:
            print("     (none)")

        print(f"  -- body via {bodysel!r} --")
        nodes = art.select(bodysel)
        print(f"     {len(nodes)} match(es); using first in document order")
        if nodes:
            ps = nodes[0].find_all("p")
            txt = clean(" ".join(p.get_text() for p in ps))
            # Does it belong to THIS headline? First words of the title should
            # appear, or at least the body should not be about something else.
            print(f"     {len(txt)} chars, {len(ps)} paras")
            print(f"     {txt[:220]!r}")
        else:
            print("     no match - dumping the biggest <p> containers instead")
            best = []
            for dv in art.find_all(["div", "article", "section"]):
                ps = dv.find_all("p")
                if len(ps) < 3:
                    continue
                t = clean(" ".join(p.get_text() for p in ps))
                if len(t) < 300:
                    continue
                best.append((len(t), f"{dv.name}.{'.'.join(dv.get('class') or [])}"[:44], len(ps), t))
            best.sort(reverse=True)
            seen = set()
            for n, k, np_, t in best:
                if k in seen:
                    continue
                seen.add(k)
                print(f"       {k:44} {n:>6}ch {np_:>3}p {t[:90]!r}")
                if len(seen) >= 6:
                    break


if __name__ == "__main__":
    main()
