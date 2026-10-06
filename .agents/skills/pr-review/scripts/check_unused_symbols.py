#!/usr/bin/env python3
"""List Go symbols a PR adds that nothing outside tests uses.

Usage: .agents/skills/pr-review/scripts/check_unused_symbols.py [base-ref]
  base-ref defaults to origin/main (merge-base with HEAD is used).

Collects the top-level funcs, methods, types, consts, vars and struct fields
declared on lines the PR adds in non-test `.go` files, then counts references
at HEAD outside the declaration line. Unexported names are searched in their
own package directory, exported names in the whole repo. Fields and methods
count only selector uses (`.name`) and keyed literals (`name:`).

  UNUSED     no reference anywhere
  TEST-ONLY  referenced only from `_test.go` files
  GENERATED  one summary line per generated file (`_generated.go` or a
             `Code generated ... DO NOT EDIT.` header)

Comment-only lines don't count as references. Methods named like standard
interface methods (String, MarshalJSON, Read, ...) are skipped.

Linters miss both: `unused` counts test callers as uses and never reports
exported fields. Matching is by name, so a common name (`Kind`, `result`) can
hide a real hit behind an unrelated use; read each hit before posting. Exit
status 1 when anything is reported.
"""
import os
import re
import subprocess
import sys
from collections import defaultdict

FUNC_RE = re.compile(r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*[\[(]")
METHOD_RE = re.compile(r"^func\s+\(")
TYPE_RE = re.compile(r"^type\s+([A-Za-z_]\w*)\b")
SINGLE_RE = re.compile(r"^(?:const|var)\s+([A-Za-z_]\w*)\b")
BLOCK_RE = re.compile(r"^(const|var|type)\s*\($")
STRUCT_RE = re.compile(r"\bstruct\s*\{\s*$")
FIELD_RE = re.compile(r"^\s+([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s+[^\s=:(]")
BLOCK_ITEM_RE = re.compile(r"^\s+([A-Za-z_]\w*)\b")
SKIP_NAMES = {"main", "init", "_"}
# Methods that satisfy standard interfaces are called through the interface.
INTERFACE_METHODS = {
    "String", "Error", "Unwrap", "Is", "As", "MarshalJSON", "UnmarshalJSON", "MarshalText", "UnmarshalText",
    "Read", "Write", "Close", "Seek", "ReadAt", "WriteTo", "ReadFrom",
    "Open", "ReadDir", "ReadFile", "Stat", "Name", "Size", "Mode", "ModTime", "IsDir", "Sys", "Type", "Info",
    "Len", "Less", "Swap", "ServeHTTP",
}
GENERATED_RE = re.compile(r"^// Code generated .* DO NOT EDIT\.$", re.M)


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def added_lines(base):
    """Map of non-test .go file -> set of line numbers the PR adds."""
    out = defaultdict(set)
    current = None
    for line in sh("git", "diff", "-U0", f"{base}...HEAD", "--", "*.go").splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
            current = path if path and not path.endswith("_test.go") else None
        elif current and line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            start, count = int(m.group(1)), int(m.group(2) or 1)
            out[current].update(range(start, start + count))
    return out


def declarations(path, lines):
    """Yield (name, kind, line) for declarations on the given lines of path."""
    with open(path, encoding="utf-8") as f:
        text = f.read().splitlines()
    block = None
    struct_depth = 0
    for no, raw in enumerate(text, 1):
        line = raw.split("//", 1)[0].rstrip()
        if struct_depth:
            if line.strip().startswith("}"):
                struct_depth -= 1
            elif no in lines and (m := FIELD_RE.match(line)):
                for name in m.group(1).split(","):
                    yield name.strip(), "field", no
            if STRUCT_RE.search(line):
                struct_depth += 1
            continue
        if block:
            if line.startswith(")"):
                block = None
            elif no in lines and (m := BLOCK_ITEM_RE.match(line)) and line.startswith("\t") and not line.startswith("\t\t"):
                yield m.group(1), block, no
            if STRUCT_RE.search(line):
                struct_depth += 1
            continue
        if m := BLOCK_RE.match(line):
            block = m.group(1)
            continue
        if no in lines:
            if m := FUNC_RE.match(line):
                yield m.group(1), "method" if METHOD_RE.match(line) else "func", no
            elif m := TYPE_RE.match(line):
                yield m.group(1), "type", no
            elif m := SINGLE_RE.match(line):
                yield m.group(1), "var", no
        if line.startswith("type ") and STRUCT_RE.search(line):
            struct_depth = 1


def references(name, kind, path):
    scope = "." if name[0].isupper() else os.path.dirname(path) or "."
    # POSIX ERE has no \b, and git grep -P needs a PCRE build.
    if kind in ("field", "method"):
        pattern = rf"\.{name}([^A-Za-z0-9_]|$)|(^|[^A-Za-z0-9_.]){name}:"
    else:
        pattern = rf"(^|[^A-Za-z0-9_]){name}([^A-Za-z0-9_]|$)"
    try:
        hits = sh("git", "grep", "-n", "-E", pattern, "--", f"{scope}/*.go" if scope != "." else "*.go")
    except subprocess.CalledProcessError:
        return []
    return [h for h in hits.splitlines() if not h.split(":", 2)[2].lstrip().startswith("//")]


def is_generated(path):
    with open(path, encoding="utf-8") as f:
        return path.endswith("_generated.go") or bool(GENERATED_RE.search(f.read(4096)))


def main():
    base_ref = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    base = sh("git", "merge-base", base_ref, "HEAD").strip()
    reported = 0
    for path, lines in sorted(added_lines(base).items()):
        if not os.path.exists(path):
            continue
        generated = is_generated(path)
        generated_hits = 0
        for name, kind, no in declarations(path, lines):
            if name in SKIP_NAMES or (kind == "method" and name in INTERFACE_METHODS):
                continue
            refs = [r for r in references(name, kind, path) if not r.startswith(f"{path}:{no}:")]
            if not refs:
                label = "UNUSED"
            elif all(r.split(":", 1)[0].endswith("_test.go") for r in refs):
                label = "TEST-ONLY"
            else:
                continue
            reported += 1
            if generated:
                generated_hits += 1
            else:
                print(f"{label:9}  {path}:{no}  {kind} {name}")
        if generated_hits:
            print(f"GENERATED  {path}  {generated_hits} unused or test-only symbols; check the generator's filter")
    return 1 if reported else 0


if __name__ == "__main__":
    sys.exit(main())
