# Review retrospective (coordinator, after each review round)

The review skill improves only from its own misses. After a round's reviews are posted, collect what went wrong, turn each into a general rule or a lint, and prove the rule on a clean context before it lands.

## 1. Collect misses

From the PRs reviewed in the round (and replies since the previous round):

- **Missed:** a concern a human or bot raised on code our review saw, that our review didn't find (agents report these under "other reviewers' threads"; also read human review comments added after our post).
- **Wrong:** a finding of ours the author refuted with reasoning we accept, or that we withdrew.
- **Wasted:** a finding on code that other reviewers then had removed, or a nit class the user keeps dismissing (e.g. `t.Parallel()` nits on unit tests later deleted in #1505/#1507).
- **Recurring:** the same finding on two or more PRs. Prefer a lint for these.

Skip one-offs that depend on knowledge no rule can encode.

## 2. Propose a fix

For each miss, fork a subagent with the PR, the miss and the current skill files. It proposes the smallest general change:

1. A lint or script check when the problem is deterministic (golangci config, `forbidigo`/`depguard` rule, a check in `pr-review/scripts/`).
2. Otherwise one or two lines in `pr-review/SKILL.md` (or its companion checklists) or `agent-instructions.md`, placed in the step that should have caught it.

Don't add a rule that duplicates an existing one; sharpen that one instead. Instruction count costs adherence, so remove or merge a line for each one added where possible.

A second subagent checks the proposal for test-case leakage: it must not name the PR's files, functions or test values. A rule that only works because it describes the answer is rejected.

## 3. Prove it

Don't edit the skill files yet. Run 3 independent clean-context review agents on the PR at the head where the miss happened, each given the standard prompt plus the candidate rule as extra text. Keep the rule only if all 3 catch the miss. Also run it once on a PR from the round that was clean, to check it adds no false positive.

If it fails, revise and repeat; give up after 3 revisions and note the miss as unencoded.

## 4. Land it

Show the user each proven change (the miss, the rule, the 3/3 result). Apply only what they approve, to the skill files in place. Never commit; the user commits.

## Bugs found on main

This machine reviews PRs; bug hunting on main is a separate job (Heshan's nightly bug hunter). File only bugs a review came across incidentally, and never start agents or probes just to look for more.

Agents report such pre-existing bugs with a repro, its output on main, the expected behaviour with its spec rule, and a duplicate search. For each:

1. Re-run the repro on current main once (no load tests, long race runs or extra exploration).
2. Search open and closed issues again (`gh issue list --repo ballerina-nutcracker/ballerina --state all --search "<key words>"`). A duplicate gets a comment with the new repro instead of a new issue, only if it adds a case.
3. Otherwise file it: a one-line title, the repro as a corpus-style program with `// @output` / `// @error` markers, actual vs expected, the spec section, and the PR review it came from. Label `triage` and `Type/Bug`, so the morning triage job picks it up.
4. Report the filed issue numbers in the round's summary to the user.
