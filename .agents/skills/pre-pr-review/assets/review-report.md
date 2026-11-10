---
issue: <issue_number>
reviewed_diff: sha256:<64 hex — git diff origin/main...HEAD -- . ':!docs/changes/' | sha256sum>
skill_version: sha256:<64 hex — cat pre-pr-review/SKILL.md nutcraker-review-guidelines/SKILL.md (if present) | sha256sum>
agent: <e.g. claude-code / claude-opus-5 | cursor / gpt-x>
date: <ISO 8601 UTC>
patch_coverage: <int — percent of changed statement lines covered; target 80, reviewer decides below that>
important: <count>
verify: <count — suspected, not confirmed; not counted in verdict>
verdict: <"0 Important findings — ready for human review" | "N Important findings — fix first" | "0 Important, N to verify — run parity first" | "Needs design discussion — <reason>">
---

# Review report — #<issue_number> <short title>

## Verdict
<verdict line, plus the one main reason>

## Must fix (Important)
| # | Pass | File:line | Issue | Fix |
|---|---|---|---|---|
| 1 | Correctness (spec) | lib/langlibs/go/lang.xml/xml.go `strip()` | Drops whitespace text before regrouping; jBallerina groups first | Filter comments/PIs, normalize, then drop whitespace-only chunks. Test: `io:println("[", (xml \` <!--c-->a\`).strip(), "]"); // @output [ a]` |

Empty → `None`.

## Nits (suggested, not applied)
Already-open external PR (no push access) only — mechanical nits the author can apply themselves. Not findings: never counted toward `important:`, never gate the push.
- `semantics/internal/analysis/lock_analyzer.go:449` — `NoInitializer`'s doc comment restates the field name; its siblings (`Final`, `Configurable`, `Isolated`) are equally self-explanatory and have none — drop it for consistency.

Empty (nothing to suggest, or this is your own branch and you fixed them instead) → `None`.

## Already raised (not re-posted)
Already-open PR only — concerns someone else (human, CodeRabbit, other bot/agent) already raised that are still open at the reviewed head. Not posted again; Important ones still count toward `important:`.
| # | Raised by | Where | Concern | Status at head |
|---|---|---|---|---|
| 1 | heshanpadmasiri (review body) | `semtypes/env.go:113` | `-race` fails in `TestSemanticAnalysis` on the new `multiple-from-v.bal` | still open — reproduced |

Empty → `None`.

## Verify (not counted — run these)
| # | File:line | Suspected | Program to run on `bal` and Nutcracker |
|---|---|---|---|
| 1 | xml.go `getAttributes()` | returns copy; jBallerina may return live map | `xml:Element e = xml \`<a/>\`; e.getAttributes()["k"] = "v"; io:println(e);` |

Empty → `None`.

## Flagged for the reviewer (not counted)
| Kind | Detail |
|---|---|
| Skipped test | `subset10/.../empty-iterator-static-type-v.bal` — #853 |
| Changed fixture | `corpus/bir/subset8/08-xml/namespace5-v.txt` — attribute keys are expanded names (INTENT.md §Approach) |
| Coverage below target | 74% of 212 changed lines; uncovered `values/convert.go:214-220, 301` → Deferred #1490 |
| New dependency | none |
| Benchmark | `corpus/bench/08-bench/map-v.bal` +1.4σ (run-to-run σ 0.9%) |

Empty → `None`.

## Fixed during review
Own branch (push access) only — mechanical nits actually applied.
- `xml.go:concat`, `xml.go:setChildren` — added `default: panic` on compiler-guaranteed switches
- `model/opaque.go:181` — `make([]Symbol, OpaqueFnXMLFilter+1)` instead of magic `10`
- `corpus/bal/.../lang-xml-api-v.bal` — added equality test for prefix-independent `==`

Empty (nothing mechanical to fix, or reviewing an external PR) → omit this section.

## Evidence
| Pass | Result |
|---|---|
| Branch / scope | `head` vs merge-base `abc1234`; N commits, N files (+X / −Y) |
| INTENT.md | present / agent-drafted (developer must rewrite) |
| Commits | Conventional ✔ · no Co-authored-by ✔ · no AI author ✔ |
| Lint, fmt, license headers | clean (N fixed) |
| Dead code | none / N removed |
| `go test` + corpus | pass, delta vs main 0 |
| `go test -race` | pass / N races (introduced · exposed by new test) |
| Prior review | N prior concerns, M fixed at head, K still open (listed above) |
| Impossible-condition scan | N guards checked |
| Sibling consistency · Reuse · Scope | clean |
| Mutation check | new tests fail when fix reverted ✔ |
| Patch coverage | 84% of 212 changed lines (target 80) — per-file table below |
| jBallerina parity | 5/5 programs match |
| Verification pass | N findings checked, M dropped |
| Commands | `go test ./values/... ./corpus/...`, `golangci-lint run ./values/...`, `patch_coverage.py`, `bal run ...` |

| File | Changed lines | Covered | Uncovered |
|---|---|---|---|
| values/convert.go | 96 | 91% | 214-220, 301 |
