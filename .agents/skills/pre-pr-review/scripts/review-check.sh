#!/usr/bin/env bash
# Verifies the required artifacts (INTENT.md, review-report.md) are present and
# match the diff being pushed. Does not care which agent produced them — the
# process specifies the artifacts, not the tool.
# Usage: scripts/review-check.sh [base-ref]   (default origin/main)
# Exit 0 = ok, non-zero = reject. No AI involved.
set -euo pipefail

# portable sha256 (Linux: sha256sum, macOS: shasum)
sha256() { if command -v sha256sum >/dev/null; then sha256sum | cut -c1-64; else shasum -a 256 | cut -c1-64; fi; }

base=${1:-origin/main}
skill_files=".agents/skills/pre-pr-review/SKILL.md"
[[ -f .agents/skills/nutcraker-review-guidelines/SKILL.md ]] && skill_files="$skill_files .agents/skills/nutcraker-review-guidelines/SKILL.md"

changed=$(git diff --name-only "$base"...HEAD)

# 1. Report must be part of this change
report=$(grep -E '^docs/changes/[^/]+/[^/]+/review-report\.md$' <<<"$changed" | head -1 || true)
if [[ -z "$report" ]]; then
  echo "review-check: no docs/changes/<release_number>/<issue_number>/review-report.md in this change. Run the pre-pr-review skill and commit its report." >&2
  exit 1
fi
issue_dir=$(dirname "$report")

field() { grep -E "^$1:" "$report" | head -1 | sed -E "s/^$1:[[:space:]]*//; s/^sha256://; s/[[:space:]].*//"; }

# 2. Diff hash must match
actual=$(git diff "$base"...HEAD -- . ':!docs/changes/' | sha256)
recorded=$(field reviewed_diff)
if [[ "$actual" != "$recorded" ]]; then
  echo "review-check: code changed after review (hash mismatch). Re-run the pre-pr-review skill." >&2
  exit 1
fi

# 3. Guideline version must be current
current=$(cat $skill_files 2>/dev/null | sha256)
used=$(field skill_version)
if [[ "$current" != "$used" ]]; then
  echo "review-check: review used an outdated guideline. Re-run the pre-pr-review skill." >&2
  exit 1
fi

# 4. No unresolved Important findings
if [[ "$(field important)" != "0" ]]; then
  echo "review-check: review-report.md has unresolved Important findings." >&2
  exit 1
fi

# 4b. Patch coverage is reported, not gated (target 80%; reviewer decides)
cov=$(field patch_coverage)
if [[ -z "$cov" ]]; then
  echo "review-check: patch_coverage missing from $report." >&2; exit 1
fi
(( cov < 80 )) && echo "review-check: note — patch coverage ${cov}% is below the 80% target; reviewer to decide." >&2

# 5. Every changed .go/.bal/.py file appears in INTENT.md's change map (non-code files exempt)
intent="$issue_dir/INTENT.md"
if [[ ! -f "$intent" ]]; then
  echo "review-check: $intent missing." >&2
  exit 1
fi
missing=0
while read -r f; do
  [[ "$f" == docs/changes/* ]] && continue
  [[ "$f" =~ \.(go|bal|py)$ ]] || continue
  grep -qF "$f" "$intent" || { echo "review-check: $f not in change map of $intent" >&2; missing=1; }
done <<<"$changed"
[[ $missing -eq 0 ]] || exit 1

echo "review-check: ok ($report)"
