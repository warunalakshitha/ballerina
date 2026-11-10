---
name: pre-pr-review
description: >-
  Local pre-PR review for Ballerina Nutcracker (ballerina-lang-go), for an
  unpushed local branch or an already-open PR by number/URL. Checks INTENT.md,
  Conventional Commits, no Co-authored-by / AI authors, Go quality, impossible
  guards, sibling consistency, reuse, dead code, patch coverage from local go
  test (no Codecov), jBallerina parity, and writes
  docs/changes/<release_number>/<issue_number>/review-report.md with a diff hash that
  `make review-check` verifies (in CI and pre-push). Use when the user asks
  for pre-PR review, /pre-pr-review, "am I ready to push", to review an
  unpushed branch, or to review/post an existing ballerina-nutcracker/ballerina
  PR by number or URL.
---

# Nutcracker pre-PR review

You are the last check before a human sees this PR. The reviewer will read
`INTENT.md` and the `.bal` tests, not the diff — anything a line-by-line
reviewer would have caught is your job. Thorough on substance, quiet on style.
You never approve a merge.

There is no common launcher across coding agents, so this process does not try
to invoke one: it specifies the required artifacts, not the tool that
produces them. A PR must come with `INTENT.md` and `review-report.md`; the
report is produced by running this skill with whatever agent the developer
uses, and `scripts/review-check.sh` verifies the result (in CI and pre-push).

## Local-only

Run entirely on this machine: local `git`, `go`, `golangci-lint` / `staticcheck`,
`bal`, local jBallerina source. No Codecov, CodeRabbit, cloud agents or CI as
the runner. Do not open a PR or post to GitHub unless the user asks.

| Role | Path |
|------|------|
| Nutcracker (Go) | the repo you are in (`$ROOT`, must contain `AGENTS.md`) |
| jBallerina source | `$JBALLERINA_SRC` (default `../ballerina-lang`) |
| jBallerina CLI | `bal` on PATH |

Read `AGENTS.md` and `CONTRIBUTING.md` before judging style or tests. Rules
cited below as "team rule" live there.

## Inputs

- Branch diff vs merge-base with `origin/main` (committed + staged + unstaged
  unless the user says uncommitted-only).
- `docs/changes/<release_number>/<issue_number>/INTENT.md` (`<release_number>` is the next release tag, e.g. `v0.7.0`) — the developer's problem, approach,
  change map, deferred items. Written in plain English. Always (re)generate its **Change map** table from the diff — one row per changed
  `.go`/`.bal`/`.py` file with a one-line reason — and keep any reasons the
  developer already wrote. If the file is **missing**, draft Problem and Approach
  from the diff too, write it to that path, and report Important:
  *"INTENT.md was agent-drafted — rewrite the Problem and Approach in your own
  words before opening the PR."* If it reads like agent output (long, vague,
  complex wording), report a Nit with a plain-English rewrite.
- `.agents/skills/nutcraker-review-guidelines/SKILL.md` — the team's review rules (owner: heshanpadmasiri), when present in the repo. **Read it and apply every rule in it**; the passes below name the most frequently missed ones but the guideline file is authoritative when they differ. If it does not exist yet, skip it and rely on this file plus `AGENTS.md`.
- `references/review-comment-patterns.md` — where each rule below came from.

Scope is Nutcracker (`ballerina-lang-go`) only: judge everything against this
repo's `AGENTS.md`, its Go conventions, and its corpus tests. Read jBallerina
source under `$JBALLERINA_SRC` only as a behavior reference (step 8), never as
a style or process authority.

## Workflow

Copy and track:

```
Review progress:
- [ ] 1. Scope diff + base
- [ ] 2. Read / draft INTENT.md
- [ ] 3. Commits, authors, trailers
- [ ] 4. Hygiene
- [ ] 5. Correctness and regression
- [ ] 6. Design vs intent
- [ ] 7. Tests and patch coverage
- [ ] 8. jBallerina parity
- [ ] 9. Verify every finding; drop false positives
- [ ] 10. Fix what you can, re-run 4–7
- [ ] 11. Write review-report.md (hash last)
- [ ] 12. Post to the PR (only when asked)
```

### 1. Scope

```bash
ROOT=$(git rev-parse --show-toplevel); cd "$ROOT"
BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'); BASE=${BASE:-main}
MB=$(git merge-base HEAD "origin/$BASE")
git status -sb; git log --oneline "$MB"..HEAD; git diff --stat "$MB"...HEAD
git diff "$MB"...HEAD; git diff; git diff --cached
```

Collect changed `.go` (non-test), `.bal`, `.py`, `.txt`/`.txtar` paths. Use a
`/tmp` worktree if the main tree has unrelated dirty state.

