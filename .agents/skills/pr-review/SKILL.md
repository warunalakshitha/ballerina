---
name: pr-review
description: >-
  Reviews Ballerina Nutcracker PRs (ballerina-nutcracker/ballerina). Starts with
  what the fix is, example Ballerina code, and a point-form implementation summary,
  then Conventional Commits, no Co-authored-by / AI authors, Go quality, unused
  code, Codecov gaps, skips concerns already raised by humans/CodeRabbit/bots,
  optional jBallerina parity against a local ballerina-lang clone. Use when the
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

Repo rules: read `AGENTS.md` and `CONTRIBUTING.md` in the Nutcracker root before judging style/tests.

Deliver the report using [output-template.md](output-template.md).

## Trigger

When the user gives `https://github.com/ballerina-nutcracker/ballerina/pull/<N>` (or equivalent), run the full workflow below immediately. Do not ask whether to review.

## Workflow

Copy and track:

```
Review progress:
- [ ] 1. Fetch PR metadata + checkout
- [ ] 2. Initial understanding (fix / example .bal / impl summary) — write this first in the report
- [ ] 3. Commits / authors / trailers
- [ ] 4. Diff + design review (incl. unnecessary / large comments)
- [ ] 5. Go validation
- [ ] 6. Unused / unneeded files, duplicate tests, test locations
- [ ] 7. Subset doc updated for new features / improvements
- [ ] 8. Codecov coverage gaps
- [ ] 9. Prior review overlap (skip duplicates)
- [ ] 10. jBallerina parity (if needed)
- [ ] 11. Write full report (template)
```

### 1. Fetch PR metadata + checkout

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

### 3. Commits / authors / trailers

For every non-merge commit on the PR:

1. **Conventional Commits** — subject must match repo validator:
   - Format: `<type>(<optional scope>): <description>`
   - Types: `feat`, `fix`, `build`, `chore`, `ci`, `docs`, `style`, `refactor`, `perf`, `test`, `revert`
   - Description starts with lowercase; subject ≤ 72 chars
   - Run: `python3 "$ROOT/.github/scripts/validate_commits.py" "<subject>"`
   - Also validate the **PR title** the same way
2. **No Co-authored-by** — fail any commit whose message contains `Co-authored-by:` (any co-author, including bots)
3. **No AI agent author** — flag if author/committer name or email matches AI tooling, e.g.:
   - `cursor`, `copilot`, `chatgpt`, `openai`, `anthropic`, `claude`, `gemini`, `devtools@`, `noreply` AI bots
   - Trailers like `Generated-by:`, `Assisted-by:`, `Signed-off-by: Cursor`, `Co-authored-by: Cursor`, `GPT`, `Claude`
   - Commit body claiming the change was generated by an AI agent

Report each violation with SHA + subject.

### 4. Diff + design review

Review for:

- Correctness vs intended Ballerina semantics (compare to jBallerina source under `$JBALLERINA_SRC` when behavior is unclear)
- Fit with interpreter stages in `AGENTS.md` (parse → AST → symbols → types → semantic → CFG → desugar → BIR → interpret)
- PAL: no direct platform I/O outside PAL
- Symbols: never map-key `model.Symbol`; use `model.SymbolRef`; go through compiler context
- Public API surface not widened without need
- License headers on new `.go` / `.bal` files
- Corpus tests preferred over unit tests for pipeline behavior (`AGENTS.md`)
- **Unnecessary / large comments** (see below)

- New Go tests call `t.Parallel()` (unless they touch process-global state such as env vars or cwd); report each one that doesn't as its own nit, even when another finding suggests deleting that test
- Native stdlib externs: each `runtime.RegisterExternFunction` takes a named function, not an inline closure (a closure over `rt` becomes a named function returning `extern.NativeFunc`)
- Spec over jBallerina: before calling a jBallerina difference a bug, quote the spec rule for that exact construct; if the spec decides it, the PR following the spec is right
- Edge cases of any exception the PR adds: if it rejects/accepts values above a bound, also try below the other bound (e.g. a negative value where it only checked `> max`)
- Doc / README lines the PR changes: check every factual statement against the source declaration (record open vs closed, `readonly &`, `distinct`, signatures, defaults), not only the behaviour claims
- Process docs the PR edits (`.agents/skills/**`, CONTRIBUTING, templates): each new step instruction must also appear in that document's checklist, and vice versa
- Merge interplay: rebase the PR onto current main locally (and, if it uses an API another open PR redefines, merge that PR in too):
  - Clean rebase/merge → build and run the tests, including the ones main added since the merge-base; a failure is a finding even though neither side breaks alone
  - Conflict → `git rebase --abort` / `git merge --abort`. Don't resolve it and don't report bugs that depend on how it would be resolved; the author owns the resolution. Only note in **PR summary** that it conflicts with main (files + the main commit) and needs a rebase
