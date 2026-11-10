# Posting a review to a GitHub PR

Used by step 12 of `SKILL.md`. `scripts/post_review.py` does the posting; this
file says what to put in `findings.json` and how to write it.

## Where each thing goes

| Content | Posted as |
|---|---|
| Important / Verify tied to a changed line | inline comment on that line or range |
| Nit, including unnecessary, oversized or inaccurate new comments (not unit-test justification comments) | inline comment with a `suggestion` (empty string = delete the lines) |
| Concern about a whole changed file | file-level comment (`"anchor": "file"`) |
| Missing code (e.g. a test the fix needs) | inline on the changed line it belongs to, code in `code` |
| Commit type/message, PR title or body problems (e.g. missing `Closes #N`) | a finding with `"anchor": "pr"` (no `path`): counted in the status line and rendered with its badge in the summary — never a plain `summary.items` bullet, and never a file comment on an unrelated file |
| Missing subset doc or other code gap | a finding anchored on the implementing file/line (inline or `"anchor": "file"`) |
| Informational PR-wide notes only (merge conflicts, perf numbers, `Read line by line`) | `summary.items` |

Never posted: the INTENT.md finding, **Fixed during review**, Evidence, report
metadata, empty sections. They're reported in chat only.

The script checks every anchor against the PR diff before posting: a line
outside the diff becomes a file-level comment, a file outside the diff becomes a
summary item. Nothing is dropped.

Severity is marked with a colored badge and bold label — 🔴 **Important**,
🟡 **Verify**, 🔵 **Nit** — in both the inline header and the summary counts.
GitHub strips font colors from comments, so the badge carries the color. Every
agent comment starts with 🤖 (it is posted from the developer's account); the
tool name is not repeated in each comment.

## Writing rules

Developers skip long bot comments. Keep every comment short enough to read in
five seconds and act on without scrolling.

- **Title**: one line, ≤ 80 chars, names the problem, not the category
  (`` `next()` makes line 28 invalid ``, not "Test correctness issue").
- **Body**: ≤ 3 sentences, ≤ 400 chars. What is wrong, why, what to do. No
  restating the diff, no history of how you found it, no hedging.
- **Code**: every example is a real Ballerina block in `code`
  (`"lang": "ballerina"`), never inline in the body or a table cell. A
  reproducer with `outputs` is a complete runnable program — imports, `main`,
  and `// @output` / `// @error` / `// @panic` markers — so it can be pasted as a
  corpus test as is. A fix to existing lines goes in `suggestion` instead, so
  the author applies it with one click.
- **Outputs**: compiler output only, one line per compiler, trimmed to the
  lines that show the difference. They render collapsed.
- **Summary**: a `## 🤖 PR review summary · #N` heading, then one status line
  computed by the script — counts, fixed-since-last-run count and the reviewed
  commit (`1 Important · reviewed <sha>.`; `0 findings ✅ (2 fixed)` once
  everything is addressed). Optional
  `summary.checked` adds one line of what this review verified beyond CI and
  Codecov (≤ 4 entries, ≤ 40 chars each, e.g. `fails on main`, `jBallerina
  parity`, `uncovered branches traced`); leave it empty when there is nothing
  distinctive to say. Leave `summary.line` empty unless it says something
  the inline comments don't (e.g. on a clean PR: "Fix verified exhaustively.");
  never restate a finding. `summary.items` holds only PR-level notes with no
  line to attach to (merge conflicts, perf numbers, commit problems): at most
  5, ≤ 140 chars each. The script then adds `CodeRabbit: <n> of <m> threads
  unresolved.` whenever CodeRabbit opened review threads on the PR.

The dry run prints a warning for each rule a finding breaks. Fix them before
`--post`.

## `findings.json`

Never inside the repo checkout: keep it in a temp/scratch directory. Shape: see
`assets/findings.json`.

| Field | Meaning |
|---|---|
| `head_sha` | PR head the review ran on; posting refuses if the PR moved (`--allow-moved-head` when only `main` was merged in and the diff hash is unchanged) |
| `reviewed_diff`, `skill_version` | same values as the report frontmatter |
| `findings[].id` | stable slug, unique in the PR; reruns match comments by it |
| `severity` | `important`, `verify` or `nit` |
| `kind` | short pass name shown in the prefix (`Test`, `Correctness`, `Comment`, …) |
| `anchor` | `line` (default), `file` or `pr` |
| `path`, `line`, `start_line` | RIGHT-side lines in the PR head; `start_line` for a range |
| `code` | `{ "lang": "ballerina", "text": "…" }` or `null` |
| `outputs` | `{ "jBallerina": "…", "Nutcracker": "…" }` or `null` |
| `suggestion` | replacement text for `start_line..line`, `""` to delete, `null` for none |
| `summary.line` | optional sentence; only when it adds something the inline comments don't |
| `summary.items` | PR-level notes with no line to attach to. Never echo other reviewers' threads here; the script adds `CodeRabbit: <n> of <m> threads unresolved.` from the live thread state |
| `summary.checked` | optional short list rendered as `Checked: a ✔ · b ✔` |
| `answered` | ids of earlier findings dropped because the author answered them (declined with a reason, deferred to an issue or later PR, or resolved without a change); counted as "answered" instead of "fixed" in the status line. Keep ids from earlier rounds in the list |
| `stack` | stacked PRs only: paste `scripts/stack.py <N> --json`. Renders `Stack: #a → **#b** → #c · reviewed as a unit at <tip>`; each `fixed_later` entry (`pr`, `text`, optional old finding `id`) becomes a `✅ Fixed later in the stack by #m` item, and that old comment is resolved with the same reason. Omit for a standalone PR |

## Reruns

Run the review again, rewrite `findings.json`, dry-run, post. The script:

- edits an agent comment in place when its finding is still reported but the
  text changed, and leaves it alone when unchanged;
- replies "✅ No longer reported at `<sha>`" and resolves the thread when a
  finding is gone (e.g. the author fixed it);
- counts a gone finding as "withdrawn", not "fixed", in the summary when its
  thread has an agent reply starting "🤖 Withdrawn" (reply that way, by hand,
  when withdrawing a wrong finding, then drop it from `findings.json`);
- posts new findings in one new review;
- edits the one summary comment in place, replacing a legacy
  `# Review report — #N` comment the first time.