**Reviewing an already-open PR by number/URL** (no local branch, no push
access) works the same way, in a dedicated `/tmp` worktree: `git fetch
<remote-url> refs/pull/<N>/head:pr-<N>`, then `git worktree add <path>
pr-<N>`. Get the base from `gh api repos/<owner>/<repo>/pulls/<N> --jq
'.base.sha'`, but **do not trust it as the merge-base** — `main` may have moved
since the PR branched, so that field can point at a commit that isn't even an
ancestor of the PR (confirmed happening in this series). Always compute the
real one: `git merge-base --is-ancestor <reported-base-sha> <pr-branch> ||
git merge-base <pr-branch> origin/main` and use whichever commit that returns.
Steps 2–11 are otherwise identical, except that nothing is written into the
repo: no `docs/changes/`, no drafted `INTENT.md`, no `review-report.md`. The
report goes to chat; `findings.json` (step 12) lives in a temp/scratch directory
outside the checkout. A missing `INTENT.md` is not a finding here; the PR
description carries the context. This is the primary way to review an
existing PR with this skill.

When picking open PRs to review or re-review, skip drafts and PRs labelled
"don't merge" (any spelling), and say how many were skipped. To tell whether a
PR needs re-review, compare its head with the `reviewed` SHA in the **newest**
summary comment (7-40 hex chars); some PRs carry more than one.

**Not this review's job — CI and the merge queue own it:** interactions with
other open PRs that aren't in the same stack (an API one redefines, a golden
both touch) and re-running tests after a hypothetical rebase onto `main`.
Checking every pair grows with the number of open PRs, and the merge queue
rejects whichever lands second if they break. Report a merge conflict with
`main` only as a one-line summary item (GitHub already shows it).

**Stacked PRs.** Always run `python3 .agents/skills/pre-pr-review/scripts/stack.py <N>`
first. It follows base branches down to `main` and open PRs up from this one,
fetches every head to `refs/pr-stack/<n>`, and prints each PR's own range. A
one-line result means the PR isn't stacked: carry on as above. Otherwise
review the stack as one unit and comment per PR:

- Build and probe at the **tip** (`refs/pr-stack/<top>`) over the whole stack
  diff (`<bottom base>..<tip>`). The team lands a stack together, so the tip is
  the code that ships; a PR's own head is only checked to attribute a problem.
  If a PR in the stack is marked or described as landing alone, review it on its
  own instead.
- Scope stays per PR: a finding belongs to the PR whose own commits added the
  line. Attribute with `stack.py <N> attribute <path:line>...`; a line owned by
  another stack PR goes to that PR, never to this one.
- Verify every finding against the rest of the stack before posting, in a
  separate subagent with a fresh context (given the finding, its repro and the
  tip SHA): it re-runs the repro at the tip and reads the later PRs' diffs for a
  fix. Only findings that survive are posted on PR k.
- Before posting anything on PR k, re-run its repro at the tip. Broken at the
  tip → post it on PR k. Broken at PR k's head but fixed by a later PR m → no
  finding; add `{"pr": m, "text": "...", "id": "<old finding id, if one was
  posted>"}` to `stack.fixed_later` in PR k's `findings.json` (the summary shows
  it and an old comment is resolved with "fixed later in the stack by #m").
