"""Tests for cleanup of documentation preview deployments."""

import unittest

from scripts.cloudflare_previews import make_plan


class PreviewPlanTests(unittest.TestCase):
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
