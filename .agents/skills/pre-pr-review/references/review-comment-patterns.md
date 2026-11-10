# Where the checks come from

Human review comments on PRs #506, #529, #851, #902, #934 (bots excluded), grouped by pattern, with the SKILL.md rule that now covers each. Use this when tuning the skill: a new repeated comment type gets a row here and a rule there.

| Pattern (what the human caught) | Examples | Count | Skill rule |
|---|---|---|---|
| Impossible / always-true guard, unexplained nil check | #529 bir_gen:469, desugar:371, statement:1017, constants:37/39; #506 convert:75/136/325; #851 clean:141 | 9 | Correctness → Impossible conditions |
| Reimplements logic that exists elsewhere | #506 numeric conversion vs cast; #529 casting in values; #851 CLI harness ×4 | 4 | Design → Reuse before reimplement |
| Inconsistency between sibling commands / functions | #851 add vs new case-sensitivity, quoted vs unquoted paths, trailing punctuation ×3 | 5 | Correctness → Consistency between siblings |
| Stale or history-describing comment | #529 ast:1070, bir_gen:1744, symbol:313; #851 add:159 (too long) | 4 | Hygiene → Comments describe code as it is now |
| Unwanted files in PR | #529 `.claude/settings.local.json`, `coverage_report.html` | 2 | Hygiene → No unwanted files (explicit list) |
| New public API / exported symbol without need | #506 semtypes predefined_type:83; #529 expressions:769 | 2 | Design → Visibility and API surface |
| Field on hot struct that most instances don't use | #529 symbol:262 (annotations on every TypeSymbol) | 1 | Design → Visibility (side table) |
| Representation: strings/slices for a fixed set | #529 node_builder:2734 (Point as byte enum), symbol:867 (bitset) | 2 | Design → Representation |
| Repeated traversal / repeated type switch / unneeded clone | #506 convert:30 (two passes); #529 constants:103, values:54 | 3 | Design → Representation, Efficiency |
| Parallelism or multi-phase pipeline without measured need | #529 type_resolver:1101/1102, constant_evaluator:65 | 4 | Design → Over-engineering red flags |
| Thread-safety of writes to shared state | #529 type_resolver:925/938 | 2 | Correctness → Concurrency |
| Behavior differs from jBallerina / spec | #506 review (cyclic, defaults, nilable-required); type_resolver:5514; #529 bir_gen:389 | 5 | Correctness → Spec gaps + jBallerina differential |
| Missing spec contract on a public runtime function | #506 convert:26 | 1 | Design → Spec contract |
| Equality where subtype check is needed | #506 convert:61 | 1 | Correctness → Semtype comparisons |
| Corpus fixture changed — intentional? | #506 missing-member.txtar; #529 desugar:524 ("added to satisfy corpus tests") | 2 | Correctness → Corpus fixture changes |
| Test depth: only flat cases | #506 clonewithtype-numeric-v.bal:18 | 1 | Tests → Depth |
| CLI flag without corpus coverage across commands | #851 build:103 (`--target-dir`) | 1 | Tests → Every new CLI flag |
| Reviewer had to write the `.bal` that covers a line | #902 constant_evaluator:418/294 | 2 | Tests → Coverage (skill writes it) |
| Exception to a rule only probed on its intended use | #1024 (CodeRabbit) `init` may assign a deferred `final` twice / with `+=`; #1024 also reused #973's conclusions unprobed | 1 | Correctness → Exceptions to a rule; re-submitted code gets fresh probes |
| Hygiene step skipped in a manual review | #1020 new test without `t.Parallel()`, 5-line struct field comment; #684 changed tests; #1013 one of three tests | 3 | Hygiene → run `check_parallel.py` and the added-comment listing every time |
| Scope creep / wrong release | #934 subset10 functions in subset9 docs; #851 test templates before test support | 3 | Design → Scope |
| Follow-up without an issue | #529 module:38; #506 issue #657 | 2 | Design → Deferred needs an issue |
| Missing package doc / spec terminology | #506 never.go:16, predefined_type:83 | 2 | Hygiene → Package doc, spec terminology |
| Platform-dependent test (root / Windows) | #851 clean_test:105 | 1 | Correctness → Platform |
| `-race` failure exposed by a new corpus test in untouched code | #684 review body: `semtypes/env.go:113` unlocked `len(recListAtoms)`, first failing on `multiple-from-v.bal` | 1 | Correctness → `go test -race`; Scope exception |
| Valid member of an input family rejected (new error replaced "unimplemented") | #684 `from var i in 1...3` → "is not an iterable collection" | 1 | Parity → probe every member of the family |
| Prior reviewer's summary-level ask left unanswered | #684 `-race`, ranges `-fe` test (review body, no thread) | 2 | Scope → Prior review on an open PR |
| Edge case in CLI semantics (workspace root) | #851 add:112 | 1 | Correctness → Consistency + Spec gaps (CLI behaviour) |
| Convention: AST is pure data, no view/adaptor | #529 ast:1069/1094 | 2 | Design → Project conventions (`AGENTS.md`) |
| Naming nit | #529 symbol:75 (ValueSymbol vs VariableSymbol) | 1 | Nit (no rule) |
| Deep architectural redesign | #529 ast:235 (constant folding at symbol level) | 1 | Not automatable — human reviewer, via INTENT.md Approach |

