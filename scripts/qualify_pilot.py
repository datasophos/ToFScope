"""Local read-only qualification with explicit fixture identities, never a live proxy.

The app runs under TestClient's isolated peer; no production identity is forged.
"""

import argparse
import json
from pathlib import Path
import resource
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from tofscope.config import Settings
from tofscope.api.app import create_app


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tofscope-qualification-") as directory:
        settings = Settings(
            a.data_root,
            runtime_dir=Path(directory),
            mode="proxy",
            trusted_proxies=("testclient",),
            public_origin="http://testserver",
        )
        app = create_app(settings)
        with TestClient(app) as c:
            headers = {
                o: {"x-tofscope-user": o, "Origin": "http://testserver"}
                for o in ("fixture-a", "fixture-b")
            }
            analyses = {}
            timings = []
            payload = []
            for o in headers:
                w = c.post("/api/v1/workspaces", headers=headers[o]).json()
                analyses[o] = []
                for _ in range(3):
                    response = c.post(
                        f"/api/v1/workspaces/{w['id']}/analyses",
                        headers=headers[o],
                        json={"relative_path": a.file},
                    )
                    response.raise_for_status()
                    analyses[o].append(response.json())
            active = analyses["fixture-a"][0]
            other = analyses["fixture-b"][0]
            owner = headers["fixture-a"]
            aid = active["id"]
            generation = active["dataset"]["generation"]
            denied = (
                c.get(
                    f"/api/v1/analyses/{aid}", headers=headers["fixture-b"]
                ).status_code
                == 404
            )
            for i in range(12):
                start = time.perf_counter()
                r = c.post(
                    f"/api/v1/analyses/{aid}/commands",
                    headers=owner,
                    json={
                        "request_id": f"roi-{i}",
                        "expected_revision": i,
                        "dataset_generation": generation,
                        "command": {
                            "type": "set_roi",
                            "roi": [
                                i % active["shape"][2],
                                active["shape"][2] - 1,
                                0,
                                active["shape"][1] - 1,
                            ],
                        },
                    },
                )
                r.raise_for_status()
                timings.append((time.perf_counter() - start) * 1000)
            response = c.get(f"/api/v1/analyses/{aid}/data", headers=owner)
            response.raise_for_status()
            payload.append(len(response.content))
            assert (
                c.get(
                    f"/api/v1/analyses/{other['id']}", headers=headers["fixture-b"]
                ).json()["revision"]
                == 0
            )
            last = min(63, active["shape"][0] - 1)
            job = c.post(
                f"/api/v1/analyses/{aid}/jobs",
                headers=owner,
                json={
                    "request_id": "integrate",
                    "expected_revision": 12,
                    "dataset_generation": generation,
                    "spec": {
                        "intervals": next(row["recipe"]["intervals"] for row in active["signals"] if row["id"] == active["image_signal_id"]),
                        "frames": [0, last],
                        "name": "Qualification signal",
                    },
                },
            )
            job.raise_for_status()
            jid = job.json()["id"]
            health = []
            states = []
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                start = time.perf_counter()
                c.get("/healthz").raise_for_status()
                health.append((time.perf_counter() - start) * 1000)
                status = c.get(f"/api/v1/jobs/{jid}", headers=owner).json()
                states.append(status["status"])
                if status["status"] in ("succeeded", "failed", "cancelled", "obsolete"):
                    break
                time.sleep(0.01)
            assert status["status"] == "succeeded", status
            cache = app.state.services.cache
            result = {
                "users": 2,
                "analyses": 6,
                "same_file": True,
                "foreign_denied": denied,
                "independent_revision": True,
                "selection_p50_ms": statistics.median(timings),
                "selection_p95_ms": sorted(timings)[int(0.95 * (len(timings) - 1))],
                "health_p95_ms": sorted(health)[int(0.95 * (len(health) - 1))],
                "payload_bytes": payload,
                "job_states": list(dict.fromkeys(states)),
                "managed_bytes": cache.budget.physical_bytes,
                "peak_rss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "external_services_modified": False,
            }
            assert result["health_p95_ms"] < 250, result
            (a.output / "qualification.json").write_text(json.dumps(result, indent=2))
            print(json.dumps(result))


if __name__ == "__main__":
    main()
