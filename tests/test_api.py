import unittest
from fastapi.testclient import TestClient
from service_fixture import setup_case
from tofscope.api.app import create_app


class APITests(unittest.TestCase):
    def setUp(self):
        setup_case(
            self,
            mode="proxy",
            trusted_proxies=("testclient",),
            public_origin="http://testserver",
        )
        self.client = TestClient(create_app(self.settings))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.a = {"x-tofscope-user": "a", "Origin": "http://testserver"}
        self.b = {"x-tofscope-user": "b", "Origin": "http://testserver"}

    def test_ownership_revisions_and_safe_errors(self):
        c = self.client
        self.assertEqual(c.get("/api/v1/workspaces").status_code, 401)
        w = c.post("/api/v1/workspaces", headers=self.a).json()
        r = c.post(
            f"/api/v1/workspaces/{w['id']}/analyses",
            headers=self.a,
            json={"relative_path": "a.h5"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        a = r.json()
        aid = a["id"]
        self.assertEqual(
            c.get(f"/api/v1/analyses/{aid}", headers=self.b).status_code, 404
        )
        cmd = {
            "request_id": "roi",
            "expected_revision": 0,
            "dataset_generation": a["dataset"]["generation"],
            "command": {"type": "set_roi", "roi": [1, 1, 0, 0]},
        }
        r = c.post(f"/api/v1/analyses/{aid}/commands", json=cmd, headers=self.a)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["revision"], 1)
        self.assertEqual(
            c.post(f"/api/v1/analyses/{aid}/commands", json=cmd, headers=self.a).json()[
                "revision"
            ],
            1,
        )
        cmd["request_id"] = "new"
        self.assertEqual(
            c.post(
                f"/api/v1/analyses/{aid}/commands", json=cmd, headers=self.a
            ).status_code,
            409,
        )
        self.assertEqual(c.get("/api/v1/unknown", headers=self.a).status_code, 404)
        self.assertEqual(
            c.post(
                "/api/v1/workspaces", headers=self.a | {"Origin": "http://evil.test"}
            ).status_code,
            403,
        )
        self.assertEqual(
            c.post(
                f"/api/v1/workspaces/{w['id']}/analyses",
                headers=self.a,
                json={"relative_path": "a.h5", "owner": "b"},
            ).status_code,
            422,
        )
        self.assertNotIn(
            str(self.settings.data_root),
            c.get("/api/v1/files?directory=../", headers=self.a).text,
        )

    def test_views_and_jobs_are_owner_scoped(self):
        c = self.client
        w = c.post("/api/v1/workspaces", headers=self.a).json()
        a = c.post(
            f"/api/v1/workspaces/{w['id']}/analyses",
            headers=self.a,
            json={"relative_path": "a.h5"},
        ).json()
        aid = a["id"]
        v = c.post(f"/api/v1/analyses/{aid}/views", headers=self.a).json()
        self.assertEqual(
            c.post(f"/api/v1/views/{v['id']}/heartbeat", headers=self.b).status_code,
            404,
        )
        j = c.post(
            f"/api/v1/analyses/{aid}/jobs",
            headers=self.a,
            json={
                "request_id": "job",
                "expected_revision": 0,
                "dataset_generation": a["dataset"]["generation"],
                "spec": {
                    "intervals": [[1, 2], [4, 5]],
                    "frames": [0, 2],
                    "name": "Ti",
                },
            },
        )
        self.assertEqual(j.status_code, 202, j.text)
        id = j.json()["id"]
        self.assertEqual(c.get(f"/api/v1/jobs/{id}", headers=self.b).status_code, 404)

    def test_api_rejects_foreign_signal_and_legacy_target(self):
        c = self.client
        workspace = c.post('/api/v1/workspaces', headers=self.a).json()
        a = c.post(f"/api/v1/workspaces/{workspace['id']}/analyses", headers=self.a, json={'relative_path':'a.h5'}).json()
        base = {'request_id':'legacy','expected_revision':a['revision'],'dataset_generation':a['dataset']['generation']}
        bad = c.post(f"/api/v1/analyses/{a['id']}/jobs", headers=self.a, json=base | {'spec':{'intervals':[[1,2]],'frames':[0,2],'target':'active'}})
        self.assertEqual(bad.status_code, 422)
        workspace_b = c.post('/api/v1/workspaces', headers=self.b).json()
        b = c.post(f"/api/v1/workspaces/{workspace_b['id']}/analyses", headers=self.b, json={'relative_path':'a.h5'}).json()
        response = c.post(f"/api/v1/analyses/{a['id']}/commands", headers=self.a, json=base | {'command':{'type':'select_image_signal','signal_id':b['image_signal_id']}})
        self.assertEqual(response.status_code, 422)