- Coverage and tests are measured at the tip: a line in PR k covered by a test
  in PR m is covered (say so in PR k's report). Uncovered lines are attributed
  like findings.
- A `note:` saying a PR isn't based on the current head of the PR below means
  the stack needs a rebase; put it in the lowest affected PR's summary items.
- Write one `findings.json` per PR, each with the same `stack` block from
  `stack.py <N> --json`. When any PR in the stack moves, re-review the stack;
  `post_review.py` refuses to post while any recorded stack head is stale.

**Prior review on an open PR.** Before issue hunting, collect what others
already raised — humans, CodeRabbit, other bots and agents (everything except
this skill's own marked comments):

```bash
gh api repos/<owner>/<repo>/pulls/<N>/comments --paginate   # inline threads
gh api repos/<owner>/<repo>/pulls/<N>/reviews --paginate    # review bodies
gh api repos/<owner>/<repo>/issues/<N>/comments --paginate  # PR conversation
```

Collect again before every re-post: bots often review after you do (CodeRabbit's
#1061 review, with an outside-diff finding in its body, arrived two minutes
after this skill's summary).

Review bodies and conversation comments carry findings too (a `-race`
failure, "please add a `-fe` test"); they have no reply thread, so nothing
shows whether they were addressed. For every prior concern, decide at the
reviewed head whether it is fixed (re-run its repro; an author's "Fixed with
<sha>" is a claim to check, not proof) or still open. Then:

- A finding of yours that matches a prior concern on the same line or about
  the same code is **not re-posted**. It goes under **Already raised (not
  re-posted)** in the report with who raised it, and whether it is still
  open at head. Still-open Important ones count toward `important:` — they
  are real defects, only the comment is a duplicate. Every such concern that
  is still open at head (any severity you'd have posted) also gets one
  `summary.items` line, `Still open (raised by <login>): <what>`, so the PR
  summary doesn't read as if it was missed (#1089: the subset1 tests were
  caught but only Heshan's comment showed them). Write the login without `@`
  so it doesn't notify anyone.
- A prior concern that is still open at head but that you did not find
  yourself is a miss in this review: confirm it and list it the same way.
- Fixed prior concerns are one Evidence row ("N prior concerns, M fixed at
  head"), not findings.

### 2. Read / draft INTENT.md

See `## Inputs` above for what to do when `docs/changes/<release_number>/<issue_number>/INTENT.md`
is present, missing, or reads like agent output — do it now, before any issue
hunting, since the rest of the workflow (especially step 6's "does the code do
what INTENT.md says") depends on it existing.

### 3. Commits, authors, trailers

For every non-merge commit on `$MB..HEAD`:

- Conventional Commits: `python3 .github/scripts/validate_commits.py "<subject>"`.
  Types `feat fix build chore ci docs style refactor perf test revert`; lowercase
  description; ≤ 72 chars. Also check the likely PR title.
- No `Co-authored-by:` trailer of any kind.
- No AI agent as author/committer (`cursor`, `copilot`, `claude`, `anthropic`,
  `openai`, `gemini`, `noreply` bots), no `Generated-by:` / `Assisted-by:`
  trailers, no body claiming AI generation. Report SHA + subject.

### 4. Hygiene

- `make fmt` / `make lint` (or `golangci-lint run ./<affected>/...`) clean — fix, don't report.
- License headers on new `.go` / `.bal` files (templates under `cli/templates/` are exempt).
- Team rule: every new/changed `TestXxx(t *testing.T)` and each `t.Run` subtest calls
  `t.Parallel()` — once at the top level and once per subtest, not only inside the
- `check_parallel` hits on pre-existing tests whose `func` line is outside the diff (the PR only edits their body) go in one optional summary item listing them, not one Nit per test (#1078). Tests the PR adds, or whose top-level lines it changes, still get a Nit each.
  subtests. Missing it is mechanical and local; add it and list under **Fixed during
  review** (own branch) or **Nits (suggested, not applied)** (external PR). Always run
  `python3 .agents/skills/pre-pr-review/scripts/check_parallel.py <base>` — don't
  eyeball it; it lists every new or changed test and subtest without the call
  (review each hit: tests that mutate process-global state must stay serial).
- Comments: list every added comment line with
  `git diff -U0 <base>...HEAD -- '*.go' | grep -n '^+\s*//'` and judge each one
  against the rules below, struct field comments included — a manual review that
  skips this list misses them.
- No unwanted files: agent-local settings (`.claude/settings.local.json`, `.cursor/`),
  coverage output (`coverage_report.html`, `*.out`), scratch `_*.bal`, debug dumps,
  files unrelated to the intent.
- New corpus tests go in the open subset. Subsets 1–9 are released (subset9
  shipped with 0.6.0), so a **new** `.bal` under `corpus/bal/subset[1-9]/` is a
  Nit: move it to `corpus/bal/subset10/10-<same area>/`, with its goldens
  (`ast`/`cfg`/`desugared`/`bir`) and `corpus/integration` `.txtar`. Editing,
  renaming or re-marking an existing test in an old subset is fine. List them
  with `git diff --name-status --diff-filter=A <base>...HEAD -- 'corpus/bal/subset[1-9]/*.bal'`
  (for a stack, attribute each file to the PR that added it).
- Docs and README lines the PR changes: check every factual statement against
  the source, not only the behaviour claims — a type's shape (open vs closed
  record, `readonly &`, `distinct`), a signature, a default, a path. Grep the
  declaration for each one (#1144 called a `record {| |}` "open"). A row the
  PR doesn't touch is out of scope even if it looks stale.
- Process docs the PR edits (`.agents/skills/**`, CONTRIBUTING, templates):
  every new instruction in the steps must also be in that document's
  checklist, and every checklist item must match the steps (#1144: the root
  package-list step had no checklist entry).
- Native extern registration: each `runtime.RegisterExternFunction` call passes a
  named function (e.g. `createType1Extern`), not an inline closure — one Nit per
  inline closure (#662). A closure that captures `rt` becomes a named function
  returning `extern.NativeFunc`, like `fromAvroExtern(types)`.
- No duplicate corpus tests: run `python3 .agents/skills/pre-pr-review/scripts/check_duplicate_tests.py <base>`
  (about 1 s for the whole corpus). It compares each new `.bal` under corpus/bal,
  corpus/lib and corpus/project with every existing one, ignoring the license,
  comments, markers and string contents. `EXACT` is a Nit to delete the copy;
  `NEAR` prints the differing tokens — post it only when the difference doesn't
  test anything new (e.g. renamed variables), not for a one-keyword variant that
  exercises a distinct case (`final` vs plain module var).
- Standard-library tests have their own corpus and numbering: a new stdlib test is
  `corpus/lib/subset3/<name>.bal` with its only golden at
  `corpus/integration/lib/subset3/<name>.txtar` (no per-stage goldens). A new
  stdlib test under `corpus/bal/...`, or a new file in `corpus/lib/subset1|2`, is
  a Nit to move it there.
- Dead code: `staticcheck` / `golangci-lint` unused; plus by reading — unreachable
  branches, orphaned helpers, interface methods nothing calls (e.g. `Copy()` on a
  symbol never narrowed), duplicate corpus goldens. Team rule: a branch no `.bal`
  program can reach is dead code — **delete it, do not write a unit test for it.**
- Comments: "if the code says it, no comment." Public doc comments state caller restrictions the signature can't (nil behavior, required call order) — and if such a restriction exists, first ask whether the type can enforce it instead. Implementation notes (perf, clever algorithm) go inside the body, not the public doc. Struct field comments say what the field *is*, omitted when the name says it. Remove restating, step-by-step,
  or PR-history comments ("moved from X", "previously did Y"). Keep short "why"
  comments, license headers, corpus `@output`/`@error`/`@panic` markers. Keep the
  comment above a new Go unit test that says why a corpus test can't cover it,
  even when it's several lines or names an issue: maintainers want it in code
  as a signal to agents to prefer corpus tests (#1059). The reverse is a Nit: a
  new unit test with no such justification comment. Match
  neighbors: similar private functions in a package either all have a one-line
  doc or none do. After a refactor, re-read every comment in touched functions
  for staleness. Flag TODOs without an issue number. Each unnecessary,
  oversized or inaccurate comment on a changed line is its own Nit anchored to
  the comment's lines, with the deletion or the shorter/corrected text as the
  suggestion.
- Every new Go package has a `// Package foo ...` comment in one file.
- Names and comments use spec terminology (string/xml are sequence types, not
  basic; error is behavioural).

### 5. Correctness and regression

- Run `go test ./<affected>/...` and the relevant corpus (`go test ./corpus -run ...`
  or `make conformance`). Report the delta vs `origin/main`, not just pass/fail.
- Run the same packages with `-race` (`go test -race ./<affected>/...`; CI runs
  `make test-race`). A race that first fails on a corpus file this change adds
  is in scope even when the racy code is untouched (see Scope of findings);
  compare with `origin/main` to say whether the change introduced or exposed it.
- **Impossible conditions.** For every guard in changed code (`== nil`, `!ok`,
  `len == 0`, "can this be false here?"), decide from the invariants whether it
  can fire. Stage awareness: after symbol/type resolution, symbols and types are
  resolved; after semantic analysis, no malformed AST survives — a nil/zero check
  on those in a later stage hides an established invariant and is a defect. If
  a guard can't fire: remove it, or make it an internal error / panic so a broken
  assumption surfaces. Silent fall-through on an impossible state is Important.
  A function whose only behavior is to panic or raise an internal error obscures
  the failing path — inline it at the call site or delete it. Invariant checks
  that *are* kept need a corpus test showing the path is unreachable.
- **Lint suppressions** (`//nolint`, `_ = x`) without a comment saying why are Important.
- Unnecessary runtime checks: values the compiler already validated (langlib
  args, resolved types) are not re-validated in the runtime.
- Semtype comparisons on types from user code use `IsSubtype` /
  `IsSubtypeSimple`, never equality.
- **Exceptions to a rule.** When the change adds an exception to a restriction
  ("allowed once", "allowed in `init`", "allowed before first read", "allowed
  for locals only"), probe the exception's edges, not just its intended use:
  apply it twice, use the compound form (`+=`), inside a branch, a loop and a
  closure, after a read, and from another module. Each is a `.bal` repro run
  on head and jBallerina.
- Code re-submitted in a new PR (moved branch, stacked rewrite) gets the same
  probes again; don't carry an earlier review's conclusions over unverified.
- Boundaries: `MaxInt64`/`MinInt64`, float→int rounding, nil vs empty, cycles.
  A narrowed or computed result that is then discarded in favour of the original
  is a bug.
- Concurrency: any write to shared state (package resolver, env, caches) from
  code that can run under a concurrent resolver or worker must be shown safe.
- Interpreter stages per `AGENTS.md` (parse → AST → symbols → types → semantic →
  CFG → desugar → BIR → interpret): work happens in the right stage.
- PAL: no platform I/O outside PAL. Symbols: never map-key `model.Symbol`; use
  `model.SymbolRef` via the compiler context.
- Spec: cite the section in the finding (e.g. §6.4 const-expr is compile-time).
  Where the spec is silent, jBallerina is the reference (see step 8). Before
  reporting a jBallerina difference as a bug, quote the spec rule for that exact
  construct (e.g. lvexpr static types in §7.15.1, not the general narrowing
  rules); if the spec decides it, head following the spec is correct. The same
  applies to pre-existing bugs listed under Out of scope / issue candidates: each
  needs its spec rule, or is marked as a question for the team (#1088: "`1 =>`
  after `_ =>` is unmatchable" looked like a bug because jBallerina accepts it,
  but §7.21.2 + §7.4.3 make it a compile error).
- **Consistency between siblings.** Touching one of a family (CLI commands,
  langlib functions, AST node kinds) means checking the others: same flag
  semantics (`bal add -t` and `bal new -t` both case-insensitive), same message
  format (quoted vs bare paths, trailing punctuation), same usage/error shape.
- **Corpus fixture changes.** Every changed `.txt`/`.txtar` expected output is
  listed in the report with the behavior reason from `INTENT.md`. "Changed so
  tests pass" is Important.
- Platform: permission/root/path-separator dependent tests skip or adapt on
  Windows and as root.

### 6. Design vs intent

- The code does what `INTENT.md` says and nothing more. Over-engineering is
  Important; name two red flags explicitly: parallelism or caching without a
  measured need, and collect-then-evaluate phases where one ordered pass
  (topological sort, then fold) would do.
- Scope: extra functions, refactors of untouched areas, docs for another
  release (`doc/lang/subsetN.md` covers only what `corpus/bal/subsetN` exercises)
  → report, move to another PR.
- **Reuse before reimplement.** For each new non-trivial function, search the
  repo for an existing implementation (numeric conversion in cast, casting in
  `values`, CLI harness in `corpus/`). Duplication is Important; say where the
  existing one lives. On a diff too large to search function-by-function
  (dozens of new functions), first run this mechanical pass before the manual
  one — it is cheap and catches the common case for free: list every new
  function name (`git diff -U0 | grep '^+func '`) and grep the whole repo for
  each one's verb/noun stem (`validate`, `parse`, `resolve`, `is`, …) across
  *all* packages the diff touches, not just the file it's in — a name landing
  in both a domain package (`values`, `semtypes`) and a thin caller package
  (`lib/langlibs/...`, `runtime/...`) is the specific shape to watch for: the
  domain implementation is usually unexported, forcing the caller to
  reimplement it instead of the two being kept in sync. Only after this pass
  turns up nothing do you fall back to reasoning about behavior from scratch
  for the remaining functions.
- Spec contract: a public function implementing language behavior names the
  spec abstract operation / section in its doc comment and matches it. No spec
  counterpart → the contract is stated.
- API surface: a new exported symbol needs a caller outside its package, else
  unexport. No one-off helpers in `semtypes` / `model`. Sparse per-symbol data
  (annotations) lives in the compiler env keyed by `SymbolRef`, not as a field
  on every symbol/AST node (team rule; AST is pure data — no view/adaptor
  wrappers).
- Representation: fixed small sets are an enum/byte or bitset, not strings or
  slices; mutually exclusive booleans become one enum, independent flags a
  bitset with set/check methods. Prefer a field's zero value over a separate
  "is set" boolean when a safe nonzero encoding exists. Illegal states should be
  unrepresentable (sum types + private marker methods, `gochecksumtype`) rather
  than checked. Repeated type switches on one value collapse into one function.
  Clones/copies with no later mutation go.
- Shape: shallow private helpers with one caller are inlined (exceptions: data
  preparation, interface accessors, parent proxies, public inner-package
  proxies); no interface with a single implementation unless there is a real
  boundary; no forwarding proxy kept for a superseded API — update callers and
  delete it; excessive callbacks/hooks where the decision could be made ahead of
  time and passed as a value; setters where the value is known at construction.
  Several types/functions sharing a name prefix → a focused package.
- Temporal dependencies are explicit: ordered stages return the values the next
  stage consumes instead of mutating hidden shared state; stage-specific state
  lives in the stage context, not on AST or symbol structs. Stored derived
  fields are suspect — accept only with a comment giving the perf reason, source
  fields private, and every update method updating source and derived together.
- Efficiency: cache a stable method result reused within one function; avoid
  repeated lookups into a shared map during one computation (use a handle or
  index); consider struct-of-arrays when a hot loop reads one field from an
  array of structs.
- Errors: user-facing errors carry position, value and target type; panics that
  need a stack trace keep it.
- Change map: you generated it (step 2); now check every reason still holds
  against the final diff (non-code files exempt). Every Deferred item has a
  reason and an issue; "will do in a separate PR" in a comment or
  this report also needs an issue.

### 7. Tests and patch coverage

Rule: every behavior change has a `.bal` scenario test through the interpreter
asserting observable behavior. Go unit tests alone don't satisfy it. Areas a
`.bal` program cannot reach (CLI, tooling) use integration/unit tests — the
developer states this under Deferred; you don't grant exceptions.

- Map each behavior change in `INTENT.md` to a `.bal` test; write missing ones
  or report Important with a paste-ready snippet.
- Depth: type-driven logic (conversion, union candidates, narrowing) has at
  least one case more than one level deep — nested records with union fields.
- Every new CLI flag is exercised in the CLI corpus for every command that
  accepts it.
- Bug fixes: the failing `.bal` test exists in a commit before the fix and fails
  on `origin/main`.
- Mutation check: revert the core change, run the new tests, confirm they fail,
  restore.
- Uncovered code that is not an internal error / unimplemented path needs a corpus test: front-end paths a `-e` test, runtime paths a `-p` or `-v` test; validate the new test's output against jBallerina.
- Completeness check before posting: every uncovered line in the coverage table ends up as a posted Nit (reachable → add test; unreachable → delete) or as a report line naming the program you ran and its result. A line that is only listed means the review isn't finished. Re-do this on every re-review, since new heads can move lines.
- Never assert a branch is unreachable/internal-error/deferred without a repro attempt, and verify each uncovered branch independently — do not extend one branch's classification to a neighbor just because they're adjacent, share a comment, or look like "the same story." Two failure modes to watch for: (1) trying one negative example against an eligibility rule and stopping there — if the rule has multiple ways to qualify (e.g. a type-level filler check with several branches), construct a case for *each* branch of that rule, not just the first one tried; (2) several adjacent uncovered ranges getting one shared explanation instead of each having its own precondition traced and, where feasible, its own `.bal` repro run. If you can't verify one within reasonable effort, write "not verified, only inspected" in the report rather than asserting unreachability as fact.
- An uncovered failure check after a call (`if !ok`, `if err != nil`, a nil check on the result) is only "the error path" if the callee can produce that result. Open the callee and find a `return …, false` / non-nil error / nil return that the call can reach. If it has none (e.g. its only return is `return x, true`), the check is dead: post a Nit to drop it, and mention any identical pre-existing checks against the same callee. Never label such a line "early return when X fails" without naming the return statement in the callee that makes it fail. (Missed twice on #1104, where `resolveMatchClause`'s only return is `return bodyEffect, true`.) This applies to the result of a specific callee. A guard inside a general accessor (e.g. a `CompilerContext` method documented for several symbol kinds, doing `x, ok := sym.(Iface)`) is not dead just because today's only caller passes the right kind; don't ask to replace it with a bare assertion (#1063).
- When there are too many uncovered ranges to individually trace within reasonable effort (patch coverage already at or above target, or a single file with a long list), don't sample arbitrarily — triage by classification first, using whatever categorization the diff or its own PR description already gives you (e.g. a stated semanticError/unimplemented/internalError split): spend the budget on the categories a reachable instance would actually need a test for (semantic-error branches, and plain successful-evaluation paths for a specific case/operator) before spending any of it on branches that are exempt by definition (internal-error/panic-recovery paths). The exempt category is the easiest to confirm and the lowest-value to check — don't let its ease of dismissal eat the budget meant for the categories that matter. State plainly which categories you sampled and which you skipped, so the gap in coverage-of-verification is visible, not just the gap in code coverage.
- Patch coverage: `python3 .agents/skills/pre-pr-review/scripts/patch_coverage.py`
  runs `go test -covermode=atomic -coverpkg=<changed pkgs> ./<pkgs>/... ./corpus/...`
  and intersects with `git diff -U0`. Paste its table into the report and its
  total into `patch_coverage:` in the frontmatter. **Target: 80% of changed
  statement lines.** Below 80% is reported as a finding (Important unless every
  uncovered range is listed under Deferred in `INTENT.md` with a reason); it
  does not block the push by itself — the human reviewer decides whether the
  Deferred reasons are acceptable. For each uncovered range: write the `.bal` that
  reaches it (prefer `corpus/bal/...` / `corpus/lib/...`, `*-v.bal`/`*-e.bal`/
  `*-p.bal`), or report Important unless `INTENT.md` lists it under Deferred.
  Unreachable from `.bal` → Dead code, not a coverage gap. Same file+lines at
  most once; one snippet may cover several gaps.

### 7b. Flag for the human reviewer

These are reported in their own section, not counted as findings, because the
decision is the reviewer's:

- New dependencies (`go.mod` / `go.sum` changes) — name them and why.
- Disabled or skipped tests (new entries in `test_util/skip.go`, `t.Skip`,
  commented-out cases) — each needs an issue link; report ones without.
- Unrelated changes and public API changes not mentioned in `INTENT.md`.
- Performance: if the change touches `runtime/`, `values/`, `semtypes/` or the
  interpreter loop, run the corpus benchmarks against `origin/main`
  (`corpus/bench`, same runner as the CI benchmark workflow) and report any
  case where the difference exceeds one standard deviation, with the run-to-run
  variance stated.

### 8. jBallerina parity

Run when semantics, runtime, stdlib, or error/panic positions change (skip and
say why for docs/CI/chore). For each new langlib function or value operation
write 3–5 edge-case programs — cyclic values, defaults, nilable-required fields,
empty/nil, nested unions — then:

```bash
go run ./cli/cmd run <file>      # Nutcracker
bal run <file>                   # jBallerina
```

When the change accepts or rejects a family of inputs (iterable collections,
numeric types, binding patterns, clause kinds), probe every member of the
family, not only the ones the new tests use — for iteration: list, map,
string, xml, table, stream, `object:Iterable`, `1...3` and `1..<3` ranges,
and a union of two of them. A new semantic error that fires on a valid program
is a regression even where the feature used to be unimplemented; a member left
unsupported needs a `-f*` test.

Compare stdout/stderr/exit and error line numbers (messages may differ). Every
divergence is a finding until `INTENT.md` justifies it. Read the jBallerina
source under `$JBALLERINA_SRC` when intent is unclear.

### 9. Verify findings (drop false positives)

Before fixing anything, re-check every finding from steps 4–8 as if you were a
second reviewer who has not seen your reasoning. Where the agent supports it,
do this in a fresh context (subagent or new session) given only the diff, the
finding list, and `AGENTS.md`; otherwise do it sequentially, one finding at a
time, re-reading the code rather than your notes.

For each finding confirm the claim against the code, not the diff hunk alone:

- "guard can't fire" → trace the callers and invariants; if any path can reach
  it, the guard stays and the finding goes.
- "duplicates existing logic" → open the existing implementation; if the
  semantics differ (e.g. cast allows numeric conversion, this path must not),
  it is not duplication.
- "not covered" → check the corpus for a test that already reaches it and check
  whether it is unreachable from `.bal` (then it is dead code, not a gap).
- "inconsistent with sibling" → confirm the sibling really behaves differently
  today, not in an older version.
- "diverges from jBallerina" → re-run the program on both if you inferred it
  from reading.
- "unused / dead" → grep for callers including tests, generated code and `.bal`
  externs before declaring it dead.
- Anything you can only support with "looks like" or "probably" is dropped.
- Stacked PR → re-run the repro at the stack tip; fixed there by a later PR
  means it moves to `stack.fixed_later`, not a finding (see step 1).

Record only the count under **Verification** in the report ("N findings
checked, M dropped") so the reviewer can see the second pass ran; the dropped
items themselves stay out. Only verified findings feed `important:`.

### 10. Fix, then re-run

On your own branch: fix directly — fmt, lint, dead code, comments, unwanted
files, missing `.bal` tests you can write confidently. Report only: behavior,
design, `INTENT.md` content, anything unsure. Never edit an existing test to
make it pass. After fixing, re-run steps 4–7 so the report describes the final
state. New findings from the re-run go through step 9 too.

Reviewing an already-open external PR (no push access): nothing here gets
fixed. Mechanical nits that would have been fixed go under **Nits (suggested,
not applied)** in the report instead (see the Nit rule in Severity) — list
them, don't drop them just because you can't apply them yourself.

### 11. Report

Write `docs/changes/<release_number>/<issue_number>/review-report.md` from
`assets/review-report.md`. Compute after all fixes are committed:

- `reviewed_diff`: `git diff origin/main...HEAD -- . ':!docs/changes/' | sha256sum` (macOS: `shasum -a 256`)
- `skill_version`: `cat .agents/skills/pre-pr-review/SKILL.md .agents/skills/nutcraker-review-guidelines/SKILL.md 2>/dev/null | sha256sum` (macOS: `shasum -a 256`) — a rule change in either file invalidates old reports; if the guidelines skill does not exist locally, hash `pre-pr-review/SKILL.md` alone

`scripts/review-check.sh` verifies both in CI and pre-push; a stale hash
rejects the push. Verdict is exactly one of:

- `0 Important findings — ready for human review`
- `N Important findings — fix first`
- `0 Important, N to verify — run parity first`
- `Needs design discussion — <reason>` (only when the approach itself is in question)

### 12. Post to the PR (only when asked)

Write `findings.json` next to the report (local, not committed) from
`assets/findings.json`, following `references/github-posting.md`: short title,
at most three sentences, every example a runnable ```` ```ballerina ```` program or
a `suggestion`. Leave out the INTENT.md finding, **Fixed during review**,
**Already raised (not re-posted)** and Evidence; they stay in the report. For a
stacked PR, add the `stack` block from `stack.py <N> --json` and fill
`fixed_later` (step 1). Then:

```bash
python3 .agents/skills/pre-pr-review/scripts/post_review.py <findings.json>         # dry run → pr-comment.md
python3 .agents/skills/pre-pr-review/scripts/post_review.py <findings.json> --post  # after the user approves
```

Show the user the dry-run preview and fix every brevity warning before posting.
An overlap warning means someone else already commented near that line: drop
the finding from `findings.json` if it is the same concern, keep it only if it
is a different one.
Line findings become inline comments, the rest one short summary comment, and
reruns update, resolve or add comments instead of duplicating them.

## Scope of findings

Findings count only on lines this change adds or modifies (the `git diff -U0`
ranges), plus files it creates. Problems you notice elsewhere — an old bug, an
inconsistent message in an untouched command, a stale comment the diff didn't
reach — are **not reported** and not fixed in this PR. If one is clearly worth
tracking, say so in one line in your chat reply to the developer so they can
open an issue; it never enters the report. Different agents notice different
things outside the diff; keeping them out of the report keeps the verdict the
same regardless of agent.

Exception: a pre-existing problem that the change makes worse or newly
reachable (a new caller of a buggy function, a new branch inheriting an
unchecked assumption, a new corpus test on which `-race` first fails) is in
scope and counts.

## Severity

Important is a gate: every Important blocks the push. Reserve it for things
that would ship wrong behavior or leave a behavior change unverifiable. A rule
violation is not automatically Important — ask "what goes wrong for a user or
the next developer if this merges as-is?"

- **Important** — (a) confirmed divergence from spec or jBallerina, or a
  confirmed bug; (b) a user-observable behavior change with no `.bal` test;
  (c) `INTENT.md` missing, or the code contradicts it; (d) a changed corpus
  fixture with no behavior reason; (e) a team-rule violation whose consequence
  is a wrong result (e.g. a defensive check that masks a real invariant break
  on a reachable path).
- **Verify** — a suspected divergence or bug you could not confirm (parity not
  run, jBallerina source unclear). Listed with the exact program to run. Does
  **not** count toward `important:`; the developer confirms and it becomes
  Important or is dropped.
- **Nit** — everything else: style, naming, clarity, missing `default:` on a
  compiler-guaranteed switch, duplication that doesn't change behavior, doc
  comments, representation choices. General test: the code (or a comment)
  merely implies something a naming/structural convention already establishes
  — e.g. a doc comment restating what a self-explanatory field/signature
  already says, checked against its neighbors (siblings that are equally
  self-explanatory but uncommented are the tell); a switch missing `default:`
  where the language guarantees exhaustiveness; a name that duplicates its
  type. **Nits are never reported** as findings — they never count toward
  `important:` and never gate the push; the human decides whether to keep or
  drop each one, you only surface it. On your own branch (push access), apply
  each mechanical, local one yourself (fmt, comments, a `default:`, a magic
  length, an obvious `strings.Cut`) and list it under **Fixed during review**;
  drop the ones that aren't mechanical. Reviewing an already-open external PR
  (no push access) — you can't apply it, but don't drop it either: list it as
  a suggested fix under **Nits (suggested, not applied)**, one line, file:line
  + the concrete fix, so the human can decide without it being a finding. The
  report contains only what must be fixed, confirmed, or decided as findings;
  nits live in their own section either way.

Calibration examples from the #873 dry run: `strip()` whitespace regrouping
(confirmed vs jBallerina) — Important; `getAttributes` copy vs live — Verify
until run on `bal`, then Important; missing `default:` in `concat` — Nit, add
it and list under Fixed; duplicated namespace validation — Nit, consolidate
and list under Fixed; equality change without a `.bal` test — Important under
this process (b), because the reviewer cannot otherwise tell the change is
intended.

## Where the rules come from

`references/review-comment-patterns.md` maps each rule to the human review
comments on past PRs that motivated it. When a reviewer catches something twice
that this skill missed, add a row there and a rule here. Anyone with write access
can do this via a normal PR; no separate owner.

## Out of scope

Codecov / CodeRabbit as a source of findings (this skill's own
`patch_coverage.py` and jBallerina-repro parity replace them; their comments
are read only to avoid re-posting what they already said), approving or
merging. Posting review
comments is in scope when the user asks (step 12) — it is not "opening a PR or
posting to GitHub" in the sense `## Local-only` warns against; it is delivering
this same review.

The older `.agents/skills/pr-review/` (a separate, superseded skill living in
a different checkout of this repo) predates `INTENT.md`/`review-report.md`
and `patch_coverage.py`: it produces a chat-only report and leans on scraping
Codecov/CodeRabbit bot comments instead of measuring coverage or running
parity itself. Prefer this skill for reviewing an already-open PR too; only
reach for that one if you specifically want the Codecov/CodeRabbit-comment
angle it has and this one doesn't.
