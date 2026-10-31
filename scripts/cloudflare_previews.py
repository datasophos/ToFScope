"""Clean up Pages preview deployments for closed pull requests."""

import json
import os
import sys
import urllib.error
import urllib.request

ACCOUNT = "c924686e1dae7243fe6e51e23e6a9735"
PROJECT = "tofscope-docs"
CF = "https://api.cloudflare.com/client/v4"
GH = "https://api.github.com/repos/datasophos/ToFScope"
PREFIX = f"/accounts/{ACCOUNT}/pages/projects/{PROJECT}"


def branch_of(deployment):
    return deployment.get("deployment_trigger", {}).get("metadata", {}).get("branch")


def make_plan(prs, deployments):
    """Select closed-PR previews, excluding branches used by an open PR."""
    opened = {pr["head"]["ref"] for pr in prs if pr["state"] == "open"}
    closed = {pr["head"]["ref"] for pr in prs if pr["state"] == "closed"} - opened
    return [
        d["id"]
        for d in deployments
        if d.get("environment") == "preview" and branch_of(d) in closed
    ]


def request(url, token, method="GET", body=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "tofscope-preview-reconciler",
    }
    data = None if body is None else json.dumps(body).encode()
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"{method} {url}: HTTP {error.code}: {error.read().decode()}"
        ) from error
    if isinstance(result, dict) and result.get("success") is False:
        raise RuntimeError(f"{method} {url}: {result.get('errors')}")
    return result


def pages(url, token, cloudflare=False):
    results = []
    for page in range(1, 1001):
        sep = "&" if "?" in url else "?"
        data = request(f"{url}{sep}per_page=100&page={page}", token)
        items = data["result"] if cloudflare else data
        results.extend(items)
        if cloudflare and data.get("result_info", {}).get("total_pages") is not None:
            if page >= data["result_info"]["total_pages"]:
                return results
        elif len(items) < 100:
            return results
    raise RuntimeError(f"Pagination limit reached: {url}")


def main():
    cf_token = os.environ["CLOUDFLARE_PREVIEW_TOKEN"]
    gh_token = os.environ["GH_TOKEN"]
    prs = pages(f"{GH}/pulls?state=all", gh_token)
    prs = [
        pr
        for pr in prs
        if (pr["head"].get("repo") or {}).get("full_name") == "datasophos/ToFScope"
    ]
    deployments = pages(f"{CF}{PREFIX}/deployments?env=preview", cf_token, True)
    plan = make_plan(prs, deployments)
    for deployment_id in plan:
        request(
            f"{CF}{PREFIX}/deployments/{deployment_id}?force=true", cf_token, "DELETE"
        )
    print(f"Deleted {len(plan)} preview deployments.")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, RuntimeError, OSError) as exc:
        print(f"Preview reconciliation failed: {exc}", file=sys.stderr)
        sys.exit(1)
