---
name: pr-review
description: >-
  Reviews Ballerina Nutcracker PRs (ballerina-nutcracker/ballerina). Starts with
  what the fix is, example Ballerina code, and a point-form implementation summary,
  then Conventional Commits, no Co-authored-by / AI authors, Go quality, unused
  code, Codecov gaps, skips concerns already raised by humans/CodeRabbit/bots,
  optional jBallerina parity against a local ballerina-lang clone, plus
  companion checklists for stdlib and language server PRs. Use when the
  user pastes a GitHub PR URL for ballerina-nutcracker/ballerina, asks to review
  a Nutcracker PR, or mentions nutcracker PR review / codecov / coderabbit on that repo.
---

# Ballerina Nutcracker PR Review

## Local-only

Run entirely on this machine. Do **not** use hosted automations, cloud agents, or remote CI as the review runner.

- Checkout and build/test in the local Nutcracker clone (or a local `git worktree` under `/tmp`).
- Use local `gh`, `go`, `bal`, and local jBallerina source.
- Deliver the report in chat only. Do **not** post GitHub comments unless the user explicitly asks.

Local roots:

| Role | Path |
|------|------|
| Nutcracker (Go) | this repo's root (`git rev-parse --show-toplevel`) |
| jBallerina source | `$JBALLERINA_SRC`, a local clone of `ballerina-platform/ballerina-lang` (ask the user for the path if unset) |
| jBallerina CLI | `bal` on PATH (`bal run` / `bal build`) |

Repo rules: read `AGENTS.md`, `CONTRIBUTING.md` and `doc/guides/CODING_STYLE.md` in the Nutcracker root before judging style/tests. Corpus layout, naming and golden rules live in `.agents/skills/manage-corpus-tests/SKILL.md`; subset doc rules in `.agents/skills/filling-subset-doc/SKILL.md`.

Deliver the report using [output-template.md](output-template.md).

## Trigger

When the user gives `https://github.com/ballerina-nutcracker/ballerina/pull/<N>` (or equivalent), run the full workflow below immediately. Do not ask whether to review.

## Workflow

Copy and track:

```
Review progress:
- [ ] 0. Mergeability gate — conflicts with its base? stop and report only the conflict
- [ ] 1. Fetch PR metadata + checkout
- [ ] 2. Initial understanding (fix / example .bal / impl summary) — write this first in the report
- [ ] 3. Commits / authors / trailers
- [ ] 4. Diff + design review (approach, root-cause design checks, security, agent failure modes, unnecessary / large comments)
- [ ] 5. Go validation + data races (static review and `-race`)
- [ ] 6. Unused / unneeded files, unused and test-only symbols, duplicate tests, test locations, skip-list entries (issue open + test still fails)
- [ ] 7. Subset doc updated for support / restriction / deviation changes
- [ ] 8. Codecov coverage gaps
- [ ] 9. Prior review overlap (skip duplicates)
- [ ] 10. jBallerina parity (if needed)
- [ ] 11. Write full report (template)
```

### 0. Mergeability gate

Before any review work, check that the PR merges cleanly into its base:

```bash
gh pr view "$PR" --repo ballerina-nutcracker/ballerina --json mergeable,mergeStateStatus,baseRefName,headRefOid
```

`mergeable` can be `UNKNOWN` right after a push; confirm locally with `git merge-tree --write-tree <base> <head>` (non-zero exit = conflict). For a stacked PR, check against its base branch, and also note if the stack conflicts with main.

If it conflicts: **stop**. Don't review, don't run tests, don't post findings or update an existing summary with new findings. The whole report (and, when posting, the only comment) is a short conflict note: the conflicting files, the base commit(s) it conflicts with, and "please rebase; full review once it merges cleanly". Re-run the full review after the author rebases.

```bash
PR=<N>
REPO=ballerina-nutcracker/ballerina
ROOT=$(git rev-parse --show-toplevel)

gh pr view "$PR" --repo "$REPO" --json title,body,author,baseRefName,headRefName,commits,files,url,labels,isDraft
gh pr diff "$PR" --repo "$REPO"
gh api "repos/$REPO/pulls/$PR/comments" --paginate
gh api "repos/$REPO/issues/$PR/comments" --paginate
gh api "repos/$REPO/pulls/$PR/reviews" --paginate
```

Skip the PR if it is a draft or carries a "don't merge" label.

Prefer reviewing in `$ROOT` (fetch PR branch with `gh pr checkout` into a worktree if the main tree is dirty). If the chat workspace is already a PR checkout of that repo, use it.

### 2. Initial understanding (do this before issue hunting)

After reading the PR title, body, and diff, produce the **Initial understanding** block first in the report (before verdict / findings). Required contents:

