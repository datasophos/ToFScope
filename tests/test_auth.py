import unittest
from fastapi.testclient import TestClient
from service_fixture import setup_case
from tofscope.api.app import create_app


class AuthTests(unittest.TestCase):
    def test_local_one_use_bootstrap_csrf_and_spoofed_identity(self):
        setup_case(self, public_origin="http://testserver")
        app = create_app(self.settings, bootstrap_secret="test-secret")
        with TestClient(app) as c:
            h = {"Origin": "http://testserver"}
            self.assertEqual(c.post("/api/v1/workspaces", headers=h).status_code, 401)
            r = c.post(
                "/api/v1/auth/bootstrap", json={"secret": "test-secret"}, headers=h
            )
            self.assertEqual(r.status_code, 200)
            self.assertIn("HttpOnly", r.headers["set-cookie"])
            csrf = r.json()["csrf"]
            self.assertEqual(
                c.post(
                    "/api/v1/auth/bootstrap", json={"secret": "test-secret"}, headers=h
                ).status_code,
                401,
            )
            self.assertEqual(c.post("/api/v1/workspaces", headers=h).status_code, 403)
            self.assertEqual(
                c.post(
                    "/api/v1/workspaces", headers=h | {"X-CSRF-Token": csrf}
                ).status_code,
                200,
            )
            self.assertEqual(
                c.get(
                    "/api/v1/workspaces", headers={"x-tofscope-user": "forged"}
                ).status_code,
                401,
            )
            self.assertEqual(
                c.post(
                    "/api/v1/workspaces",
                    headers=h | {"X-CSRF-Token": csrf, "Host": "evil.test"},
                ).status_code,
                403,
            )

    def test_untrusted_proxy_rejected(self):
        setup_case(
            self,
            mode="proxy",
            trusted_proxies=("127.0.0.1",),
            public_origin="http://testserver",
        )
        with TestClient(create_app(self.settings)) as c:
            self.assertEqual(
                c.get(
                    "/api/v1/workspaces", headers={"x-tofscope-user": "a"}
                ).status_code,
                401,
            )
