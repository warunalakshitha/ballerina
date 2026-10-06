# Nutcracker PR review report template

Use this structure in the chat reply. Do not post to GitHub unless asked.

**Order matters:** start with **Initial understanding**, then metadata/verdict, then findings.

## Initial understanding

### What is the fix

2–4 sentences: the problem, what the PR changes for users/language/runtime, and why (link linked issue if any).

### Example Ballerina code

Minimal `.bal` that demonstrates the fixed or new behavior (from the PR’s corpus test when possible). Include expected result in a short note after the snippet.

```ballerina
// illustrative example
```

Expected: …

### Implementation summary

- Point 1 (package / stage / key change)
- Point 2
- Point 3
- Tests: `corpus/...` (if any)
- Non-goals / follow-ups (if any)

---

## Verdict

One line: **Approve** / **Request changes** / **Comment only**, plus the main reason.

## PR summary

- **PR:** [#N — title](url)
- **Author:** @login
- **Scope:** N commits, N files (+X / −Y)
- **Base ← head:** `base` ← `head`

## Commit / authorship checks

| SHA | Subject | Conventional | Co-authored-by | AI author | Notes |
|-----|---------|--------------|----------------|-----------|-------|
| abc1234 | `fix(ast): …` | pass/fail | none/FOUND | pass/flag | … |

Also state PR title validation: pass/fail.

## Design / implementation

Bullet list of blocking or important design issues. Empty section → write `None`.

## Coding issues & nits

| Severity | File | Line | Issue | Proposed GitHub comment |
|----------|------|------|-------|-------------------------|
| blocking / nit | `path/to/file.go` | 123 | Short issue | 1–2 sentence comment to paste |

Severity guide: `blocking` = must fix; `nit` = optional polish. Only concerns nobody has raised yet go here; see **Already raised**.

## Already raised

Concerns someone else (human, CodeRabbit, other bot/agent) already raised that are still open at the reviewed head. No proposed comment — don't re-post.

| Raised by | File | Line | Concern | Status at head |
|-----------|------|------|---------|----------------|
| @reviewer (review body) | `semtypes/env.go` | 113 | `-race` fails on new corpus test | still open — reproduced |

Then one line: `N prior concerns, M fixed at head`. Empty → `None`.

## Subset doc

Does the PR need a `doc/lang/subset10.md` update (new feature, lifted restriction, new langlib/method-call support)? State `Not needed: <reason>`, `Updated: <what>` or `Missing: <bullets to add>` (missing → also a blocking row in Coding issues).

## Unused / unneeded

List files or symbols to remove. Empty → `None`.

## Unnecessary / large comments

| File | Line(s) | Problem | Proposed GitHub comment |
|------|---------|---------|-------------------------|
| `path.go` | 80–95 | Long comment narrates obvious logic | Please drop this block (or keep one short “why” line); prefer a named helper per AGENTS.md. |

Empty → `None`.

## Codecov / test suggestions

Use **Option A**: one markdown table with **file + line(s)**, gap, suggested corpus path, and a **one-line** real Ballerina snippet in the cell (no fenced code blocks inside the table — they break GitHub/markdown tables). Prefer `corpus/bal/...` paths.

Rules: (1) same file+lines at most once; (2) one shared corpus/snippet when it covers several gaps; (3) drop false positives (already covered, unreachable from `.bal`, internal-only paths).

| File | Line(s) | Gap | Suggested corpus | Snippet |
|------|---------|-----|------------------|---------|
| `path.go` | 40–52 | uncovered branch | `corpus/bal/.../foo-e.bal` | `xml _ = xml:get(1, 0); // @error` |

Empty → `None` (or “Codecov comments not present yet”).


## jBallerina parity

What was run (`bal run` / source compare), results, divergences. Or `Skipped: <reason>`.

## Go validation commands

Commands run and pass/fail summary.

## Suggested next actions for reviewer

Short checklist (e.g. post only non-overlapping comments, ask author to drop Co-authored-by, add corpus test X).
