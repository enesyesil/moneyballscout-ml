"""Small Coolify API client for the GitHub Actions workflows (stdlib only, no installs on the runner).

  configure       upsert env vars on the Coolify application; --generate creates a secret only if it is unset
  deploy          trigger a deployment and wait for it to finish (prints the build log tail on failure)
  wait-healthy    poll <site>/api/health until it answers (optionally until it reports the expected commit)
  wait-first-run  poll <site>/api/models/runs until the first model run finishes

Reads COOLIFY_URL, COOLIFY_TOKEN and COOLIFY_APP_UUID from the environment.
"""

import argparse
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DONE_OK = {"finished"}
DONE_FAIL = {"failed", "cancelled-by-user", "cancelled"}


def _env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        sys.exit(f"::error::{name} is not set")
    return v


def _request(method: str, url: str, body: dict | None = None, token: str | None = None, timeout: int = 30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else None


def api(method: str, path: str, body: dict | None = None):
    base = _env("COOLIFY_URL").rstrip("/")
    if not base.endswith("/api/v1"):
        base += "/api/v1"
    try:
        return _request(method, f"{base}{path}", body, token=_env("COOLIFY_TOKEN"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        sys.exit(f"::error::Coolify {method} {path} -> HTTP {e.code}: {detail}")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        sys.exit(f"::error::cannot reach Coolify at {base} ({getattr(e, 'reason', e)}) - check COOLIFY_URL")


def summary(text: str) -> None:
    print(text)
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(path, "a") as f:
            f.write(text + "\n")


# ---- configure

def configure(args) -> None:
    app = _env("COOLIFY_APP_UUID")
    existing = {e["key"]: e for e in api("GET", f"/applications/{app}/envs") or [] if not e.get("is_preview")}
    data: list[dict] = []
    for item in args.set or []:
        key, sep, value = item.partition("=")
        if not sep:
            sys.exit(f"::error::--set expects KEY=VALUE, got {item!r}")
        if value == "":
            print(f"skip {key}: empty value")
            continue
        data.append({"key": key, "value": value})
    for key in args.generate or []:
        cur = existing.get(key)
        if cur is not None and "value" not in cur and "real_value" not in cur:
            # token cannot read values: never risk overwriting a live database password
            print(f"::warning::{key} exists but its value is hidden from this token; leaving it unchanged")
            continue
        if cur is not None and (cur.get("real_value") or cur.get("value")):
            print(f"keep {key}: already set")
            continue
        data.append({"key": key, "value": secrets.token_urlsafe(32)})
        print(f"generate {key}")
    if not data:
        print("nothing to update")
        return
    api("PATCH", f"/applications/{app}/envs/bulk", {"data": [{**d, "is_preview": False} for d in data]})
    after = {e["key"] for e in api("GET", f"/applications/{app}/envs") or [] if not e.get("is_preview")}
    missing = [d["key"] for d in data if d["key"] not in after]
    if missing:
        sys.exit(f"::error::Coolify did not store: {', '.join(missing)}")
    summary("Configured on Coolify: " + ", ".join(f"`{d['key']}`" for d in data))


# ---- deploy

def _log_tail(dep: dict, n: int = 60) -> str:
    logs = dep.get("logs")
    try:
        entries = json.loads(logs) if isinstance(logs, str) else (logs or [])
        lines = [e.get("output", "") for e in entries if not e.get("hidden")]
    except (ValueError, AttributeError):
        lines = str(logs or "").splitlines()
    return "\n".join(lines[-n:])


def deploy(args) -> None:
    app = _env("COOLIFY_APP_UUID")
    q = urllib.parse.urlencode({"uuid": app, "force": str(args.force).lower()})
    res = api("POST", f"/deploy?{q}") or {}
    deps = res.get("deployments") or []
    if not deps or not deps[0].get("deployment_uuid"):
        sys.exit(f"::error::Coolify did not queue a deployment: {json.dumps(res)[:500]}")
    dep_uuid = deps[0]["deployment_uuid"]
    print(f"deployment {dep_uuid} queued")
    deadline = time.time() + args.timeout
    status = last = None
    while time.time() < deadline:
        dep = api("GET", f"/deployments/{dep_uuid}") or {}
        status = dep.get("status")
        if status != last:
            print(f"  status: {status}")
            last = status
        if status in DONE_OK:
            commit = dep.get("commit")
            summary(f"Deployed `{commit or 'unknown commit'}` (Coolify deployment `{dep_uuid}`)")
            if args.expect_commit and commit and not args.expect_commit.startswith(commit) and not commit.startswith(args.expect_commit):
                print(f"::warning::Coolify built {commit}, this workflow is for {args.expect_commit} (a newer push may have landed)")
            return
        if status in DONE_FAIL:
            print("::group::Coolify build log (tail)")
            print(_log_tail(dep))
            print("::endgroup::")
            sys.exit(f"::error::Coolify deployment {dep_uuid} {status}")
        time.sleep(10)
    sys.exit(f"::error::deployment {dep_uuid} still {status} after {args.timeout}s")


# ---- site checks

def _get_json(url: str):
    try:
        return _request("GET", url, timeout=15)
    except (urllib.error.URLError, TimeoutError, ValueError, ConnectionError):
        return None


def wait_healthy(args) -> None:
    site = args.site.rstrip("/")
    deadline = time.time() + args.timeout
    body = None
    while time.time() < deadline:
        body = _get_json(f"{site}/api/health")
        if body and body.get("status") == "ok":
            sha = body.get("git_sha")
            if not args.expect_commit or not sha or sha.startswith(args.expect_commit[:7]):
                summary(f"Health check passed: {site}/api/health (commit `{sha or 'not reported'}`)")
                return
        time.sleep(10)
    sys.exit(f"::error::{site}/api/health not healthy after {args.timeout}s (last response: {body})")


def wait_first_run(args) -> None:
    site = args.site.rstrip("/")
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        runs = _get_json(f"{site}/api/models/runs?limit=5") or []
        done = [r for r in runs if r.get("status") in ("success", "failed")]
        if done:
            r = done[0]
            status = _get_json(f"{site}/api/admin/sync-status") or {}
            summary(f"First model run #{r.get('id')}: **{r.get('status')}**")
            summary("```json\n" + json.dumps(status, indent=2) + "\n```")
            if r["status"] == "failed":
                print("::warning::the first run failed; it is usually missing data on day one and retries at the daily sync")
            return
        status = _get_json(f"{site}/api/admin/sync-status") or {}
        print(f"  waiting: used {status.get('used_today', '?')}/{status.get('daily_quota', '?')} requests, "
              f"{status.get('fixtures_with_player_stats', '?')} matches with player stats")
        time.sleep(60)
    print(f"::warning::no model run after {args.timeout}s; the worker keeps going on its own, check the Models page later")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("configure")
    c.add_argument("--set", action="append", metavar="KEY=VALUE")
    c.add_argument("--generate", action="append", metavar="KEY")
    c.set_defaults(fn=configure)
    d = sub.add_parser("deploy")
    d.add_argument("--force", action="store_true", help="rebuild without cache")
    d.add_argument("--expect-commit", default="")
    d.add_argument("--timeout", type=int, default=1800)
    d.set_defaults(fn=deploy)
    h = sub.add_parser("wait-healthy")
    h.add_argument("--site", required=True)
    h.add_argument("--expect-commit", default="")
    h.add_argument("--timeout", type=int, default=300)
    h.set_defaults(fn=wait_healthy)
    r = sub.add_parser("wait-first-run")
    r.add_argument("--site", required=True)
    r.add_argument("--timeout", type=int, default=3600)
    r.set_defaults(fn=wait_first_run)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
