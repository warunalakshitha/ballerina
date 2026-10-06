# Extra GitHub query helpers

Repo: `ballerina-nutcracker/ballerina`

## All review threads (issue + review comments)

```bash
PR=<N>
REPO=ballerina-nutcracker/ballerina

gh api "repos/$REPO/pulls/$PR/comments" --paginate \
  --jq '.[] | {user:.user.login, path, line, original_line, body:.body[0:240]}'

gh api "repos/$REPO/issues/$PR/comments" --paginate \
  --jq '.[] | {user:.user.login, body:.body[0:400]}'
```

## CodeRabbit only

```bash
gh api "repos/$REPO/pulls/$PR/comments" --paginate \
  --jq '.[] | select(.user.login|test("coderabbit";"i")) | {path,line,body}'

gh api "repos/$REPO/issues/$PR/comments" --paginate \
  --jq '.[] | select(.user.login|test("coderabbit";"i")) | .body'
```

## Codecov only

```bash
gh api "repos/$REPO/pulls/$PR/comments" --paginate \
  --jq '.[] | select(.user.login|test("codecov";"i")) | {path,line,body}'

gh api "repos/$REPO/issues/$PR/comments" --paginate \
  --jq '.[] | select(.user.login|test("codecov";"i")) | .body'
```

## Commits with full messages (trailers)

```bash
gh api "repos/$REPO/pulls/$PR/commits" --paginate \
  --jq '.[] | {sha:.sha[0:7], author:.commit.author.name, email:.commit.author.email, message:.commit.message}'
```

## Checkout into a disposable worktree

```bash
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
git fetch "https://github.com/$REPO" pull/$PR/head:pr-$PR  # origin may be a fork
git worktree add "/tmp/ballerina-pr$PR" pr-$PR
```