1. **What is the fix** — 2–4 sentences: problem being solved, user-visible / language / runtime effect, and why this change exists (link issue if present).
2. **Example Ballerina code** — a short, runnable-looking `.bal` snippet that shows the behavior this PR enables or fixes. Prefer:
   - A corpus test added/changed in the PR, trimmed to the essential lines, or
   - A minimal illustrative example derived from the diff
   - Label expected output / error / panic when relevant (`@output`, compile error, etc.)
3. **Implementation summary** — point form only (bullets), covering the main pipeline touchpoints, e.g.:
   - Which stages / packages changed (parser, AST, semantics, BIR, runtime, stdlib, …)
   - Key types / functions / control-flow changes
   - Tests added (corpus paths)
   - Notable non-goals or follow-ups called out in the PR

Do not skip this section for “small” PRs; shorten it instead.

For language server PRs (`ls/`), item 2 is an example LSP exchange instead of `.bal` code; see [ls-review.md](ls-review.md).

### 3. Commits / authors / trailers

For every non-merge commit on the PR:

1. **Conventional Commits** — `<type>(<optional scope>): <description>`; the validator is the source of truth for types, length and casing:
   - Run: `python3 "$ROOT/.github/scripts/validate_commits.py" "<subject>"`
   - Also validate the **PR title** the same way
2. **Atomic commits, no fixups** — each commit is one coherent change with its tests and docs. Flag any `fixup!` / `squash!` commit still on the PR (agent-authored fixups must be autosquashed before the PR; they must not land on `main`), and commits that mix unrelated changes
3. **No Co-authored-by** — fail any commit whose message contains `Co-authored-by:` (any co-author, including bots)
4. **No AI agent author** — flag if author/committer name or email matches AI tooling, e.g.:
   - `cursor`, `copilot`, `chatgpt`, `openai`, `anthropic`, `claude`, `gemini`, `devtools@`, `noreply` AI bots
   - Trailers like `Generated-by:`, `Assisted-by:`, `Signed-off-by: Cursor`, `Co-authored-by: Cursor`, `GPT`, `Claude`
   - Commit body claiming the change was generated by an AI agent
5. **Type matches behaviour** — a `refactor`/`perf`/`test` commit or PR title whose change alters accepted programs, diagnostics or runtime behaviour should be `fix`/`feat` (Nit; see item 7, #1201)

Report each violation with SHA + subject. When posting, commit, PR title and PR body problems (including a missing `Closes #N`) are PR-level findings (`"anchor": "pr"`), counted in the summary status line — never plain summary bullets, and never file comments on an unrelated file.

### 4. Diff + design review

**Base check, before any finding is posted:** confirm the problem is introduced by the PR. Run the repro, or read the code, on the base as well. If the same problem exists on main, it is pre-existing. Report it under pre-existing issues in the chat report, and suggest an issue if it is worth one. Don't post it as a PR finding, even when the PR moved, renamed, re-indented or restructured the code so that the lines show up in the diff.

For example, on #1187 the cross-build subtests already ran in parallel on main (each called `t.Parallel()`). Moving them under a parallel `TestBalCLI` wrapper didn't create the `rt/` build race, and the author correctly rejected the finding as out of scope.

Findings the PR does introduce are still worth raising even if the author may reject them. A Nit the author declines is resolved with a reply.

#### Root-cause design checks

Do these before hunting individual bugs. Each one turns a series of per-site findings into one design finding.

- **Workaround comments.** Read every comment the PR adds that explains why a case can't be handled the normal way ("can't be normalized because…", "kept here so that…", "unlike other X…"). Each one tells you about a constraint the rest of the change has to work around. Check that the constraint is real, then find every place that has to deal with it (see **Representation changes**). Example (#1188): `quotedWildcardIdentifier` said `'_` can't be normalized like other quoted identifiers because `_` is `model.IGNORE`. The constraint was real: a wildcard `var _ = 3` binds a symbol named `_`, so normalizing `'_` made `'_` resolve to it and switched off unused-variable and shadowing checks. The design finding was the consequence. Every site that turns a name into a key needed to strip the quote, there was no shared helper for it, and the sites the PR missed broke.
- **Representation changes.** When the PR changes what a field or value holds (a string format such as keeping a quote, a sentinel, a flag, a new variant), find every reader of it (`rg` the accessor, e.g. `GetValue\(\)|\.Value\b` for identifiers) and check each one. List the readers the PR updated and the ones it didn't; probe each unpatched reader with a `.bal` repro. Per-site fixes with no shared helper are a design finding naming the missed readers.
- **Repeated symptoms.** On a re-review, compare each new finding with the findings from earlier rounds (yours, other reviewers', CodeRabbit's, including its outside-diff items). If it belongs to the same bug class, don't post another instance. Post one **blocking** design finding naming the shared cause, every site found so far, and how to find the rest. #1188 had five rounds of `'_` per-site findings (enum member, object method, object field, error detail, included-record named argument) before anyone named the cause.
- **Scope widened by a finding.** When a finding (yours or another reviewer's) leads the author to accept a broader family of inputs than the issue covers (e.g. "the spec allows `'_`, accept it"), the next review checks the whole family the PR now claims to support, using the representation-change check above, not only the cases the author's tests cover.

**Validity gate for design findings.** A design finding is posted only if all of these hold. Otherwise it is downgraded to the per-site findings it rests on, or dropped:

1. **Concrete failures.** At least one site is reproduced as wrong behaviour with a `.bal` program on the PR head, and does not fail the same way on the base. A design finding with only hypothetical failures is a "consider" note in the chat report, not a posted finding.
2. **Shared cause.** Each listed site fails for the same reason; say what that reason is. A site that fails differently is its own finding.
3. **Fix checked against working cases.** The suggested direction must not break what already works. Prototype it locally (revert afterwards) and run the PR's corpus tests plus the controls. Example (#1188): stripping the quote from every named argument would break `g('_ = 1)` for a plain parameter named `'_`; only the included-record field lookup and its generated mapping key may normalize. If you can't prototype it, describe the constraint instead of prescribing a fix.
4. **Pre-existing check.** If the shared cause exists on the base (e.g. the wildcard sentinel), the finding asks the PR not to make it worse at the sites it adds; redesigning the base is a suggested issue, not a blocker.

