#!/usr/bin/env python3
"""Post pre-pr-review findings to a GitHub PR as inline review comments.

Usage: post_review.py <findings.json> [--post] [--out <preview.md>] [--allow-moved-head] [--ignore-warnings]

Default is a dry run: nothing is written to GitHub, the exact comments that
would be posted go to <preview.md> (default: pr-comment.md next to
findings.json). --post performs the writes. Only `gh` is needed.

What gets posted:
  * each finding anchored to a changed line → one inline comment (one review);
    a line outside the diff falls back to a file-level comment, a file outside
    the diff to the summary
  * one short summary comment, edited in place on every run (a legacy
    "# Review report — #N" comment is replaced by it)
  * earlier agent comments whose finding is gone → reply + resolve thread
    (the reply names the fixing PR when the finding's id is in
    stack.fixed_later)
With a "stack" block (from scripts/stack.py --json), the summary names the stack
and lists issues fixed by a later PR in the stack, and the post is refused when
any PR in the stack has moved since the review.
Every agent comment carries a hidden marker so reruns find their own comments.
A new finding within OVERLAP_LINES of someone else's inline comment (human,
CodeRabbit, other bot) is reported as an overlap warning so a duplicate can be
dropped from findings.json before posting.
"""
import argparse
import json
import os
import re
import subprocess
import sys

PREFIX = "🤖"
FINDING_MARKER = "<!-- pre-pr-review:finding id={} -->"
SUMMARY_MARKER = "<!-- pre-pr-review:summary pr={} diff={} skill={} -->"
FINDING_ID_RE = re.compile(r"<!-- pre-pr-review:finding id=(\S+) -->")
LEGACY_SUMMARY_PREFIX = "# Review report — #"
SEVERITY_LABEL = {"important": "Important", "verify": "Verify", "nit": "Nit"}
SEVERITY_BADGE = {"important": "🔴", "verify": "🟡", "nit": "🔵"}
MAX_TITLE, MAX_BODY, MAX_SENTENCES = 80, 400, 3
MAX_SUMMARY_LINE, MAX_ITEMS, MAX_ITEM = 160, 5, 140
MAX_CHECKED, MAX_CHECK = 4, 40
OVERLAP_LINES = 3

THREADS_QUERY = """
query($owner: String!, $name: String!, $num: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $num) {
      reviewThreads(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { id isResolved comments(first: 1) { nodes { databaseId } } }
      }
    }
  }
}"""
RESOLVE_MUTATION = """
mutation($id: ID!) { resolveReviewThread(input: {threadId: $id}) { thread { isResolved } } }"""


def gh(*args, payload=None):
    cmd = ["gh", "api", *args]
    if payload is not None:
        cmd += ["--input", "-"]
    # A stalled GitHub response must not hang the run. Reads are retried; a write
    # that times out may still have landed, so stop and let the next dry run show it.
    is_write = payload is not None or any("mutation" in a for a in args)
    # Resolving a thread is idempotent, so it is retried like a read.
    retryable = not is_write or any("resolveReviewThread" in a for a in args)
    for attempt in range(3 if retryable else 1):
        try:
            r = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None,
                               capture_output=True, text=True, timeout=120 if is_write else 60)
            break
        except subprocess.TimeoutExpired:
            if not retryable or attempt == 2:
                sys.exit(f"gh {' '.join(args)[:80]} timed out{'; it may have been applied: re-run the dry run before posting again' if is_write else ''}")
    if r.returncode != 0:
        sys.exit(f"gh {' '.join(args)} failed:\n{r.stdout}{r.stderr}")
    return json.loads(r.stdout) if r.stdout.strip() else None


