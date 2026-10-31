"""Reconcile Pages preview domains with ToFScope pull requests."""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ACCOUNT = "c924686e1dae7243fe6e51e23e6a9735"
ZONE = "9212207752ff5d7f475ce53a11058fb5"
PROJECT = "tofscope-docs"
DOMAIN = "datasophos.co"
CF = "https://api.cloudflare.com/client/v4"
GH = "https://api.github.com/repos/datasophos/ToFScope"
PREFIX = f"/accounts/{ACCOUNT}/pages/projects/{PROJECT}"


def branch_of(deployment):
    return deployment.get("deployment_trigger", {}).get("metadata", {}).get("branch")


def make_plan(prs, deployments, domains, records):
    """Plan idempotent changes; never delete deployments used by an open PR."""
    plan = {
        "ensure": [],
        "delete_domains": [],
        "delete_records": [],
        "delete_deployments": [],
    }
    opened = {pr["head"]["ref"] for pr in prs if pr["state"] == "open"}
    closed = set()
    for pr in prs:
        branch = pr["head"]["ref"]
        hostname = f"tofscope-pr-{pr['number']}.{DOMAIN}"
        if pr["state"] == "open":
            for deployment in deployments:
                if (
                    deployment.get("environment") == "preview"
                    and branch_of(deployment) == branch
                    and deployment.get("latest_stage", {}).get("status") == "success"
                ):
                    aliases = deployment.get("aliases") or []
                    for alias in aliases:
                        host = urllib.parse.urlparse(alias).hostname or ""
                        if host.endswith(f".{PROJECT}.pages.dev"):
                            if not any(
                                d["name"] == hostname
                                and (
                                    d.get("status") == "active"
                                    or d.get("verification_data", {}).get("status")
                                    == "active"
                                )
                                for d in domains
                            ):
                                host = f"{PROJECT}.pages.dev"
                            plan["ensure"].append((hostname, host))
                            break
                    else:
                        continue
                    break
        else:
            if branch not in opened:
                closed.add(branch)
            if any(d["name"] == hostname for d in domains):
                plan["delete_domains"].append(hostname)
            for record in records:
                if record["name"] == hostname and record["type"] == "CNAME":
                    plan["delete_records"].append(record["id"])
    plan["delete_deployments"] = [
        d["id"]
        for d in deployments
        if d.get("environment") == "preview" and branch_of(d) in closed
    ]
    return plan


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
    domains = pages(f"{CF}{PREFIX}/domains", cf_token, True)
    records = pages(f"{CF}/zones/{ZONE}/dns_records?type=CNAME", cf_token, True)
    plan = make_plan(prs, deployments, domains, records)
    for hostname, target in plan["ensure"]:
        if not any(d["name"] == hostname for d in domains):
            request(f"{CF}{PREFIX}/domains", cf_token, "POST", {"name": hostname})
        existing = [r for r in records if r["name"] == hostname]
        record = {
            "type": "CNAME",
            "name": hostname,
            "content": target,
            "proxied": True,
            "ttl": 1,
        }
        if not existing:
            request(f"{CF}/zones/{ZONE}/dns_records", cf_token, "POST", record)
        elif len(existing) == 1 and (
            existing[0]["content"] != target or not existing[0]["proxied"]
        ):
            request(
                f"{CF}/zones/{ZONE}/dns_records/{existing[0]['id']}",
                cf_token,
                "PUT",
                record,
            )
    for record_id in plan["delete_records"]:
        request(f"{CF}/zones/{ZONE}/dns_records/{record_id}", cf_token, "DELETE")
    for hostname in plan["delete_domains"]:
        request(f"{CF}{PREFIX}/domains/{hostname}", cf_token, "DELETE")
    for deployment_id in plan["delete_deployments"]:
        request(
            f"{CF}{PREFIX}/deployments/{deployment_id}?force=true", cf_token, "DELETE"
        )
    print(json.dumps({key: len(value) for key, value in plan.items()}))


if __name__ == "__main__":
    try:
        main()
    except (KeyError, RuntimeError, OSError) as exc:
        print(f"Preview reconciliation failed: {exc}", file=sys.stderr)
        sys.exit(1)
