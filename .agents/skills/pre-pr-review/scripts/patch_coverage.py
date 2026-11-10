#!/usr/bin/env python3
"""Patch coverage for changed Go lines, computed locally (no Codecov).

Usage: patch_coverage.py [base-ref] [--no-corpus]
  base-ref defaults to origin/main (merge-base with HEAD is used).

Runs `go test -covermode=atomic -coverpkg=<changed pkgs> <changed pkgs> ./corpus/...`
and intersects the profile with the added/modified lines from `git diff -U0`.
Prints a markdown table plus total, ready to paste into review-report.md.
"""
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict

TARGET = 80  # percent of changed statement lines; advisory, reviewer decides


def sh(*cmd, check=True):
    return subprocess.run(cmd, capture_output=True, text=True, check=check).stdout


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_corpus = "--no-corpus" in sys.argv
    base = args[0] if args else "origin/main"
    mb = sh("git", "merge-base", "HEAD", base).strip()
    # A coverage profile's paths are prefixed with each package's own module path.
    # In a go.work workspace, changed files can belong to different modules (e.g.
    # the repo root module and a tool module like compiler-tools/benchmark), so a
    # single "mod" prefix isn't enough — build a path→dir map for every module and
    # relativize each profile line against the longest-matching one.
    repo_root = sh("git", "rev-parse", "--show-toplevel").strip()
    modules = []  # (module path, dir relative to repo root), longest path first
    for entry in sh("go", "list", "-m", "-f", "{{.Path}}|{{.Dir}}", "all").splitlines():
        if "|" not in entry:
            continue
        mpath, mdir = entry.split("|", 1)
        if not mdir:
            continue
        rel = os.path.relpath(mdir, repo_root).replace(os.sep, "/")
        modules.append((mpath, "" if rel == "." else rel))
    modules.sort(key=lambda m: len(m[0]), reverse=True)

    def relativize(path):
        for mpath, mreldir in modules:
            if path == mpath:
                return mreldir or path
            if path.startswith(mpath + "/"):
                suffix = path[len(mpath) + 1:]
                return f"{mreldir}/{suffix}" if mreldir else suffix
        return path

    # 1. changed Go source files (non-test), incl. staged/unstaged
    diff_files = set()
    for rng in ([f"{mb}...HEAD"], [], ["--cached"]):
        out = sh("git", "diff", "--name-only", *rng, "--", "*.go")
        diff_files.update(l for l in out.split() if not l.endswith("_test.go"))
    if not diff_files:
        print("No Go source files changed.")
        return

    # 2. changed line numbers per file from unified diff with 0 context
    changed = defaultdict(set)
    for rng in ([f"{mb}...HEAD"], [], ["--cached"]):
        out = sh("git", "diff", "-U0", *rng, "--", "*.go")
        cur = None
        for line in out.splitlines():
            if line.startswith("+++ b/"):
                cur = line[6:]
            elif line.startswith("@@") and cur and not cur.endswith("_test.go"):
                m = re.search(r"\+(\d+)(?:,(\d+))?", line)
                start, count = int(m.group(1)), int(m.group(2) or 1)
                changed[cur].update(range(start, start + count))

    # 3. run coverage over changed packages (+ corpus, which drives the pipeline)
    pkgs = sorted({"./" + f.rsplit("/", 1)[0] if "/" in f else "." for f in diff_files})
    coverpkg = ",".join(p + "/..." for p in pkgs)
    targets = [p + "/..." for p in pkgs] + ([] if no_corpus else ["./corpus/..."])
    prof = tempfile.NamedTemporaryFile(suffix=".out", delete=False).name
    cmd = ["go", "test", "-count=1", "-covermode=atomic", f"-coverpkg={coverpkg}",
           f"-coverprofile={prof}", *targets]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("go test failed:\n" + r.stdout[-3000:] + r.stderr[-3000:])
        sys.exit(1)

    # 4. per-line coverage from profile: file:start.col,end.col stmts count
    covered = defaultdict(lambda: defaultdict(int))  # file -> line -> max count
    with open(prof) as fh:
        next(fh)  # mode line
        for row in fh:
            loc, _stmts, cnt = row.split()
            path, span = loc.split(":")
            rel = relativize(path)
            (s, _), (e, _) = [tuple(map(int, p.split("."))) for p in span.split(",")]
            for ln in range(s, e + 1):
                covered[rel][ln] = max(covered[rel][ln], int(cnt))

    # 5. intersect and print
    def ranges(ns):
        ns = sorted(ns); out = []; i = 0
        while i < len(ns):
            j = i
            while j + 1 < len(ns) and ns[j + 1] == ns[j] + 1:
                j += 1
            out.append(str(ns[i]) if i == j else f"{ns[i]}-{ns[j]}")
            i = j + 1
        return ", ".join(out) or "—"

    tot_stmt = tot_cov = 0
    print("| File | Changed lines | Covered | Uncovered lines | Disposition |")
    print("|---|---|---|---|---|")
    for f in sorted(changed):
        if f not in diff_files:
            continue
        lines = {ln for ln in changed[f] if ln in covered[f]}  # only statement lines
        if not lines:
            print(f"| {f} | {len(changed[f])} | n/a (no statements) | — | |")
            continue
        unc = {ln for ln in lines if covered[f][ln] == 0}
        pct = 100 * (len(lines) - len(unc)) / len(lines)
        tot_stmt += len(lines); tot_cov += len(lines) - len(unc)
        print(f"| {f} | {len(lines)} | {pct:.0f}% | {ranges(unc)} | |")
    if tot_stmt:
        pct = 100 * tot_cov / tot_stmt
        status = "meets target" if pct >= TARGET else f"below {TARGET}% target — reviewer to decide"
        print(f"\nTotal: {pct:.0f}% of {tot_stmt} changed statement lines — {status}. "
              f"Command: {' '.join(cmd)}")
        print(f"patch_coverage: {pct:.0f}")
        sys.exit(0)


if __name__ == "__main__":
    main()
