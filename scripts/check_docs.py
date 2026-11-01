"""Check local links, anchors, and assets in a rendered documentation site."""

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.ids = set()
        self.links = []
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("name"):
            self.ids.add(attrs["name"])
        for key in ("href", "src"):
            if attrs.get(key):
                self.links.append(attrs[key])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    parser.add_argument("--base-path", default="/ToFScope/")
    args = parser.parse_args()
    site = args.site.resolve()
    pages = {path: Page(path) for path in site.rglob("*.html")}
    if site / "index.html" not in pages:
        parser.error(f"No index.html in {site}; build the documentation first.")
    errors = set()
    checked = 0
    for path, page in pages.items():
        for link in page.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            local = unquote(url.path)
            if local.startswith(args.base_path):
                local = local[len(args.base_path) :]
                target = site / local
            elif local.startswith("/"):
                target = site / local.lstrip("/")
            else:
                target = path.parent / local if local else path
            if target.is_dir():
                target /= "index.html"
            target = target.resolve()
            checked += 1
            if not target.is_relative_to(site) or not target.is_file():
                errors.add(f"{path.relative_to(site)}: missing target {link}")
            elif (
                url.fragment
                and target in pages
                and unquote(url.fragment) not in pages[target].ids
            ):
                errors.add(f"{path.relative_to(site)}: missing anchor {link}")
    if errors:
        raise SystemExit("\n".join(sorted(errors)))
    print(f"Checked {checked} local references across {len(pages)} HTML pages.")


if __name__ == "__main__":
    main()
