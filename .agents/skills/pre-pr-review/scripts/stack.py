#!/usr/bin/env python3
"""Find the PR stack a pull request belongs to and attribute lines to its PRs.

Usage:
  stack.py <pr>                          print the stack, bottom to top
  stack.py <pr> --json                   the same as JSON (paste into findings.json "stack")
  stack.py <pr> attribute <path:line>... name the stack PR whose own commits last touched each line at the tip
  options: --repo owner/name (default: ballerina-nutcracker/ballerina), --tip <pr> when the stack branches

Run inside a clone of the repo. The stack is followed down through base branches
until the default branch, and up through open PRs whose base is the current head
branch. Each PR's head is fetched to refs/pr-stack/<n>. A PR's own range is
<head of the PR below>..<its head>; the bottom PR's range starts at its merge-base
with the default branch. A warning is printed when a PR is not based on the
current head of the PR below it (the stack needs a rebase).
"""
import argparse
import json
import re
import subprocess
import sys


def run(*cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"{' '.join(cmd)} failed:\n{r.stdout}{r.stderr}")
    return r


def git(*args, check=True):
    return run("git", *args, check=check).stdout.strip()


def remote_for(repo):
    for row in git("remote", "-v").splitlines():
        name, url = row.split()[:2]
        if re.search(rf"[:/]{re.escape(repo)}(\.git)?$", url):
            return name
    sys.exit(f"no git remote points at {repo}")


def open_prs(repo):
    out = run("gh", "pr", "list", "-R", repo, "--state", "open", "--limit", "300", "--json",
              "number,title,headRefName,baseRefName,headRefOid,baseRefOid,isDraft").stdout
    return json.loads(out)


def build_stack(prs, number, default_branch, tip):
    by_num = {p["number"]: p for p in prs}
    if number not in by_num:
        sys.exit(f"#{number} is not an open PR")
    by_head = {p["headRefName"]: p for p in prs}
    down, cur, notes = [], by_num[number], []
    while True:
        down.append(cur)
        if cur["baseRefName"] == default_branch:
            break
        below = by_head.get(cur["baseRefName"])
        if below is None:
            notes.append(f"#{cur['number']} is based on `{cur['baseRefName']}`, which has no open PR")
            break
        cur = below
    stack = list(reversed(down))
    cur = by_num[number]
    while True:
        children = [p for p in prs if p["baseRefName"] == cur["headRefName"]]
        if not children:
            break
        if len(children) > 1:
            pick = [c for c in children if tip and c["number"] == tip]
            if not pick:
                notes.append(f"the stack branches above #{cur['number']}: "
                             + ", ".join(f"#{c['number']}" for c in children) + " (choose one with --tip)")
                break
            children = pick
        cur = children[0]
        stack.append(cur)
    return stack, notes


def ranges(stack, remote, default_branch):
    git("fetch", "-q", remote, default_branch,
        *[f"+pull/{p['number']}/head:refs/pr-stack/{p['number']}" for p in stack], check=False)
    result, notes = [], []
    for i, p in enumerate(stack):
        head = p["headRefOid"]
        if i == 0:
            start = git("merge-base", f"{remote}/{default_branch}", head)
        else:
            start = stack[i - 1]["headRefOid"]
            if run("git", "merge-base", "--is-ancestor", start, head, check=False).returncode != 0:
                notes.append(f"#{p['number']} is not based on the current head of #{stack[i - 1]['number']}: rebase the stack")
                start = git("merge-base", start, head)
        commits = int(git("rev-list", "--count", f"{start}..{head}"))
        result.append({"pr": p["number"], "title": p["title"], "base": start, "head": head, "commits": commits})
    return result, notes


def owner_of(commit, rngs):
    for r in rngs:
        in_head = run("git", "merge-base", "--is-ancestor", commit, r["head"], check=False).returncode == 0
        in_base = run("git", "merge-base", "--is-ancestor", commit, r["base"], check=False).returncode == 0
        if in_head and not in_base:
            return r["pr"]
    return None


def attribute(targets, rngs):
    tip = rngs[-1]["head"]
    for target in targets:
        path, _, line = target.rpartition(":")
        blame = run("git", "blame", "--porcelain", "-L", f"{line},{line}", tip, "--", path, check=False)
        if blame.returncode != 0:
            print(f"{target}\t?\t{blame.stderr.strip()}")
            continue
        commit = blame.stdout.split()[0]
        owner = owner_of(commit, rngs)
        print(f"{target}\t{'#' + str(owner) if owner else 'pre-existing'}\t{commit[:9]}")


def main():
    ap = argparse.ArgumentParser(description="Find a PR's stack and attribute lines to its PRs.")
    ap.add_argument("pr", type=int)
    ap.add_argument("cmd", nargs="?", choices=["attribute"])
    ap.add_argument("targets", nargs="*")
    ap.add_argument("--repo", default="ballerina-nutcracker/ballerina")
    ap.add_argument("--default-branch", default="main")
    ap.add_argument("--tip", type=int)
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args()

    remote = remote_for(opts.repo)
    stack, notes = build_stack(open_prs(opts.repo), opts.pr, opts.default_branch, opts.tip)
    rngs, range_notes = ranges(stack, remote, opts.default_branch)
    notes += range_notes

    if opts.cmd == "attribute":
        attribute(opts.targets, rngs)
    elif opts.json:
        print(json.dumps({"prs": [r["pr"] for r in rngs], "heads": {str(r["pr"]): r["head"] for r in rngs},
                          "tip_sha": rngs[-1]["head"], "fixed_later": []}, indent=2))
    else:
        for r in rngs:
            mark = "→" if r["pr"] == opts.pr else " "
            print(f"{mark} #{r['pr']}\t{r['base'][:9]}..{r['head'][:9]}\t{r['commits']} commit(s)\t{r['title']}")
        print(f"tip: {rngs[-1]['head']}  (review the whole stack at refs/pr-stack/{rngs[-1]['pr']})")
    for n in notes:
        print(f"note: {n}", file=sys.stderr)


if __name__ == "__main__":
    main()
