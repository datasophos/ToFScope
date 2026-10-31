"""Tests for the documentation preview lifecycle planner."""

import unittest

from scripts.cloudflare_previews import make_plan


class PreviewPlanTests(unittest.TestCase):
    def test_open_pr_gets_custom_domain_for_successful_branch_alias(self):
        prs = [{"number": 10, "state": "open", "head": {"ref": "docs-cleanup"}}]
        deployments = [
            {
                "id": "d1",
                "environment": "preview",
                "latest_stage": {"status": "success"},
                "deployment_trigger": {"metadata": {"branch": "docs-cleanup"}},
                "aliases": ["https://docs-cleanup.tofscope-docs.pages.dev"],
            }
        ]
        plan = make_plan(prs, deployments, [], [])
        self.assertEqual(
            plan["ensure"],
            [("tofscope-pr-10.datasophos.co", "tofscope-docs.pages.dev")],
        )
        self.assertEqual(plan["delete_deployments"], [])

        plan = make_plan(
            prs,
            deployments,
            [
                {
                    "name": "tofscope-pr-10.datasophos.co",
                    "status": "pending",
                    "verification_data": {"status": "active"},
                }
            ],
            [],
        )
        self.assertEqual(
            plan["ensure"],
            [("tofscope-pr-10.datasophos.co", "docs-cleanup.tofscope-docs.pages.dev")],
        )

    def test_closed_pr_removes_domain_dns_and_branch_deployments(self):
        prs = [{"number": 10, "state": "closed", "head": {"ref": "docs-cleanup"}}]
        deployments = [
            {
                "id": "d1",
                "environment": "preview",
                "deployment_trigger": {"metadata": {"branch": "docs-cleanup"}},
            }
        ]
        domains = [{"name": "tofscope-pr-10.datasophos.co"}]
        records = [
            {"id": "r1", "name": "tofscope-pr-10.datasophos.co", "type": "CNAME"}
        ]
        plan = make_plan(prs, deployments, domains, records)
        self.assertEqual(plan["delete_domains"], ["tofscope-pr-10.datasophos.co"])
        self.assertEqual(plan["delete_records"], ["r1"])
        self.assertEqual(plan["delete_deployments"], ["d1"])

    def test_shared_open_branch_is_not_deleted(self):
        prs = [
            {"number": 10, "state": "closed", "head": {"ref": "shared"}},
            {"number": 11, "state": "open", "head": {"ref": "shared"}},
        ]
        deployments = [
            {
                "id": "d1",
                "environment": "preview",
                "deployment_trigger": {"metadata": {"branch": "shared"}},
            }
        ]
        self.assertEqual(make_plan(prs, deployments, [], [])["delete_deployments"], [])