- Stacked PRs (base branch isn't `main`): review the stack as one unit at the top PR's head, put each finding on the PR whose commits added the line, and drop a finding that a later PR in the stack fixes (mention it in that PR's summary instead)

Separate **design/blocking** findings from **nits**.

#### Unnecessary / large comments

Per `AGENTS.md`: do not add comments that narrate each line; prefer extracting a named function. In the PR diff, flag:

- Long block comments or multi-paragraph explanations that restate obvious code
- Step-by-step / tutorial-style comments (AI-agent style narration)
- Oversized doc comments on unexported helpers that only repeat the function name
- Commented-out code left in the PR
- Comments that belong in the PR description or a design doc, not in source

Allow brief non-obvious “why” comments, license headers, and corpus `@output` / `@error` / `@panic` markers.

Also allow a comment on a non-corpus unit test that justifies why it is a unit test rather than a corpus test (e.g. the scenario is unreachable from `.bal`). This is a deliberate signal to agents, not review rationale leaking into code — do not flag it.

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

### 6. Unused / unneeded files

Flag:

- Dead code, unused exports, unreachable branches introduced or left by the PR
- Scratch / temp files (`_*.bal`, debug dumps, local notes)
- Duplicative corpus tests or goldens that add no coverage (see below)
- Files unrelated to the PR purpose
- Orphaned helpers only referenced from deleted call sites

Use static reading + `go test` / build; mention `staticcheck` unused findings when available.

**Duplicate tests.** On every PR that adds corpus tests, language or standard library, run:

```bash
python3 .agents/skills/pr-review/scripts/check_duplicate_tests.py <base>   # ~1 s
```

It compares each new `.bal` under `corpus/bal`, `corpus/lib` and `corpus/project` with every existing one (and with the other new ones), ignoring the license header, comments, `@output`/`@error` markers and string contents.

- `EXACT` — the same program already exists: a nit to delete the new copy.
- `NEAR` — printed with the differing tokens. Report it only when the difference tests nothing new (renamed variables, other literals). A one-keyword variant that exercises a distinct case (e.g. `final` vs plain module variable) is intentional.

**Test locations.** New language tests go in the open subset, `corpus/bal/subset10/10-<area>/`; subsets 1–9 are released, so a new file there is a nit to move it (editing an existing one is fine). New standard-library tests are `corpus/lib/subset3/<name>.bal` with their golden in `corpus/integration/lib/subset3/<name>.txtar`.

### 7. Subset doc update

A PR that adds a language feature, lifts a restriction, or adds/extends a langlib function must also update the subset doc of the open subset: `doc/lang/subset10.md` (the subset new corpus tests go in; moves to the next number once subset10 is released).

- Decide from the diff whether the change is user-visible: new syntax/expression/statement support, a restriction removed, a new langlib member, a new method-call form, a new supported import. Pure refactors, perf, bug fixes to already-documented behavior, CI and tests-only PRs need no doc change
- If it is user-visible, check the doc diff covers it in the right place: the grammar list (with a sub-bullet only where the subset still restricts the spec), the `Import declarations` langlib list, and the method-call syntax list
- Check lifted restrictions are removed from the doc, not left contradicting the new behavior
- Missing or stale doc entry → **blocking** finding anchored on the implementing file, with the exact bullet(s) to add to `doc/lang/subset10.md`

### 8. Codecov coverage gaps

Pull Codecov bot comments and check-run output:

```bash
gh api "repos/$REPO/issues/$PR/comments" --paginate --jq '.[] | select(.user.login|test("codecov";"i")) | {user:.user.login, body:.body}'
gh api "repos/$REPO/pulls/$PR/comments" --paginate --jq '.[] | select(.user.login|test("codecov";"i")) | {path,line,body}'
gh pr checks "$PR" --repo "$REPO"
```

From uncovered lines in **changed** files: propose concrete corpus tests. Prefer `corpus/bal/...` patterns from `AGENTS.md`.

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
- When the report is posted, every concern someone else raised that is still open at head gets one summary line, `Still open (raised by <login>): <what>` (login without `@`), so the summary doesn't read as if it was missed.

### 10. jBallerina parity (when needed)

Run when the PR changes language semantics, runtime behavior, stdlib, or error/panic line numbers — or when the user asks.

1. Identify a small `.bal` repro (from corpus or craft one). When the change accepts/rejects a family of inputs, probe every member — for iteration: list, map, string, xml, table, stream, `object:Iterable`, `1...3` / `1..<3` ranges, a union. A new error on a valid program is a regression even if it used to be unimplemented
2. Nutcracker: `go run ./cli/cmd run <file>`
3. jBallerina: `bal run <file>` (see also `.agents/skills/run-jballerina/SKILL.md`)
4. Compare stdout/stderr/exit; for errors/panics, compare **line numbers** (messages may differ)
5. If implementation intent is unclear, read the matching jBallerina source under `$JBALLERINA_SRC` and note divergence

Skip heavy jBallerina runs for pure docs/CI/chore with no behavior change; state that you skipped and why.

### 11. Report

Follow [output-template.md](output-template.md) exactly. **Initial understanding** must be the first section. Keep proposed GitHub comments to **1–2 sentences**, actionable, file+line anchored.

## Additional resources

- [output-template.md](output-template.md) — required report shape
- [gh-commands.md](gh-commands.md) — extra `gh` snippets (Codecov / CodeRabbit filters)
