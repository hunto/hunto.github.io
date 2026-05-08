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
TITLE_RE = re.compile(r"<pt>\s*<a[^>]*>(.*?)</a>\s*</pt>", re.DOTALL)
SKIP_WORDS = {"a", "an", "the", "of", "for", "in", "on", "with", "to", "and",
              "or", "is", "are", "from", "via", "by"}


def slug_from_title(title: str, max_words: int = 2) -> str:
    """seeing_realism style slug — first N significant alphanumeric words,
    lowercased. Articles, prepositions, and other low-content words are
    dropped wherever they appear."""
    words = re.sub(r"[^a-zA-Z0-9]+", " ", title).split()
    significant = [w for w in words if w.lower() not in SKIP_WORDS]
    return "_".join(w.lower() for w in significant[:max_words]) or "paper"


def iter_papers(html: str):
    """Yield (match, opener, body, closer, arxiv_id, title) for each paper li."""
    for m in PAPER_BLOCK.finditer(html):
        opener, body, closer = m.group(1), m.group(2), m.group(3)
        m_id = ARXIV_RE.search(body)
        if not m_id:
            continue
        m_title = TITLE_RE.search(body)
        title = re.sub(r"\s+", " ", m_title.group(1)).strip() if m_title else ""
        yield m, opener, body, closer, m_id.group(1), title


def add_data_figure(opener: str, figure_path: str) -> str:
    if "data-figure=" in opener:
        return re.sub(
            r'data-figure="[^"]*"',
            f'data-figure="{figure_path}"',
            opener,
        )
    return opener[:-1] + f' data-figure="{figure_path}">'


def asset_dir_for(slug: str) -> Path:
    return ASSETS / "papers" / slug


def process_one(arxiv_id: str, slug: str, mode: str) -> str | None:
    """Returns the figure path (relative to repo root) on success, else None."""
    out_dir = asset_dir_for(slug)
    teaser_path = out_dir / "teaser.jpg"
    rel_path = f"assets/papers/{slug}/teaser.jpg"

    if mode == "auto" and teaser_path.exists():
        print(f"  exists: {teaser_path.relative_to(ROOT)}")
        return rel_path

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
    return rel_path


def migrate_paths(html: str) -> tuple[str, int]:
    """Move any assets/<arxiv-id>/teaser.jpg to assets/papers/<slug>/teaser.jpg
    and rewrite the data-figure attribute. Returns (new_html, moved_count)."""
    edits = []
    moved = 0
    used_slugs = set()
    for m, opener, body, closer, arxiv_id, title in iter_papers(html):
        attr = re.search(r'data-figure="([^"]+)"', opener)
        if not attr:
            continue
        old_path = attr.group(1)
        if old_path.startswith("assets/papers/"):
            # already migrated; remember slug to avoid collisions
            seg = old_path.split("/")[2] if len(old_path.split("/")) > 2 else ""
            if seg:
                used_slugs.add(seg)
            continue
        slug = slug_from_title(title)
        # disambiguate against earlier papers with the same first words
        base, n = slug, 2
        while slug in used_slugs:
            slug = f"{base}_{n}"
            n += 1
        used_slugs.add(slug)
        new_path = f"assets/papers/{slug}/teaser.jpg"
        old_file = ROOT / old_path
        new_file = ROOT / new_path
        new_file.parent.mkdir(parents=True, exist_ok=True)
        if old_file.exists() and not new_file.exists():
            shutil.move(str(old_file), str(new_file))
            try:
                old_file.parent.rmdir()
            except OSError:
                pass
            moved += 1
            print(f"  {arxiv_id} ({title[:40]!r:<42}) -> assets/papers/{slug}/")
        new_opener = re.sub(
            r'data-figure="[^"]*"',
            f'data-figure="{new_path}"',
            opener,
        )
        edits.append((m.start(1), m.end(1), new_opener))
    edits.sort(reverse=True)
    for start, end, replacement in edits:
        html = html[:start] + replacement + html[end:]
    return html, moved


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
    ap.add_argument("--migrate", action="store_true",
                    help="rename assets/<arxiv-id>/ -> assets/papers/<slug>/ and rewrite HTML")
    args = ap.parse_args()

    html = PUB_HTML.read_text()

    if args.migrate:
        new_html, moved = migrate_paths(html)
        if new_html != html:
            PUB_HTML.write_text(new_html)
            print(f"\nmigrated {moved} file(s); rewrote {PUB_HTML.name}")
        else:
            print("\nnothing to migrate")
        return

    mode = "list" if args.list else "auto"
    edits = []  # list of (start, end, replacement)

    # Pre-compute slugs and disambiguate against existing dirs and each other
    used_slugs = {p.name for p in (ASSETS / "papers").glob("*") if p.is_dir()} if (ASSETS / "papers").exists() else set()

    seen = set()
    for m, opener, body, closer, arxiv_id, title in iter_papers(html):
        if args.only and arxiv_id != args.only:
            continue
        if arxiv_id in seen:
            continue
        seen.add(arxiv_id)
        print(f"\n=== {arxiv_id} :: {title[:60]} ===")

        if "data-figure=" in opener and not args.force:
            print("  has data-figure already, skipping (use --force to redo)")
            continue

        if args.dry_run:
            print("  (dry-run)")
            continue

        # Pick a slug; reuse if this paper already has a matching dir, else
        # disambiguate against any existing slugs.
        base = slug_from_title(title)
        slug, n = base, 2
        while slug in used_slugs and not (asset_dir_for(slug) / "teaser.jpg").exists():
            slug = f"{base}_{n}"
            n += 1
        used_slugs.add(slug)

        figure_path = process_one(arxiv_id, slug, mode)
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