Verify each design finding in a clean-context subagent that gets the claim, the repros and the code locations, but not your reasoning, and returns valid / false positive with evidence.

Review for:

- Correctness vs intended Ballerina semantics (compare to jBallerina source under `$JBALLERINA_SRC` when behavior is unclear)
- Fit with interpreter stages in `AGENTS.md` (parse → AST → symbols → types → semantic → CFG → desugar → BIR → interpret)
- PAL: platform interactions (io, http, fs) in compiler/interpreter execution go through PAL. PAL implementations and developer tooling may use platform APIs directly; don't flag those
- Symbols: never map-key `model.Symbol`; use `model.SymbolRef`; go through compiler context
- Dispatch on one discriminator (`AGENTS.md` review criteria): concrete type or semantic kind/tag. Flag a type switch whose fallback dispatches on kind/tag, and the converse. A type assertion inside an explicit tag case to reach that case's data is fine
- AST types: expressions get their type via `ast.SetType` / the `Ty` field, but inside the type resolver only `setNodeType` / `setTypeData`, so nothing is written during candidate trials. Non-expression, non-type-descriptor nodes have no type
- `doc/guides/CODING_STYLE.md`, in particular:
  - Public API surface not widened without need; unused helpers, superseded forwarders and single-implementation interfaces removed
  - Constructors initialize every field (maps to empty maps); no nil/zero checks that silently hide a broken invariant
  - `error` / `ok` results only where failure is possible; drop always-success signals and the dead checks at call sites
  - A new shared helper updates the existing callers that duplicate its logic
  - Each switch case's handling stays in that case; derived fields stored only with a documented reason
  - Every lint suppression has a comment explaining why