def paged(path):
    items, page = [], 1
    while True:
        batch = gh(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")
        items += batch
        if len(batch) < 100:
            return items
        page += 1


def commentable_lines(pr_files):
    """file → list of sets of RIGHT-side lines, one set per hunk (None: no patch)."""
    result = {}
    for f in pr_files:
        patch = f.get("patch")
        if patch is None:
            result[f["filename"]] = None
            continue
        hunks, line = [], 0
        for row in patch.splitlines():
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", row)
            if m:
                line = int(m.group(1))
                hunks.append(set())
            elif row.startswith("-"):
                continue
            elif hunks:
                hunks[-1].add(line)
                line += 1
        result[f["filename"]] = hunks
    return result


def place(finding, lines):
    """Return 'line', 'file' or 'pr' for where this finding can be posted."""
    path = finding.get("path")
    if finding.get("anchor") == "pr" or not path or path not in lines:
        return "pr"
    hunks = lines[path]
    if finding.get("anchor") == "file" or hunks is None or not finding.get("line"):
        return "file"
    first = finding.get("start_line") or finding["line"]
    if any(first in h and finding["line"] in h for h in hunks):
        return "line"
    return "file"


def fence(lang, text):
    ticks = "````" if "```" in text else "```"
    return f"{ticks}{lang}\n{text.rstrip()}\n{ticks}"


def render_finding(f, where):
    sev = f["severity"]
    head = f"{PREFIX} {SEVERITY_BADGE[sev]} **{SEVERITY_LABEL[sev]}** · {f['kind']} — **{f['title']}**"
    parts = [FINDING_MARKER.format(f["id"]), head, f["body"].strip()]
    if f.get("code"):
        parts.append(fence(f["code"].get("lang", "ballerina"), f["code"]["text"]))
    if f.get("outputs"):
        out = "\n".join(f"{k}: {v}" for k, v in f["outputs"].items())
        parts.append("<details><summary>Output</summary>\n\n" + fence("text", out) + "\n</details>")
    if f.get("suggestion") is not None:
        if where == "line":
            parts.append(fence("suggestion", f["suggestion"]) if f["suggestion"] else "```suggestion\n```")
        elif f["suggestion"]:
            parts.append("Suggested change:\n" + fence(f.get("suggestion_lang", "ballerina"), f["suggestion"]))
    return "\n\n".join(parts)


# A reply starting with this marks the finding as withdrawn (wrong), so the summary
# counts it apart from fixed ones and it is never re-posted as fixed.
WITHDRAWN_PREFIX = "🤖 Withdrawn"


def coderabbit_thread_counts(roots, threads):
    """(unresolved, total) review threads started by CodeRabbit."""
    rabbit = [c for c in roots if c["user"]["login"].startswith("coderabbitai")]
    unresolved = sum(1 for c in rabbit if not threads.get(c["id"], (None, False))[1])
    return unresolved, len(rabbit)


def render_summary(data, placed, fixed, withdrawn=0, coderabbit=(0, 0), answered=0):
    counts = {s: sum(1 for f in data["findings"] if f["severity"] == s) for s in SEVERITY_LABEL}
    count_text = " · ".join(f"{SEVERITY_BADGE[s]} **{n} {SEVERITY_LABEL[s]}{'s' if n > 1 and s == 'nit' else ''}**"
                            for s, n in counts.items() if n) or "0 findings ✅"
    tally = [f"{n} {word}" for n, word in ((fixed, "fixed"), (answered, "answered"), (withdrawn, "withdrawn")) if n]
    if tally:
        count_text += f" ({', '.join(tally)})"
    status = f"{count_text} · reviewed `{data['head_sha'][:9]}`."
    if line := data["summary"].get("line", "").strip():
        status += f" {line}"
    lines = [SUMMARY_MARKER.format(data["pr"], data["reviewed_diff"][:8], data["skill_version"][:8]),
             f"## 🤖 PR review summary · #{data['pr']}", status]
    stack = data.get("stack")
    if stack and len(stack["prs"]) > 1:
        chain = " → ".join(f"**#{n}**" if n == data["pr"] else f"#{n}" for n in stack["prs"])
        lines.append(f"Stack: {chain} · reviewed as a unit at `{stack['tip_sha'][:9]}`.")
    if checked := data["summary"].get("checked", []):
        lines.append("Checked: " + " · ".join(f"{c.rstrip(' ✔')} ✔" for c in checked))
    rabbit_unresolved, rabbit_total = coderabbit
    if rabbit_total:
        done = " ✅" if not rabbit_unresolved else ""
        lines.append(f"CodeRabbit: {rabbit_unresolved} of {rabbit_total} threads unresolved{done}.")
    items = list(data["summary"].get("items", []))
    items += [f"✅ Fixed later in the stack by #{f['pr']}: {f['text']}" for f in (stack or {}).get("fixed_later", [])]
    for f, where in placed:
        if where == "pr":
            loc = f" (`{f['path']}:{f['line']}` isn't in the diff)" if f.get("path") and f.get("line") else ""
            items.append(f"{SEVERITY_BADGE[f['severity']]} **{SEVERITY_LABEL[f['severity']]}** · {f['title']} — {f['body'].strip()}{loc}")
    if items:
        lines.append("")
        lines += [f"- {i}" for i in items]
    return "\n".join(lines) + "\n"


def brevity_warnings(data):
    warn = []
    s = data["summary"]
    if len(s.get("line", "")) > MAX_SUMMARY_LINE:
        warn.append(f"summary line is {len(s['line'])} chars (max {MAX_SUMMARY_LINE})")
    if len(s.get("items", [])) > MAX_ITEMS:
        warn.append(f"summary has {len(s['items'])} items (max {MAX_ITEMS})")
    warn += [f"summary item is {len(i)} chars (max {MAX_ITEM}): {i[:40]}…" for i in s.get("items", []) if len(i) > MAX_ITEM]
    if len(s.get("checked", [])) > MAX_CHECKED:
        warn.append(f"summary has {len(s['checked'])} checked entries (max {MAX_CHECKED})")
    warn += [f"checked entry is {len(c)} chars (max {MAX_CHECK}): {c}" for c in s.get("checked", []) if len(c) > MAX_CHECK]
    for f in data["findings"]:
        fid = f["id"]
        if len(f["title"]) > MAX_TITLE:
            warn.append(f"{fid}: title is {len(f['title'])} chars (max {MAX_TITLE})")
        body = f["body"].strip()
        sentences = len(re.findall(r"[.!?](\s|$)", re.sub(r"`[^`]*`", "x", body)))
        if len(body) > MAX_BODY or sentences > MAX_SENTENCES:
            warn.append(f"{fid}: body is {len(body)} chars / {sentences} sentences (max {MAX_BODY} / {MAX_SENTENCES})")
        if "<br>" in body or "\n|" in body:
            warn.append(f"{fid}: body has a table or <br>; put code in `code` instead")
        code = f.get("code")
        if code and code.get("lang", "ballerina") == "ballerina" and f.get("outputs") and not re.search(r"function main\b|^\s*service\b", code["text"], re.M):
            warn.append(f"{fid}: code has outputs but no `main`; make it a runnable program with @output/@error markers")
    return warn


def overlap_warnings(new_findings, others, threads):
    warn = []
    for f in new_findings:
        if not f.get("line"):
            continue
        lo, hi = (f.get("start_line") or f["line"]) - OVERLAP_LINES, f["line"] + OVERLAP_LINES
        for c in others:
            line = c.get("line") or c.get("original_line")
            if c["path"] != f["path"] or line is None or not lo <= line <= hi:
                continue
            state = "resolved" if threads.get(c["id"], (None, False))[1] else "open"
            text = " ".join(c["body"].split())[:80]
            warn.append(f"{f['id']}: overlaps {c['user']['login']}'s {state} comment at "
                        f"{c['path']}:{line} — drop if same concern: {text}…")
    return warn


def resolve_threads(owner, name, num):
    """comment databaseId → (thread id, isResolved) for the first comment of each thread."""
    threads, after = {}, None
    while True:
        args = ["graphql", "-f", f"query={THREADS_QUERY}", "-f", f"owner={owner}", "-f", f"name={name}", "-F", f"num={num}"]
        if after:
            args += ["-f", f"after={after}"]
        page = gh(*args)["data"]["repository"]["pullRequest"]["reviewThreads"]
        for t in page["nodes"]:
            if t["comments"]["nodes"]:
                threads[t["comments"]["nodes"][0]["databaseId"]] = (t["id"], t["isResolved"])
        if not page["pageInfo"]["hasNextPage"]:
            return threads
        after = page["pageInfo"]["endCursor"]


def main():
    ap = argparse.ArgumentParser(description="Post pre-pr-review findings to a GitHub PR.")
    ap.add_argument("findings")
    ap.add_argument("--post", action="store_true", help="publish (default: dry run)")
    ap.add_argument("--out", help="preview path (default: pr-comment.md next to findings)")
    ap.add_argument("--allow-moved-head", action="store_true")
    ap.add_argument("--ignore-warnings", action="store_true", help="post even with brevity warnings")
    opts = ap.parse_args()
    post, allow_moved = opts.post, opts.allow_moved_head
    data = json.load(open(opts.findings))
    out = opts.out or os.path.join(os.path.dirname(os.path.abspath(opts.findings)), "pr-comment.md")
    repo, num = data["repo"], data["pr"]
    owner, name = repo.split("/")
    base = f"repos/{repo}"

    me = gh("user")["login"]
    pr = gh(f"{base}/pulls/{num}")
    head = pr["head"]["sha"]
    if head != data["head_sha"] and not allow_moved:
        sys.exit(f"PR head is {head[:9]}, findings are for {data['head_sha'][:9]}: re-review, "
                 "or pass --allow-moved-head if the PR diff is unchanged (e.g. a merge of main)")
    stack = data.get("stack") or {}
    for n, sha in stack.get("heads", {}).items():
        now = head if int(n) == num else gh(f"{base}/pulls/{n}")["head"]["sha"]
        if now != sha and not allow_moved:
            sys.exit(f"stack PR #{n} moved to {now[:9]} since the review at {sha[:9]}: re-review the stack")
    fixed_by = {f["id"]: f["pr"] for f in stack.get("fixed_later", []) if f.get("id")}

    lines = commentable_lines(paged(f"{base}/pulls/{num}/files"))
    placed = [(f, place(f, lines)) for f in data["findings"]]
    bodies = {f["id"]: render_finding(f, where) for f, where in placed}

    review_comments = paged(f"{base}/pulls/{num}/comments")
    roots = [c for c in review_comments if not c.get("in_reply_to_id")]
    mine = [c for c in roots if c["user"]["login"] == me and FINDING_ID_RE.search(c["body"])]
    others = [c for c in roots if not FINDING_ID_RE.search(c["body"])]
    existing = {FINDING_ID_RE.search(c["body"]).group(1): c for c in mine}
    threads = resolve_threads(owner, name, num)

    plan = {"update": [], "new_line": [], "new_file": [], "resolve": []}
    moved = set()
    current = {f["id"] for f, where in placed if where != "pr"}
    for f, where in placed:
        if where == "pr":
            continue
        old = existing.get(f["id"])
        if old and (old.get("line") is not None or where == "file"):
            if old["body"] != bodies[f["id"]]:
                plan["update"].append((old, f))
        else:
            if old and not threads.get(old["id"], (None, False))[1]:
                plan["resolve"].append(old)
                moved.add(f["id"])
            plan["new_line" if where == "line" else "new_file"].append(f)
    for fid, c in existing.items():
        if fid not in current and not threads.get(c["id"], (None, False))[1]:
            plan["resolve"].append(c)

    all_ids = {f["id"] for f in data["findings"]}
    withdrawn_roots = {c["in_reply_to_id"] for c in review_comments
                       if c.get("in_reply_to_id") and c["user"]["login"] == me and c["body"].startswith(WITHDRAWN_PREFIX)}
    gone = [fid for fid in existing if fid not in all_ids]
    withdrawn_ids = {fid for fid in gone if existing[fid]["id"] in withdrawn_roots}
    # Findings the author answered (declined, deferred to an issue, or resolved without a change) aren't "fixed".
    answered_ids = set(data.get("answered", [])) & set(gone) - withdrawn_ids
    summary = render_summary(data, placed, len(gone) - len(withdrawn_ids) - len(answered_ids), len(withdrawn_ids),
                             coderabbit_thread_counts(roots, threads), len(answered_ids))
    issue_comments = paged(f"{base}/issues/{num}/comments")
    # Edit the most recently updated summary; older duplicates (e.g. from another session) are left alone.
    summaries = [c for c in issue_comments if c["user"]["login"] == me and (
        c["body"].startswith("<!-- pre-pr-review:summary") or c["body"].startswith(LEGACY_SUMMARY_PREFIX + str(num)))]
    old_summary = max(summaries, key=lambda c: c["updated_at"], default=None)

    warnings = brevity_warnings(data) + overlap_warnings(plan["new_line"] + plan["new_file"], others, threads)
    write_preview(out, data, placed, bodies, plan, summary, old_summary, warnings, head, fixed_by)
    print(f"Preview: {out}")
    for w in warnings:
        print(f"warning: {w}")
    if not post:
        print("Dry run — nothing posted. Re-run with --post to publish.")
        return
    if brevity_warnings(data) and not opts.ignore_warnings:
        sys.exit("Not posted: fix the brevity warnings above, or pass --ignore-warnings.")

    commit = data["head_sha"]
    for old, f in plan["update"]:
        gh(f"{base}/pulls/comments/{old['id']}", "-X", "PATCH", payload={"body": bodies[f["id"]]})
    for c in plan["resolve"]:
        fid = FINDING_ID_RE.search(c["body"]).group(1)
        if fid in moved:
            reply = f"↪ Still open at `{head[:9]}`; the code moved, so this is re-posted on the current lines."
        elif fid in fixed_by:
            reply = f"✅ Fixed later in the stack by #{fixed_by[fid]}; fine as long as the stack lands together."
        else:
            reply = f"✅ No longer reported at `{head[:9]}`."
        # A retry after a timed-out resolve must not reply a second time.
        already_replied = any(r.get("in_reply_to_id") == c["id"] and r["user"]["login"] == me and
                              r["body"].startswith(("✅ No longer reported", "✅ Fixed later", "↪ Still open")) for r in review_comments)
        if not already_replied:
            gh(f"{base}/pulls/{num}/comments/{c['id']}/replies", payload={"body": reply})
        thread = threads.get(c["id"])
        if thread and not thread[1]:
            gh("graphql", "-f", f"query={RESOLVE_MUTATION}", "-f", f"id={thread[0]}")
    if plan["new_line"]:
        comments = []
        for f in plan["new_line"]:
            c = {"path": f["path"], "line": f["line"], "side": "RIGHT", "body": bodies[f["id"]]}
            if f.get("start_line") and f["start_line"] != f["line"]:
                c.update(start_line=f["start_line"], start_side="RIGHT")
            comments.append(c)
        gh(f"{base}/pulls/{num}/reviews", payload={
            "commit_id": commit, "event": "COMMENT", "body": f"{PREFIX} PR review — inline findings for `{commit[:9]}`.",
            "comments": comments})
    for f in plan["new_file"]:
        gh(f"{base}/pulls/{num}/comments", payload={
            "commit_id": commit, "path": f["path"], "subject_type": "file", "body": bodies[f["id"]]})
    if old_summary and old_summary["body"] == summary:
        res = old_summary
    elif old_summary:
        res = gh(f"{base}/issues/comments/{old_summary['id']}", "-X", "PATCH", payload={"body": summary})
    else:
        res = gh(f"{base}/issues/{num}/comments", payload={"body": summary})
    print(f"Summary: {res['html_url']}")
    print(f"Posted: {len(plan['new_line'])} inline, {len(plan['new_file'])} file-level, "
          f"{len(plan['update'])} updated, {len(plan['resolve'])} resolved")


def write_preview(out, data, placed, bodies, plan, summary, old_summary, warnings, head, fixed_by):
    action = {id(f): "new" for f in plan["new_line"] + plan["new_file"]}
    action.update({id(f): "update" for _, f in plan["update"]})
    parts = [f"<!-- Dry-run preview for PR #{data['pr']} at {head[:9]}. Not posted. -->", ""]
    if warnings:
        parts += ["## Warnings", *[f"- {w}" for w in warnings], ""]
    state = "new" if not old_summary else "unchanged" if old_summary["body"] == summary else f"update {old_summary['id']}"
    parts += [f"## Summary comment ({state})", "", summary]
    for f, where in placed:
        if where == "pr":
            continue
        loc = f"{f['path']}:{f.get('start_line') or f['line']}-{f['line']}" if where == "line" else f"{f['path']} (file)"
        parts += [f"## {where} comment · {loc} · {action.get(id(f), 'unchanged')}", "", bodies[f["id"]], ""]
    if plan["resolve"]:
        parts += ["## Resolve"]
        for c in plan["resolve"]:
            fid = FINDING_ID_RE.search(c["body"]).group(1)
            why = f"fixed later in the stack by #{fixed_by[fid]}" if fid in fixed_by else "no longer reported"
            parts.append(f"- comment {c['id']} ({fid}): reply \"{why}\" and resolve")
        parts.append("")
    with open(out, "w") as fh:
        fh.write("\n".join(parts))


if __name__ == "__main__":
    main()
