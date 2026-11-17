"""Build documentation with a public release-feed fallback for API rate limits."""

import re
from functools import lru_cache
from urllib.parse import quote, unquote
from xml.etree import ElementTree

import requests
from great_docs.cli import cli
from great_docs.core import GreatDocs

ATOM = "{http://www.w3.org/2005/Atom}"
_original_fetch = GreatDocs._fetch_github_releases


@lru_cache(maxsize=128)
def release_metadata(url):
    """Distinguish published releases from tag-only feed entries."""
    response = requests.get(url, headers={"Accept-Language": "en-US"}, timeout=30)
    response.raise_for_status()
    page = response.text
    if "released this" in page:
        match = re.search(r'released this\s*<relative-time[^>]*datetime="([^"]+)"', page)
        if not match:
            raise ValueError(f"Cannot find publication date for {url}")
        return match.group(1), "Pre-release" in page
    if 'class="release-header"' in page:
        return None
    raise ValueError(f"Cannot determine whether {url} is a published release")


def fetch_releases(self, owner, repo, max_releases=50):
    """Use the normal API first, then the paginated public Atom feed."""
    releases = _original_fetch(self, owner, repo, max_releases)
    if releases:
        return releases
    releases = []
    seen = set()
    cursor = None
    while len(releases) < max_releases:
        url = f"https://github.com/{owner}/{repo}/releases.atom"
        if cursor:
            url += "?after=" + quote(cursor, safe="")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        entries = ElementTree.fromstring(response.content).findall(f"{ATOM}entry")
        if not entries:
            break
        for entry in entries:
            link = entry.find(f"{ATOM}link")
            href = link.get("href", "") if link is not None else ""
            tag = unquote(href.rsplit("/", 1)[-1])
            if not tag or tag in seen:
                raise ValueError("Invalid or repeated tag in release feed")
            seen.add(tag)
            cursor = tag
            metadata = release_metadata(href)
            if metadata is None:
                continue
            published, prerelease = metadata
            releases.append({
                "tag_name": tag,
                "name": entry.findtext(f"{ATOM}title", default=tag),
                "body": entry.findtext(f"{ATOM}content", default=""),
                "published_at": published,
                "html_url": href,
                "prerelease": prerelease,
            })
            if len(releases) >= max_releases:
                break
    if not releases:
        raise ValueError("No published releases found in GitHub API or Atom feed")
    print(f"Using GitHub Atom feed for {len(releases)} published releases")
    return releases


if __name__ == "__main__":
    GreatDocs._fetch_github_releases = fetch_releases
    cli(["build"])
