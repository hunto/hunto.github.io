#!/usr/bin/env python3
"""
Extract teaser figures from arXiv HTML versions of papers in publication.html.

For each <li class="paper"> with an arxiv.org/abs/<id> link and no
data-figure attribute set, this:
  1. fetches https://arxiv.org/html/<id>
  2. picks the first <img class="ltx_graphics ltx_img_landscape">
  3. resizes via `sips` to 480px-wide JPEG
  4. saves to assets/<id>/teaser.jpg
  5. adds data-figure="assets/<id>/teaser.jpg" to the <li>

Use --list to download every landscape candidate per paper into
assets/<id>/candidates/ for manual inspection (no HTML edit, no teaser
written). Combine with --only=<id> to scope to one paper.

Usage:
  python3 scripts/extract_paper_figures.py            # auto-install
  python3 scripts/extract_paper_figures.py --dry-run  # show plan
  python3 scripts/extract_paper_figures.py --list     # just dump candidates
  python3 scripts/extract_paper_figures.py --only=2502.02175
"""
import argparse
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUB_HTML = ROOT / "publication.html"
ASSETS = ROOT / "assets"
USER_AGENT = "Mozilla/5.0 (compatible; figure-extractor/1.0)"


class ArxivFigureFinder(HTMLParser):
    """Find <img class="ltx_graphics ..."> tags in document order."""

    def __init__(self):
        super().__init__()
        self.figures = []  # list of dicts: src, classes, width, height

    def handle_starttag(self, tag, attrs):
        if tag != "img":
            return
        a = dict(attrs)
        cls = a.get("class", "")
        if "ltx_graphics" not in cls:
            return
        src = a.get("src")
        if not src or src.startswith("data:"):
            return
        self.figures.append({
            "src": src,
            "classes": cls,
            "width": a.get("width"),
            "height": a.get("height"),
        })


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def candidate_image_urls(arxiv_id: str, src: str) -> list[str]:
    """Different arxiv HTML papers reference images relative to different
    base paths. Return URLs to try in order."""
    urls = []
    # 1. Standard: relative to /html/<id>/
    urls.append(urllib.parse.urljoin(f"https://arxiv.org/html/{arxiv_id}/", src))
    # 2. Some papers use paths like '<id>v1/x1.png' relative to /html/
    urls.append(urllib.parse.urljoin("https://arxiv.org/html/", src))
    return list(dict.fromkeys(urls))  # de-dupe, preserve order


def fetch_image(arxiv_id: str, src: str) -> bytes:
    last_err = None
    for url in candidate_image_urls(arxiv_id, src):
        try:
            return fetch(url)
        except Exception as e:
            last_err = e
            continue
    raise last_err if last_err else RuntimeError("no candidates")


