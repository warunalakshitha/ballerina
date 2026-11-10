"""Print a Markdown table of merge-ready PRs in ballerina-nutcracker/ballerina.

A PR is merge-ready when all of these hold:
- open, not a draft, no don't-merge/dnm/hold/wip label
- GitHub reports it MERGEABLE (no conflicts)
- every CI check on the head passed (skipped/neutral count as passed; pending or failed do not)
- our latest "PR review summary" reviewed the current head and reports 0 findings
- none of our finding threads is unresolved

Usage: python3 ready_table.py            (env REVIEWER defaults to warunalakshitha)
Network failures are retried; a PR whose data can't be fetched is listed under "Could not check".
"""
import json
import os
import re
import subprocess
import time

REPO = "ballerina-nutcracker/ballerina"
OWNER, NAME = REPO.split("/")
ME = os.environ.get("REVIEWER", "warunalakshitha")
THREADS = """query($n:Int!){repository(owner:"%s",name:"%s"){pullRequest(number:$n){
  reviewThreads(first:100){nodes{isResolved comments(first:1){nodes{author{login} body}}}}}}}""" % (OWNER, NAME)
PASSING = {"SUCCESS", "SKIPPED", "NEUTRAL"}


def gh(*args, tries=4):
    err = ""
    for i in range(tries):
        r = subprocess.run(["gh", *args], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
        err = r.stderr.strip()
        time.sleep(3 * (i + 1))
    raise RuntimeError(err[:200])


def summary(n):
    out = gh("api", f"repos/{REPO}/issues/{n}/comments?per_page=100", "--paginate", "--jq",
             f'.[] | select(.user.login=="{ME}") | select(.body|test("PR review summary")) | .body | @json')
    bodies = [json.loads(line) for line in out.splitlines() if line.strip()]
    return bodies[-1] if bodies else ""


def open_threads(n):
    data = json.loads(gh("api", "graphql", "-f", f"query={THREADS}", "-F", f"n={n}"))
    nodes = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    return sum(1 for t in nodes if not t["isResolved"] and t["comments"]["nodes"]
               and t["comments"]["nodes"][0]["author"]["login"] == ME
               and "pre-pr-review:finding" in t["comments"]["nodes"][0]["body"])


def ci(n):
    out = gh("pr", "view", str(n), "--repo", REPO, "--json", "statusCheckRollup")
    checks = json.loads(out)["statusCheckRollup"] or []
    states = [(c.get("conclusion") or c.get("state") or "PENDING").upper() for c in checks]
    failed = [c.get("name") or c.get("context") for c, s in zip(checks, states) if s not in PASSING and s != "PENDING"]
    pending = sum(1 for s in states if s == "PENDING" or s == "")
    return failed, pending


def main():
    prs = json.loads(gh("pr", "list", "--repo", REPO, "--state", "open", "--limit", "200", "--json",
                        "number,title,author,headRefOid,isDraft,labels,mergeable,reviewDecision,url"))
    ready, blocked, unknown = [], [], []
    for p in sorted(prs, key=lambda p: p["number"]):
        n = p["number"]
        if p["isDraft"] or any(re.search("merge|dnm|hold|wip", l["name"], re.I) for l in p["labels"]):
            continue
        try:
            if p["mergeable"] != "MERGEABLE":
                blocked.append((n, "conflicting" if p["mergeable"] == "CONFLICTING" else "mergeability unknown"))
                continue
            body = summary(n)
            shas = re.findall(r"reviewed `([0-9a-f]{7,40})", body)
            if not shas or not p["headRefOid"].startswith(shas[-1]):
                blocked.append((n, "not reviewed at current head"))
                continue
            status = next((line for line in body.splitlines() if "reviewed `" in line), "")
            if not status.startswith("0 findings"):
                blocked.append((n, "open findings"))
                continue
            if open_threads(n):
                blocked.append((n, "unresolved finding threads"))
                continue
            failed, pending = ci(n)
            if failed:
                blocked.append((n, "CI failed: " + ", ".join(failed[:3])))
                continue
            if pending:
                blocked.append((n, f"CI pending ({pending})"))
                continue
        except RuntimeError as e:
            unknown.append((n, str(e)))
            continue
        ready.append(p)
    print("| PR | Title | Author | Approval | Reviewed |")
    print("|---|---|---|---|---|")
    for p in ready:
        print(f"| [#{p['number']}]({p['url']}) | {p['title'][:70]} | {p['author']['login']} | "
              f"{(p['reviewDecision'] or 'REVIEW_REQUIRED').replace('_', ' ').lower()} | `{p['headRefOid'][:9]}` |")
    if not ready:
        print("| — | no merge-ready PRs | | | |")
    if blocked:
        print("\nNot ready: " + "; ".join(f"#{n} {why}" for n, why in blocked))
    if unknown:
        print("\nCould not check (network): " + ", ".join(f"#{n}" for n, _ in unknown))


if __name__ == "__main__":
    main()
