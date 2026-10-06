#!/usr/bin/env python3
"""Find corpus tests a PR adds that duplicate existing ones.

Usage: .agents/skills/pr-review/scripts/check_duplicate_tests.py [base-ref] [--threshold 0.85]
  base-ref defaults to origin/main (merge-base with HEAD is used).

Compares every `.bal` the PR adds under corpus/bal, corpus/lib and
corpus/project with every other `.bal` in those trees at HEAD (language and
standard-library tests are checked against both). Each program is normalized
before comparing: the license header, comments (including @output/@error
markers), string-literal contents and whitespace are dropped, so two tests
that differ only in comments or printed text still match.

  EXACT  same normalized program
  NEAR   token 5-gram overlap >= threshold (Jaccard), or the new test is
         >= 0.95 contained in an existing one

Programs shorter than MIN_TOKENS tokens are only checked for EXACT, since tiny
`-e` tests share most of their tokens by construction. Exit status 1 when
anything is reported. Review each hit before posting: a NEAR pair with a
different marker kind (-v vs -e) or a different expected output can be
intentional.
"""
import argparse
import difflib
import hashlib
import os
import re
import subprocess
import sys
from collections import defaultdict

ROOTS = ("corpus/bal/", "corpus/lib/", "corpus/project/")
TOKEN_RE = re.compile(r'"(?:\\.|[^"\\])*"|`[^`]*`|[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|\S')
SHINGLE = 5
MIN_TOKENS = 30
CONTAINMENT = 0.95


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def tokens(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    out = []
    for tok in TOKEN_RE.findall(text):
        if tok.startswith('"'):
            tok = '"S"'
        elif tok.startswith("`"):
            tok = "`T`"
        out.append(tok)
    return out


def shingles(toks):
    return {hash(tuple(toks[i:i + SHINGLE])) for i in range(len(toks) - SHINGLE + 1)}


def token_diff(a, b, limit=6):
    """Short summary of what separates two token lists, for triaging a NEAR hit."""
    parts = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        new_side, old_side = " ".join(a[i1:i2])[:40], " ".join(b[j1:j2])[:40]
        if op == "delete":
            parts.append(f"new has [{new_side}]")
        elif op == "insert":
            parts.append(f"existing has [{old_side}]")
        else:
            parts.append(f"[{old_side}] -> [{new_side}]")
        if len(parts) == limit:
            parts.append("...")
            break
    return "; ".join(parts) or "(only comments/strings/whitespace)"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("base", nargs="?", default="origin/main")
    ap.add_argument("--threshold", type=float, default=0.85)
    opts = ap.parse_args()

    mb = sh("git", "merge-base", "HEAD", opts.base).strip()
    added = [f for f in sh("git", "diff", "--name-only", "--diff-filter=A", f"{mb}...HEAD").split()
             if f.endswith(".bal") and f.startswith(ROOTS)]
    if not added:
        print("check_duplicate_tests: the PR adds no corpus .bal files")
        return 0
    corpus = [f for f in sh("git", "ls-files", *ROOTS).split() if f.endswith(".bal")]

    toks, digest, shing = {}, {}, {}
    for f in corpus:
        try:
            t = tokens(open(f, encoding="utf-8").read())
        except OSError:
            continue
        toks[f] = t
        digest[f] = hashlib.sha1(" ".join(t).encode()).hexdigest()
        if len(t) >= MIN_TOKENS:
            shing[f] = shingles(t)

    by_digest = defaultdict(list)
    for f, d in digest.items():
        by_digest[d].append(f)
    index = defaultdict(set)
    for f, s in shing.items():
        for h in s:
            index[h].add(f)

    hits = []
    added_set = set(added)
    for f in added:
        if f not in digest:
            continue
        for other in by_digest[digest[f]]:
            if other != f and (other not in added_set or other > f):
                hits.append((f, other, "EXACT", 1.0))
        s = shing.get(f)
        if not s:
            continue
        overlap = defaultdict(int)
        for h in s:
            for other in index[h]:
                if other != f:
                    overlap[other] += 1
        for other, common in overlap.items():
            if digest[other] == digest[f] or (other in added_set and other < f):
                continue
            jaccard = common / (len(s) + len(shing[other]) - common)
            contained = common / len(s)
            if jaccard >= opts.threshold or contained >= CONTAINMENT:
                hits.append((f, other, "NEAR", max(jaccard, contained)))

    for f, other, kind, score in sorted(hits, key=lambda h: (h[0], -h[3])):
        print(f"{kind:5} {score:.2f}  {f}  ~  {other}")
        if kind == "NEAR":
            print(f"             differs: {token_diff(toks[f], toks[other])}")
    if not hits:
        print(f"check_duplicate_tests: {len(added)} new test(s), no duplicates in {len(corpus)} corpus files")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