def resize_to_jpeg(src_path: Path, dst_path: Path, width: int = 1200, quality: int = 82):
    subprocess.run(
        [
            "sips",
            "--resampleWidth", str(width),
            "--setProperty", "format", "jpeg",
            "--setProperty", "formatOptions", str(quality),
            str(src_path),
            "--out", str(dst_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


PAPER_BLOCK = re.compile(r'(<li class="paper"[^>]*>)(.*?)(</li>)', re.DOTALL)
ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")


def iter_papers(html: str):
    """Yield (match, opener, body, closer, arxiv_id) for each paper li."""
    for m in PAPER_BLOCK.finditer(html):
        opener, body, closer = m.group(1), m.group(2), m.group(3)
        m_id = ARXIV_RE.search(body)
        if not m_id:
            continue
        yield m, opener, body, closer, m_id.group(1)


def add_data_figure(opener: str, figure_path: str) -> str:
    if "data-figure=" in opener:
        return re.sub(
            r'data-figure="[^"]*"',
            f'data-figure="{figure_path}"',
            opener,
        )
    return opener[:-1] + f' data-figure="{figure_path}">'


def process_one(arxiv_id: str, mode: str) -> str | None:
    """Returns the figure path (relative to repo root) on success, else None."""
    out_dir = ASSETS / arxiv_id
    teaser_path = out_dir / "teaser.jpg"

    if mode == "auto" and teaser_path.exists():
        print(f"  exists: {teaser_path.relative_to(ROOT)}")
        return f"assets/{arxiv_id}/teaser.jpg"

    try:
        page = fetch(f"https://arxiv.org/html/{arxiv_id}").decode("utf-8", "replace")
    except Exception as e:
        print(f"  ! arxiv html fetch failed: {e}")
        return None

    finder = ArxivFigureFinder()
    finder.feed(page)
    landscape = [f for f in finder.figures if "ltx_img_landscape" in f["classes"]]
    if not landscape:
        print("  ! no landscape figures in arxiv html")
        return None

    print(f"  found {len(landscape)} landscape figure(s)")

    if mode == "list":
        cand_dir = out_dir / "candidates"
        cand_dir.mkdir(parents=True, exist_ok=True)
        for i, fig in enumerate(landscape, 1):
            print(f"    [{i}] {fig['width']}x{fig['height']}  {fig['src']}")
            try:
                data = fetch_image(arxiv_id, fig["src"])
            except Exception as e:
                print(f"    ! download failed: {e}")
                continue
            ext = Path(fig["src"]).suffix.lower() or ".png"
            tmp = cand_dir / f"{i}_src{ext}"
            tmp.write_bytes(data)
            preview = cand_dir / f"{i}.jpg"
            try:
                resize_to_jpeg(tmp, preview)
            finally:
                tmp.unlink(missing_ok=True)
        return None

    # auto mode: take first landscape
    fig = landscape[0]
    print(f"  picking first landscape: {fig['src']} ({fig['width']}x{fig['height']})")
    try:
        data = fetch_image(arxiv_id, fig["src"])
    except Exception as e:
        print(f"  ! image download failed: {e}")
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(fig["src"]).suffix.lower() or ".png"
    tmp = out_dir / f"_src{ext}"
    tmp.write_bytes(data)
    try:
        resize_to_jpeg(tmp, teaser_path)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"  -> {teaser_path.relative_to(ROOT)} ({teaser_path.stat().st_size} bytes)")
    return f"assets/{arxiv_id}/teaser.jpg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="don't download or modify any files")
    ap.add_argument("--list", action="store_true",
                    help="download all landscape candidates per paper for review")
    ap.add_argument("--only", metavar="ARXIV_ID",
                    help="process only this paper")
    ap.add_argument("--force", action="store_true",
                    help="re-download even if teaser.jpg already exists")
    args = ap.parse_args()

    mode = "list" if args.list else "auto"
    html = PUB_HTML.read_text()
    edits = []  # list of (start, end, replacement)

    seen = set()
    for m, opener, body, closer, arxiv_id in iter_papers(html):
        if args.only and arxiv_id != args.only:
            continue
        if arxiv_id in seen:
            continue
        seen.add(arxiv_id)
        print(f"\n=== {arxiv_id} ===")

        if "data-figure=" in opener and not args.force:
            print("  has data-figure already, skipping (use --force to redo)")
            continue

        if args.dry_run:
            print("  (dry-run)")
            continue

        figure_path = process_one(arxiv_id, mode)
        if figure_path and mode == "auto":
            new_opener = add_data_figure(opener, figure_path)
            edits.append((m.start(1), m.end(1), new_opener))

    if args.dry_run or not edits:
        if not args.dry_run:
            print("\nno HTML changes")
        return

    # apply edits in reverse so offsets stay valid
    edits.sort(reverse=True)
    new_html = html
    for start, end, replacement in edits:
        new_html = new_html[:start] + replacement + new_html[end:]
    PUB_HTML.write_text(new_html)
    print(f"\nupdated {PUB_HTML.name} ({len(edits)} paper(s))")


if __name__ == "__main__":
    main()
