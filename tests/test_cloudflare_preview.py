"""Tests for cleanup of documentation preview deployments."""

import unittest
from unittest.mock import patch

from scripts.cloudflare_previews import make_plan, pages


class PreviewPlanTests(unittest.TestCase):
    def test_cloudflare_pagination_uses_supported_page_size(self):
        with patch("scripts.cloudflare_previews.request") as request:
            request.return_value = {
                "result": [{"id": "d1"}],
                "result_info": {"total_pages": 1},
            }
            self.assertEqual(
                pages("https://example.test/deployments?env=preview", "token", True),
                [{"id": "d1"}],
            )
            self.assertIn("per_page=25", request.call_args.args[0])

    def test_closed_branch_deployments_are_selected(self):
        prs = [{"state": "closed", "head": {"ref": "docs-cleanup"}}]
        deployments = [
            {
                "id": "d1",
                "environment": "preview",
                "deployment_trigger": {"metadata": {"branch": "docs-cleanup"}},
            },
            {
                "id": "d2",
                "environment": "production",
                "deployment_trigger": {"metadata": {"branch": "docs-cleanup"}},
            },
        ]
        self.assertEqual(make_plan(prs, deployments), ["d1"])

    def test_shared_open_branch_is_not_deleted(self):
        prs = [
            {"state": "closed", "head": {"ref": "shared"}},
            {"state": "open", "head": {"ref": "shared"}},
        ]
        deployments = [
            {
                "id": "d1",
                "environment": "preview",
                "deployment_trigger": {"metadata": {"branch": "shared"}},
            }
        ]
        self.assertEqual(make_plan(prs, deployments), [])