- License headers on new `.go` / `.bal` files
- Corpus tests preferred for behaviour reachable from Ballerina source (`AGENTS.md`); no tests or guards for states the compiler/runtime guarantees are impossible
- **Challenge every new Go unit test, even one with a "why not corpus" comment.** Don't take the comment's word for it. Sort each test case into one of these:
  1. Already covered by an existing corpus test: name the test and say the case is redundant.
  2. Unreachable from `.bal`, e.g. a `float64` infinity case for a langlib function whose parameter is `decimal`: say it is a dead input.
  3. Reachable: write the corpus program, run it, then mutation-test it by reverting the fix and checking that the output changes.
  4. Truly unobservable from Ballerina — infrastructure, failure injection, or an external interface contract (e.g. a `transform.Transformer` branch) that no corpus test can reach: only these justify the unit test.

  5. Covers only an exported helper the PR adds for a follow-up PR, with no caller yet: not a reason for a unit test. The consumer PR's corpus tests cover it; a Nit to drop the test (#1505, #1507). Don't also raise `t.Parallel()` on it.

  Report categories 1–3 as one Nit, "can be a corpus test", with the program you ran and the mutant's output.
  For "can't run to completion" (huge sleeps, waits, long loops), test what the guard prevents instead of the full run: `_ = start f(...)`, then a short `runtime:sleep` in `main`, then check a flag. The program exits when `main` returns, even with strands still sleeping (#664: `sleep(1e300)` returning immediately was caught this way).
- **Production defaults are tested.** For every tunable the PR adds with a non-zero default (debounce, timeouts, worker or queue limits, cache bounds), at least one test must run with the default. Tests that all override it (`WithDebounce(0)`) leave the shipped path untested: a Nit naming the default and the override every test uses.
- **Unnecessary / large comments** (see below)

- New Go tests call `t.Parallel()` unless they touch process-global state; report each one that doesn't as its own nit, even when another finding suggests deleting that test. Before raising one, read the test body and its helpers for `t.Setenv`/`os.Setenv`, `t.Chdir`/`os.Chdir`, process-wide counters (`testing.AllocsPerRun`, `runtime.ReadMemStats`, `runtime.NumGoroutine`), `os.Stdout`/`os.Stderr`/`os.Stdin` swaps, `flag` or `log` global setup, and package-level vars the test writes. Such a test stays serial; without a comment saying so, the Nit is "add `// Not parallel: <reason>`", not `t.Parallel()` (#954)
- `check_parallel` hits on pre-existing tests whose `func` line is outside the diff (the PR only edits their body) go in one optional summary item listing them, not one Nit per test (#1078). Tests the PR adds, or whose top-level lines it changes, still get a Nit each.
- Native stdlib externs: each `runtime.RegisterExternFunction` takes a named function, not an inline closure (a closure over `rt` becomes a named function returning `extern.NativeFunc`)
- Spec over jBallerina: before calling a jBallerina difference a bug, quote the spec rule for that exact construct; if the spec decides it, the PR following the spec is right
- Edge cases of any exception the PR adds: if it rejects/accepts values above a bound, also try below the other bound (e.g. a negative value where it only checked `> max`)
- Float range checks: `x < min || x > max` on a Ballerina `float` (config fields, langlib arguments) lets NaN through, since every comparison with NaN is false. Ask for `math.IsNaN` before the comparison, or a note on why NaN cannot reach it. Raise it even when jBallerina has the same check, as a Nit noting the shared gap (#1446: a NaN `failureThreshold` made a circuit breaker that never opens)
- Doc / README lines the PR changes: check every factual statement against the source declaration (record open vs closed, `readonly &`, `distinct`, signatures, defaults), not only the behaviour claims
- Process docs the PR edits (`.agents/skills/**`, CONTRIBUTING, templates): each new step instruction must also appear in that document's checklist, and vice versa
- On a re-review, any doc (`AGENTS.md`, README, skills) the new commits change gets the whole-file checks again, not only the changed lines: a rewrite can drop or keep a stale statement outside its hunks
  - Clean rebase/merge → build and run the tests, including the ones main added since the merge-base; a failure is a finding even though neither side breaks alone
  - Conflict → `git rebase --abort` / `git merge --abort`. Don't resolve it; the author owns the resolution. A conflict with the PR's own base stops the review (step 0). A conflict only with another open PR is a note in **PR summary** (files + PR), not a finding
- Stacked PRs (base branch isn't `main`; find the chain with `gh pr list --json number,baseRefName,headRefName`): review the stack as one unit at the top PR's head and put each finding on the PR whose commits added the line. Verify each finding in a separate subagent with a fresh context: it re-runs the repro at the top of the stack and reads the later PRs' diffs. A finding a later PR fixes is dropped (mention it in that PR's summary instead)
- Not this review's job: interactions with other open PRs outside the stack, or rehearsing a rebase onto `main`. CI and the merge queue catch those, and checking pairs grows with every open PR. A merge conflict with `main` is at most a one-line summary item

Separate **design/blocking** findings from **nits**.

Not findings:

- **Process-doc additions by maintainers.** A maintainer adding a review criterion or rule to `AGENTS.md` or `.agents/skills/**` alongside a feature is deliberate process work, not unrelated scope. Check that the text is accurate; don't ask for a separate PR (#978).
- **Deliberately conservative restrictions.** A rejection or unsupported path that a nearby code comment explains, and whose root cause is an open tracked issue, is a known limitation, not a defect, e.g. rejecting a worker reference in a join collection because joins are lowered per frame (#1047). Raise it only if the explanation is wrong, or if the restriction is user-visible and `doc/lang/subset10.md` doesn't mention it.
- **Spec-shaped code.** Code whose structure and variable names follow a spec algorithm or rule step by step is not a readability or simplification Nit, even if a shorter form exists (#1201). Raise it only if it deviates from the spec text.

#### Security

Check every change that touches untrusted input, the file system, the network, processes or credentials (CLI, `projects/` loading, PAL, stdlib natives, `ls/`):

- **Paths.** Package, import, `Ballerina.toml`/`Dependencies.toml` or archive entry names joined into file paths without cleaning: `..` traversal, absolute paths, symlinks out of the project or cache dir (zip-slip in `.bala` extraction).
- **Processes and shells.** `exec.Command` with user-controlled arguments through a shell, or flags injectable via a leading `-`.
- **Network and TLS.** Certificate verification disabled or skippable by default, plaintext fallback, missing timeouts, unbounded response or request bodies.
- **Untrusted input size.** Parsers and decoders (source, TOML, JSON, XML, YAML, CSV, protobuf, LSP messages) with unbounded recursion, allocation or loops a crafted input can trigger; a crash or hang there is Important.
- **Secrets.** Credentials, tokens or config secrets written to logs, error messages, traces or golden files.
- **Concurrency as a safety issue.** Races on shared runtime state that could corrupt values across strands (see Data races).
- **Defaults.** New stdlib options whose default is less safe than jBallerina's (e.g. accepting any host, world-readable files).

Each hit needs a concrete input that reaches it; an unreachable path is at most a Nit.

#### Where agent-written code goes wrong

LLM-written code fails in predictable ways that a local read of the diff misses. Check each:

- **Accrued duplication.** For each new helper, search the repo (`rg` the key operation, the package's existing helpers, `semtypes`) for one that already does the job. A duplicate of existing code is a Nit naming the existing function.
- **State explosion.** New hooks, callback or function-valued parameters, flags that change control flow, local error recovery, `recover`, fallbacks for states the types could rule out. Ask whether a type or an invariant would make the bad state unrepresentable instead.
- **Workaround comments.** A comment that justifies a workaround ("we do X here because Y doesn't support Z") is usually a bug to fix, and the next agent will copy the pattern. Raise the underlying problem, not the comment (see **Root-cause design checks**).
- **Data smuggled past accessors.** New AST fields or side tables used to pass data to a later stage instead of going through the stage's parameters, context or proper accessor.
- **Global performance claims.** Local perf reasoning is fine; claims about whole-program cost must be measured (`compiler-tools` benchmark, a scaled probe), never guessed.

Don't spend findings on what the linters already enforce (`make lint`: walkpurity, forbidigo no-panic and syntax-error sites, depguard allowlists, gochecknoglobals). When a finding could be caught by a deterministic check next time, list it as a lint candidate in the final message.

#### Consistency with surrounding code

Compare each new declaration and function with its neighbours in the same file and package. Raise a Nit where it breaks the local layout, for example:

- A package-level variable added to a `var (...)` block that otherwise holds only interface assertions (`_ I = &T{}`), or placed away from its only user, when the file declares such variables as standalone `var x = ...`
- A new variable, constant or helper that duplicates an existing one (check `semtypes` predefined types and the package's existing helpers first)
- Control flow that is harder to read than it needs to be, e.g. assigning a variable through an `if` only to return it where an early return reads directly

When a Nit names a pattern, search the rest of the diff and the touched file for the same pattern. Raise each hit in the diff as its own Nit. In the Nit's body, name pre-existing hits in the same file or package that should change with it (e.g. "`newXMLSequence` could reuse it for empty sequences"), so the author can fix them together.

#### Unnecessary / large comments

Per `doc/guides/CODING_STYLE.md`: do not add comments that narrate code or restate names and types; prefer extracting a named function. Function docs describe the contract (inputs, results, preconditions), not implementation details or cost notes. In the PR diff, flag:

- Long block comments or multi-paragraph explanations that restate obvious code
- Step-by-step / tutorial-style comments (AI-agent style narration)
- Oversized doc comments on unexported helpers or tests (`TestXxx` included) that only repeat the function name
- Commented-out code left in the PR
- Comments that belong in the PR description or a design doc, not in source

Allow brief non-obvious “why” comments, license headers, and corpus `@output` / `@error` / `@panic` markers.

Also allow a comment on a non-corpus unit test that justifies why it is a unit test rather than a corpus test (e.g. the scenario is unreachable from `.bal`). This is a deliberate signal to agents, not review rationale leaking into code — do not flag it as a comment. Still verify its claim case by case (see "Challenge every new Go unit test" above); a wrong justification is a finding.

Report each hit in **Coding issues & nits** (usually `nit`, or `blocking` if it buries real logic) and/or **Unnecessary comments** with file + line range and a short proposed GitHub comment (e.g. delete or shrink to one “why” line).

### 5. Go validation

Run what the change warrants (narrowest useful scope):

```bash
cd "$ROOT"
go test ./<affected>/...
go test -race ./<affected>/...   # CI runs make test-race; a race first hit by a new corpus test counts even in untouched code
# optional
golangci-lint run ./<affected>/...
go test ./corpus -run <relevant>   # when corpus touched
```

Record failures as blocking issues with command + excerpt.

#### Data races

`-race` only reports races the tests actually execute, so also read the diff for shared state that can be touched concurrently. Concurrency in this codebase comes from: files parsed in parallel, stages 5–9 running concurrently across modules (`AGENTS.md`), parallel tests (`t.Parallel()`, parallel corpus drivers), and at runtime strands (`start`, workers, listeners, PAL callbacks).

Flag, with the two concurrent paths named:

- New or changed package-level variables, caches and registries (including lazy init and `sync.Once` whose result is later mutated) written after startup
- Plain maps/slices shared across modules or strands without a lock (`sync.Map`, a mutex, or ownership by one goroutine); check-then-act sequences (lookup then insert) even when each step is locked
- Mutations of compiler-context, environment or type-env state from per-module stages, and of `values` (maps, lists, objects) from runtime code without the existing locking
- Swapping a global for the duration of a call (save / set / restore), e.g. debug flags or writers
- Test helpers that mutate process-global state (env vars, cwd, globals) in a test that calls `t.Parallel()`

For each suspect, try to reproduce: run the affected tests with `go test -race -count=5` (add `-tags debug` when the code is debug-only), or write a small corpus program that drives both paths (several modules, `start`/workers). A reproduced race is **blocking**; an unreproduced but plausible one is a finding with the interleaving spelled out. A race that already exists on main goes under pre-existing issues.

### 6. Unused / unneeded files

Flag:

- Dead code, unused exports, unreachable branches introduced or left by the PR
- Scratch / temp files (`_*.bal`, debug dumps, local notes)
- Duplicative corpus tests or goldens that add no coverage (see below)
- Files unrelated to the PR purpose
- Orphaned helpers only referenced from deleted call sites

Use static reading + `go test` / build; mention `staticcheck` unused findings when available.

**Unused and test-only symbols.** On every PR that adds Go code, run:

```bash
python3 .agents/skills/pr-review/scripts/check_unused_symbols.py <base>
```

It lists the funcs, methods, types, consts, vars and struct fields the PR adds that nothing references (`UNUSED`) or that only `_test.go` files reference (`TEST-ONLY`). Linters miss both: `unused` counts test callers as uses and never reports exported fields. Read each hit before posting, because matching is by name: a common name can be hidden by an unrelated use (a field `DocumentURI` matches the type `workspace.DocumentURI`), and a symbol the PR description reserves for a follow-up is not dead. A `TEST-ONLY` symbol is a Nit to delete it, or to move it into the test file when only tests need it. A `GENERATED` line is one Nit on the generator's filter, not one per symbol.

**Duplicate tests.** On every PR that adds corpus tests, language or standard library, run:

```bash
python3 .agents/skills/pr-review/scripts/check_duplicate_tests.py <base>   # ~1 s
```

It compares each new `.bal` under `corpus/bal`, `corpus/lib` and `corpus/project` with every existing one (and with the other new ones), ignoring the license header, comments, `@output`/`@error` markers and string contents.

- `EXACT` — the same program already exists: a nit to delete the new copy.
- `NEAR` — printed with the differing tokens. Report it only when the difference tests nothing new (renamed variables, other literals). A one-keyword variant that exercises a distinct case (e.g. `final` vs plain module variable) is intentional.

**Test locations** (per `manage-corpus-tests`):

- Language tests go in the highest-numbered `corpus/bal/subset<N>/` (currently `subset10`), in `<id>-<feature>/` for features or `<id>-bug/` for bug regressions — including regressions for features from earlier subsets. A new file in a released subset is a nit to move it (editing an existing one is fine).
- Multi-file / multi-module behaviour goes in `corpus/project/`; parser and compiler recovery from source errors in `corpus/recovery/` (`.txtar` with `ast` and `stderr` goldens, run by `TestRecovery`).
- Standard-library tests are `corpus/lib/subset<N>/<name>.bal` with their golden in `corpus/integration/lib/subset<N>/<name>.txtar` (currently `subset3`). The library subset is its own release track: don't infer it from the language subset, and a PR opening a new library subset needs the release decision called out.
- No leading zeros in numeric filename parts (`call2-v.bal`, not `call02-v.bal`).

**Skip lists.** When the PR adds, keeps or moves entries in `test_util/skip.go` (`UnsupportedTests`, `WASMUnsupportedTests`) or another test exclusion list, check every entry in the hunks it touches, not only the added lines (#1495):

1. The cited issue is open: `gh issue view N --repo ballerina-nutcracker/ballerina --json state,stateReason,comments`. An entry under a closed issue is **blocking**. Read the closing comment first: "not a bug, the tests are wrong" means the test must be rewritten (e.g. `-e` → `-v` with `@output`), not just un-skipped.
2. The skipped test still fails on the PR head: run it with `go run ./cli/cmd run <file>` and compare with its markers. A test that passes is **blocking**: remove the entry and add its goldens.
3. One finding per shared reason lists every affected entry, with one inline comment per file (e.g. all four tests skipped for the same closed issue).
4. A missing reason comment on a group is a Nit only after 1–2 pass; don't post it instead of checking them.

Re-run this check on every re-review, even when the skip list is unchanged: issues close between pushes.

**Golden drift.** Every changed golden must follow from the PR's change. Goldens for fixtures the PR didn't touch (unscoped `-update` run, non-deterministic ordering) are a nit to revert.

**Langlib coverage docs.** A PR touching `lib/langlibs/ballerina/**`, `model/opaque.go` or `doc/langlib/**` must keep the generated `doc/langlib/README.md`, the module READMEs and the repo-root coverage summary in sync: `python3 .github/scripts/langlib_coverage.py --check` (the `Lang Library Coverage` CI check). Hand edits to generated files are a finding.

**Generated-file headers.** Before flagging a hand edit to a file whose header says `Code generated ... DO NOT EDIT`, find its generator (`//go:generate`, Makefile targets, `scripts/`, `.github/scripts/`). If it exists, the hand edit is the finding. If it no longer exists in the repo, the edit is fine and the Nit is the stale header: golangci-lint and reviewers skip files with that header, so hand-maintained code there goes unlinted (#1536).

### 7. Subset doc update

Subset docs record which grammar rules are supported and any restrictions on, or deviations from, the spec. A compilation-pipeline change (stages 1–10) updates the highest-numbered `doc/lang/subset<N>.md` (currently `subset10.md`) in the same change only when it adds or removes support for a grammar rule, or adds, changes or removes a restriction or deviation. Released subsets are preserved unless the PR is explicitly revising them. Follow `filling-subset-doc`.

- Needs a doc check: new syntax/expression/statement support, a restriction lifted or added, a new or removed spec deviation, a new langlib member, a new method-call form, a new supported import
- No doc change needed: a bug fix that makes already supported syntax conform to the spec (e.g. unary `-` result typing per §6.22.1, #1098), even when it changes what is accepted or rejected; interpreter-only (stage 11) changes, pure refactors, perf, CI and tests-only PRs, and `ls/`-only PRs
- Classify by behaviour, not by the PR title or commit type. If `main` and head differ on whether a program compiles, or on its diagnostics (e.g. the PR's new `-v`/`-e` tests fail at `main`), decide whether the difference lifts or adds a restriction/deviation or only brings supported syntax to the spec, even when titled `refactor`/`perf`. When a title nit reclassifies the PR, re-run this check (#1201)
- A fix that leaves a remaining gap vs the spec (e.g. a check done at runtime instead of compile time, #1481) needs a restriction sub-bullet under the construct's grammar bullet; a fix that fully conforms needs none — never add bullets that just describe spec-conforming behaviour
- Check the doc diff covers it in the right place: the grammar list (with a sub-bullet only where the subset still restricts the spec), the `Import declarations` langlib list, and the method-call syntax list. Where the implementation now supports the full spec, restrictions are removed rather than each supported case listed; no new bullet repeats what an existing "only supports" restriction already excludes
- An intentional, permanent departure from the spec goes under **Spec deviations** (`Matching jBallerina` / `Deviations from jBallerina`), not as a subset restriction; a temporary limitation is the reverse
- Check lifted restrictions are removed from the doc, not left contradicting the new behavior
- Changed subset docs pass `python3 .github/scripts/check_doc_links.py doc/lang/subset<N>.md`
- Missing or stale doc entry → **blocking** finding anchored on the implementing file, with the exact bullet(s) to add

### 8. Codecov coverage gaps

Pull Codecov bot comments and check-run output:

```bash
gh api "repos/$REPO/issues/$PR/comments" --paginate --jq '.[] | select(.user.login|test("codecov";"i")) | {user:.user.login, body:.body}'
gh api "repos/$REPO/pulls/$PR/comments" --paginate --jq '.[] | select(.user.login|test("codecov";"i")) | {path,line,body}'
gh pr checks "$PR" --repo "$REPO"
```

From uncovered lines in **changed** files: propose concrete corpus tests, placed per **Test locations** (step 6).

An uncovered failure check after a call (`if !ok`, `if err != nil`) counts as an error path only if the callee can return that failure. Open the callee and find the return that produces it. If there is none (for example, its only return is `return x, true`), the check is dead code: report a Nit to remove it, rather than asking for a test. This does not apply to a type-assertion guard inside a general accessor that is documented for several kinds. Such a guard is not dead just because today's callers pass only one kind.

Present suggestions as **Option A** — one markdown table (no fenced code blocks inside cells). Each row must include:

- **File** and **Line(s)** for the uncovered Go code
- Short gap description + suggested corpus path (`*-v.bal` / `*-e.bal` / `*-p.bal`)
- A **one-line** real Ballerina snippet in the Snippet column (paste-ready; include `@output` / `@error` / `@panic` when useful)
- **Dedupe:** the same `file` + line range must appear in at most one row. If several gaps share one corpus file, use one row (or the same Suggested corpus name) with a short multi-call snippet that hits them together
- **False positives:** drop gaps already exercised by existing corpus, unreachable from `.bal` (e.g. XML lexer can’t produce PI content containing `?>`), or pure internal failure paths (`materialize`/`resolve`/`unreachable`)
- Skip gaps already covered by existing corpus tests; mirror nearby corpus style when possible
- Prefer verifying suspects with a quick local `go run ./cli/cmd run` (or compile-error check) before listing them


### 9. Prior review overlap

Collect every existing review comment — humans, CodeRabbit (`coderabbitai`), other bots and agents — from inline threads, review bodies and the PR conversation (step 1 commands). Review bodies matter: summary-level asks (e.g. a `-race` failure, "add a `-fe` test") have no reply thread showing whether they were addressed.

- A finding of yours that matches a prior concern on the same line or about the same code is **not reported as a new finding** and gets no proposed GitHub comment. List it under **Already raised** with who raised it and whether it is still open at the reviewed head (re-run its repro; "Fixed with <sha>" is a claim to check).
- A prior concern still open at head that you did not find yourself: confirm it and list it the same way.
- Fixed prior concerns: one line ("N prior concerns, M fixed at head").
- When the report is posted, don't echo other reviewers' concerns in the summary; the posting script adds the live count of unresolved CodeRabbit threads. List them only in the chat report, including CodeRabbit's "outside diff range" items, which appear only in its review body.
- For each prior concern, note whether this review would have found it on its own. One it would have missed is a skill gap: report it for the retrospective.

### 10. jBallerina parity (when needed)

Run when the PR changes language semantics, runtime behavior, stdlib, or error/panic line numbers — or when the user asks.

1. Identify a small `.bal` repro (from corpus or craft one). When the change accepts/rejects a family of inputs, probe every member — for iteration: list, map, string, xml, table, stream, `object:Iterable`, `1...3` / `1..<3` ranges, a union; for an identifier form (e.g. quoted `'_`): variable, parameter, named argument to a plain parameter and to an included-record field (`f(*R r)` and `new C(...)`), record field, mapping key and field access, mapping/error binding pattern, enum member, object field and method, error-constructor detail. A new error on a valid program is a regression even if it used to be unimplemented
2. Nutcracker: `go run ./cli/cmd run <file>`
3. jBallerina: `bal run <file>` (see also `.agents/skills/run-jballerina/SKILL.md`)
4. Compare stdout/stderr/exit; for errors/panics, compare **line numbers** (messages may differ)
4a. Where the two differ, decide which is right in a clean-context subagent that sees only the spec section and the repro (not the PR, not either output) and returns the expected behaviour with the rule it rests on. jBallerina is not the oracle

5. If implementation intent is unclear, read the matching jBallerina source under `$JBALLERINA_SRC` and note divergence

Skip heavy jBallerina runs for pure docs/CI/chore with no behavior change; state that you skipped and why.

For PRs under `ls/` (or `cli/cmd/langserver.go`), follow [ls-review.md](ls-review.md) instead of the `bal run` comparison above: LSP 3.18 conformance, `ls/AGENTS.md` layering, UTF-16 positions, generation/event-bus concurrency, fixture tests under `ls/corpus`, and parity with the jBallerina language server.

For PRs under `lib/stdlibs/`, also follow [stdlib-review.md](stdlib-review.md): walk the module's upstream spec section by section, compare the public API and native behaviour with `ballerina-platform/module-ballerina-<name>`, and check the compiler plugin rules. For `lib/stdlibs/ballerina/workflow/` (or PRs against `feat/workflow`), also follow [workflow-review.md](workflow-review.md).

### 11. Report

Follow [output-template.md](output-template.md) exactly. **Initial understanding** must be the first section. Keep proposed GitHub comments to **1–2 sentences**, actionable, file+line anchored.

## Additional resources

- [output-template.md](output-template.md) — required report shape
- [stdlib-review.md](stdlib-review.md) — **required for PRs touching `lib/stdlibs/`**: spec walk against `module-ballerina-<name>/docs/spec/spec.md`, public API and native behaviour vs the upstream sources, compiler plugin rules, port-specific checks
- [workflow-review.md](workflow-review.md) — **required for PRs touching `lib/stdlibs/ballerina/workflow/`** (on top of stdlib-review.md): engine strands and yielding, panic isolation, typed errors, `Duration` handling, workflow/activity binding, compile-time checks, Temporal mode, the #1477 task list
- [ls-review.md](ls-review.md) — **required for PRs touching `ls/`**: checklist adjustments, layering, protocol conformance, positions, concurrency and incremental compile, fixture tests, jBallerina LS parity
- [gh-commands.md](gh-commands.md) — extra `gh` snippets (Codecov / CodeRabbit filters)
