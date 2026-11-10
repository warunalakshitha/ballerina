#!/usr/bin/env python3
"""List new or changed Go tests that don't call t.Parallel() (team rule).

Usage: check_parallel.py [base-ref]
  base-ref defaults to origin/main (merge-base with HEAD is used).

A test counts as changed when any line of its body is in the `git diff -U0`
ranges. Each reported line is `file:line TestName` for a test whose first
statements don't include t.Parallel(), and `file:line TestName/t.Run` for a
subtest closure that doesn't call it. Exit status 1 when anything is reported.
Tests that mutate process-global state (os.Setenv, os.Chdir, os.Stdout, PATH)
must stay serial; review each hit before suggesting the fix.
"""
import re
import subprocess
import sys


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def changed_lines(base, path):
    lines = set()
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", sh("git", "diff", "-U0", f"{base}...HEAD", "--", path), re.M):
        start, count = int(m.group(1)), int(m.group(2) or 1)
        lines.update(range(start, start + count))
    return lines


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    mb = sh("git", "merge-base", "HEAD", base).strip()
    files = [f for f in sh("git", "diff", "--name-only", "--diff-filter=AM", f"{mb}...HEAD", "--", "*_test.go").split() if f]
    hits = []
    for path in files:
        changed = changed_lines(mb, path)
        src = open(path).read().splitlines()
        tests = [(i, m.group(1)) for i, line in enumerate(src, 1)
                 for m in [re.match(r"func (Test\w+)\(t \*testing\.T\)", line)] if m]
        for k, (start, name) in enumerate(tests):
            end = tests[k + 1][0] - 1 if k + 1 < len(tests) else len(src)
            if not any(start <= c <= end for c in changed):
                continue
            if not any("t.Parallel()" in src[j] for j in range(start, min(start + 3, end))):
                hits.append(f"{path}:{start} {name}")
            for j in range(start, end):
                if re.search(r"\bt\.Run\(", src[j]) and not any("t.Parallel()" in src[x] for x in range(j + 1, min(j + 4, end))):
                    hits.append(f"{path}:{j + 1} {name}/t.Run")
    for h in hits:
        print(h)
    if not hits:
        print("check_parallel: every new or changed test calls t.Parallel()")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