## Rules taken from `nutcraker-review-guidelines` (heshanpadmasiri)

Applied via the Inputs section rather than copied: stage-aware defensive-check rule, boolean→enum, temporal dependencies / stage context, shallow helpers and single-impl interfaces, forwarding proxies, derived fields, zero-value over is-set, lint-suppression comments, sole-panic functions, cache repeated calls / map lookups, name-prefix → package, doc-comment content rules, illegal states unrepresentable, and the "flag for human" list (dependencies, disabled tests, unrelated changes, benchmarks). The -e/-p coverage rule is his as well. This skill applies these rules directly when `nutcraker-review-guidelines` is not present locally; adopt it as the authority once it exists in this repo.

## Not covered on purpose

- Architectural redirection (e.g. "fold constants at symbol level, not AST"). This is the human reviewer's job and is why `INTENT.md` has an Approach and Alternatives section — the reviewer should see the design before code exists.
- Naming preferences. Reported as nits only when they contradict spec terminology or `AGENTS.md`.
- Anything outside Nutcracker (`ballerina-lang-go`). jBallerina source is a behavior reference only (step 8), not a review target.

## Conventions the skill assumes are in `AGENTS.md`

Added there alongside this skill:

- AST nodes are pure data; no view/adaptor wrappers.
- Annotations (and other sparse per-symbol data) live in the compiler env keyed by symbol ref, not as struct fields.
- A scenario with no corpus test is one that cannot happen; unreachable branches are dead code.
- Prefer an internal error over a silent guard when an invariant is assumed.
- `doc/lang/subsetN.md` documents only what `corpus/bal/subsetN` exercises.
- When a PR changes behaviour because a linked issue says "the spec allows it", read the cited spec clause yourself: the issue can be wrong (#1060 relied on #1051, but §7.15.3 excludes the nil-lifted form).
- A comment above a new unit test that justifies why it is not a corpus test is intended, not reviewer noise; a new unit test without one is the Nit (heshanpadmasiri on #1059, withdrawn finding).
- Before reporting "jBallerina accepts it, so head is wrong", find the spec rule for that exact construct: jBallerina narrows variable-reference lvexprs, but §7.15.1 gives them the declared type (#1060, withdrawn finding).
- Listing uncovered changed lines is not triage: probe each one with a `.bal` program. Reachable means a Nit to add a corpus test; unreachable means a Nit to delete it (#1060: the `f += 1` function arm was reachable, the annotation arm was dead; both were only listed).
- Stacked PRs are reviewed as one unit at the tip and commented per PR: #1024 got two Important findings that #1023 (higher in the same stack) already fixed. Re-run each repro at the tip before posting (`stack.py`).
- A finding dropped as a duplicate of someone else's still-open comment still gets a `Still open (raised by <login>)` summary item; otherwise the summary reads as a miss (#1089 subset1 tests).
- Every `check_parallel` hit is posted as its own Nit with the `t.Parallel()` suggestion, even when another finding asks to delete that test (#662: folding it into the delete-the-test Nit hid it if the test is kept).
- On a re-review, carry over every still-true PR-level summary item from the previous summary (re-check each one); rewriting the summary from scratch dropped a still-valid commit-message note on #712.
- Stdlib ports: probe every setter × getter pair (setXml→getText, setJson→getText, setByteArray→getText, …), not just the getter for its own type (#712 getText on an XML body).
- Native stdlib code: register externs with named functions, not inline closures (user rule, #662); post one Nit per inline closure.
- Diff every probe output line against jBallerina, not only the field the probe targets (#662: the node probe also showed toString padding 0002 vs 02, unnoticed).
- Doc/README changes: grep the declaration behind every factual statement in a changed line (record kind, readonly, distinct, signature); behaviour probes alone miss wording errors (#1144 "open record").
- Skill/process-doc edits: cross-check new step prose against the checklist both ways (#1144 missing package-list checklist item).
- Run check_duplicate_tests.py on every PR that adds corpus tests; triage NEAR hits by the printed token diff (#1124: final vs plain module var is a deliberate variant).
- Withdrawn (2026-10-07, heshanpadmasiri on #1099): don't merge a PR with other non-stacked open PRs or rehearse a rebase onto main to look for breakage; CI and the merge queue catch it, and the pairs grow with every open PR.
