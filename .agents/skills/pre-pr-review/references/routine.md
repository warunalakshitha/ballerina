# Scheduled review round (cloud routine)

You are the coordinator of one review round for ballerina-nutcracker/ballerina. You run unattended in a fresh cloud checkout of `warunalakshitha/ballerina` branch `chore/review-routine`. Nothing from earlier runs survives except what is on GitHub and on this branch.

## 0. Setup
1. `REPO=$(git rev-parse --show-toplevel)`; `SP=/tmp/review-sp`; `mkdir -p $SP/review-out`. Agents get `$SP` and `$REPO` in their prompts.
2. `git remote add upstream https://github.com/ballerina-nutcracker/ballerina.git` (ignore "already exists"); `git fetch upstream main`.
3. Keep the branch current: `git merge --no-edit upstream/main`.
   - Clean merge: `git push origin HEAD:chore/review-routine`. This is the only push you may make.
   - Conflict: `git merge --abort`. If the conflict touches `.agents/skills/pr-review/**` or `.agents/skills/pre-pr-review/**`, stop the round and report it (the skill may be stale). Otherwise continue on the unmerged branch and say so in the report.
4. Check tooling and record what is missing in the report (never install system packages beyond these):
   - `gh auth status` must succeed with permission to comment on ballerina-nutcracker/ballerina. If it can't post, run the round as report-only and say so first in the report.
   - Go: the version in `$REPO/go.work`/`go.mod`. If `go version` is older, `go install golang.org/dl/go<ver>@latest && go<ver> download` and put it first on PATH.
   - jBallerina `bal` (2201.13.x) is optional. If it is missing and can't be installed quickly, agents skip parity runs and say "jBallerina not available" instead of claiming parity.

## 1. Scan
`python3 $REPO/.agents/skills/pre-pr-review/scripts/scan_prs.py` lists PRs that need a review: `NEW` (no summary of ours yet) or `MOVED` (head differs from the commit our last summary reviewed). It already skips drafts, approved PRs and don't-merge/dnm/hold/wip labels. `ERR` means GitHub couldn't be read: retry once, then list it as "not checked".

A PR whose head equals the commit in our latest summary is already reviewed: skip it.

## 2. Review
- Drop PRs that conflict with `upstream/main` (`git merge-tree --write-tree upstream/main <head>`): no review, no comment, list them as skipped.
- Stacks (base branch isn't `main`): `stack.py <tip> --json`; review the stack as one unit at the highest non-conflicting PR.
- Classify MOVED PRs with an interdiff of the PR's own changes (old reviewed head vs new head, each against its merge-base). Only merges of main, no PR-file change: refresh the summary instead of re-reviewing (rewrite `head_sha`/`reviewed_diff` in a findings.json rebuilt from GitHub and post).
- Spawn one review subagent per PR (stack = one agent), at most 3 at a time, from a queue, smallest PRs first. Each prompt says: follow `$REPO/.agents/skills/pre-pr-review/references/agent-instructions.md` exactly, gives `$SP`, `$REPO`, the PR number, the last reviewed sha (MOVED) and the PR-specific focus. Rules go in agent-instructions.md, never only in a prompt.
- There are no local findings files: agents rebuild every still-open finding of ours from GitHub before re-reviewing.

## 3. Post
For each finished review: dry-run `python3 $REPO/.agents/skills/pre-pr-review/scripts/post_review.py $SP/review-out/<N>/findings.json`, fix brevity warnings (shorten text; make repros complete programs), check overlap warnings against the other reviewer's comment (drop only true duplicates), then `--post`. If the head moved since the review, don't post; re-queue it.

## 4. Bugs found on main
Follow `retrospective.md` "Bugs found on main": one repro on current main, duplicate search with `gh issue list --state all --search`, then file with labels `triage` and `Type/Bug` (or `Type/Docs` / `Type/Improvement`). No bug-hunting beyond what reviews found.

## 5. Report
Run `python3 $REPO/.agents/skills/pre-pr-review/scripts/ready_table.py`. Write the report to the Claude Doc titled **Nutcracker merge-ready PRs** (replace its content each run; create it if missing), and also print it as your final message:
1. Run time (Asia/Colombo), upstream main sha, branch merge result, tooling gaps.
2. The merge-ready table from `ready_table.py` and its "Not ready" line.
3. What this round reviewed and posted: PR, verdict, new Important/Verify findings (one line each), summary link.
4. Skipped PRs (conflicting, not checked) and filed issues.
5. Review-skill updates proposed by agents (from PRs that change AGENTS.md, skills, lint config, hooks or CI validators). Don't apply them in the cloud; list them for the user.

## Limits
- If a usage limit stops you, stop cleanly: post nothing half-finished and say in the report which PRs weren't reached. Never enable or rely on paid overage.
- Never commit or push anything except the upstream merge in step 0. Never approve, merge, label or close PRs. Never push to ballerina-nutcracker/ballerina.
- Only kill processes you started; services and listeners need process groups (agent-instructions.md).
