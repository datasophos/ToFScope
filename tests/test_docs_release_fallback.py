"""Exercise release-feed pagination without contacting GitHub."""

import importlib.util
import unittest
from unittest.mock import Mock, patch


@unittest.skipUnless(importlib.util.find_spec("great_docs"), "documentation dependencies absent")
class ReleaseFeedTests(unittest.TestCase):
    def test_paginates_and_excludes_unpublished_tags(self):
        from scripts import build_docs

        def feed(tags):
            entries = "".join(
                f'<entry><link href="https://github.com/o/r/releases/tag/{tag}"/>'
                f"<title>{tag}</title><content>notes</content></entry>"
                for tag in tags
            )
            return f'<feed xmlns="http://www.w3.org/2005/Atom">{entries}</feed>'.encode()

        def response(tags):
            result = Mock(content=feed(tags))
            result.raise_for_status.return_value = None
            return result

        pages = [response(["v2", "tag-only"]), response(["v1"]), response([])]
        with (
            patch.object(build_docs, "_original_fetch", return_value=[]),
            patch.object(build_docs.requests, "get", side_effect=pages) as get,
            patch.object(
                build_docs,
                "release_metadata",
                side_effect=[("2026-01-01", False), None, ("2025-01-01", True)],
            ),
        ):
            releases = build_docs.fetch_releases(None, "o", "r", 50)
        self.assertEqual([release["tag_name"] for release in releases], ["v2", "v1"])
        self.assertTrue(releases[1]["prerelease"])
        self.assertTrue(get.call_args_list[1].args[0].endswith("?after=tag-only"))
        self.assertTrue(get.call_args_list[2].args[0].endswith("?after=v1"))
