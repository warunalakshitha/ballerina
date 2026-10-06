# Standard library PR review

Use this in addition to the main checklist when a PR adds or changes a module under `lib/stdlibs/ballerina/<name>/`. A Nutcracker stdlib is a port of jBallerina's `ballerina/<name>`. The source of truth is the module's spec. jBallerina's Ballerina and Java sources are the reference implementation.

## 1. Fetch the references

For `ballerina/<name>`, the upstream repo is `ballerina-platform/module-ballerina-<name>` (default branch usually `main`; check with `gh api repos/ballerina-platform/module-ballerina-<name> --jq .default_branch`). Pin the version that matches the jBallerina distribution used for parity, e.g. the tag of the version `bal` pulls from central, and say which one you used.

```bash
M=module-ballerina-<name>
gh api "repos/ballerina-platform/$M/git/trees/main?recursive=1" --jq '.tree[].path' \
  | grep -E '^docs/spec/spec.md$|^ballerina/.*\.bal$|^native/src/main/java/.*\.java$|^compiler-plugin/src/main/java/.*\.java$' | grep -vi test
gh api "repos/ballerina-platform/$M/contents/docs/spec/spec.md" --jq .content | base64 -d > $SP/<name>-spec.md
```

Fetch only the files a check needs. The spec, the public `.bal` files, and the Java class behind a native method are enough for most findings.

## 2. Spec walk (section by section)

Go through every section of `docs/spec/spec.md` and give each one a status:
- **Implemented:** the behaviour matches. Verify with a program, not by reading code.
- **Partial:** some parts are missing or behave differently. Name what.
- **Not supported:** absent.

Then cross-check the PR's package README coverage table and `doc/library/README.md`. Every Partial or Not-supported item must appear as Partially Supported or Not Supported, or under Notable Behavioural Changes. A row marked Supported that the spec walk found Partial is a finding (doc fact). Recompute the README counts and percentages.

## 3. Public API parity (`ballerina/*.bal`)

Compare the PR's `.bal` with upstream:
- types, records and their fields, open vs closed (`{| |}`), defaults;
- `distinct` error and service types;
- function and method signatures (parameter names matter for named arguments), return types, `isolated`, `remote` and `resource` qualifiers;
- enums, constants and annotations.

A missing or changed public symbol needs a README note, or it's a finding.

## 4. Behaviour vs the native implementation (`native/.../*.java`)

For each native method, read the Java class it maps to, e.g. `UdpClient.java` or `Listener.java`, for:
- error types and messages, and which error is returned versus panicked;
- default values and timeouts (`0` or negative meaning "no timeout");
- lifecycle: `start`, `gracefulStop`, `immediateStop`, restart after stop, double `close()`, attach and detach, and `start()` with no service;
- resource limits (buffer sizes, truncation), encodings and charsets, IPv6, and name resolution.

Confirm each difference with `bal run` (see the main skill's step 10) before raising it. Apply the main skill's Base check and spec-over-jBallerina rules.

**jBallerina bugs are fixed, not copied** (`add-stdlib-support` step 5). Where jBallerina contradicts its spec or API docs, or is clearly defective (data loss, races, silent overflow or truncation, unenforced limits, ignored inputs), the port implementing the correct behaviour is right, not a parity finding. Check instead that each such fix:

- is listed under the package README's **Notable Behavioural Changes** (and mirrored in `doc/library/README.md`) with a real link to an existing or filed issue in `ballerina-platform/ballerina-library` — a missing or placeholder link is a finding;
- has its corpus `@output` that differs from jBallerina cite that issue in a comment;
- isn't contradicted by a corpus test that still asserts the buggy jBallerina behaviour.

Conversely, a port that copies a jBallerina bug to keep outputs identical is a finding.

## 5. Compiler plugin (`compiler-plugin/.../*.java`)

Upstream compile-time rules, for example service validators for allowed remote methods, parameter types and return types, are part of the module contract. For each rule, check whether the port enforces it, at compile time or at attach or runtime, or documents that it doesn't. An invalid service that jBallerina rejects at compile time and the port accepts silently is a finding unless the README lists it.

## 6. Port-specific checks

- **PAL:** no direct `os`, `net`, `time` or `fmt.Fprint*(os.Stderr)` use. DNS resolution, dialing, listening, clocks and stderr go through `rt.Platform()`. Randomness via `crypto/rand` is fine, since PAL has no randomness interface.
- **Ballerina code on a native goroutine:** a panic must not crash the interpreter. This covers every `go func()` that calls `InvokeFunctionValue` / `InvokeFunction`: listener and service dispatch, engines that run user functions on their own strand, and callbacks. Recover around the invocation. Dispatch logs `error: <msg>` through PAL stderr and keeps serving, as http's `startHTTPServer`, udp's `dispatch.go` and file's listener do. An engine records the panic as the run's failure.
- **Blocking externs yield:** an extern that waits (a channel receive, `time.After`, `time.Sleep`, `sync.WaitGroup.Wait`, a socket read without a deadline loop) must not hold the strand's thread. Loop with `<-ctx.Yield()` between checks, as `lang.runtime` `sleep` does with `Platform.Time.MonotonicNow`. A bare wait can starve another strand that would unblock it (e.g. the strand that sends the data being waited on): **Important**.
- **Typed errors:** for each `error` subtype a public function documents (`distinct` or not), find the native path that produces it and check it builds that type. A test like `r is mod:NotFoundError` must hold. A plain `NewErrorWithMessage` where a subtype is documented is a finding per error type.
- **Externs:** named functions only. Types are built once in module init, not per call.
- **Tests:** anything that needs no network or OS fixture goes in the open library subset `corpus/lib/subset<N>` (currently `subset3`; golden in `corpus/integration/lib/subset<N>`). Real sockets, servers, chmod or links go in `corpus/extern` with `.bal` fixtures and `t.Parallel()`. Challenge each Go test case (main skill). A new package with no test at all is a finding unless the PR defers it to a tracked task (see deferrals below).
- **Docs:** a **new** package ships `lib/stdlibs/ballerina/<name>/0.0.1/go1.27/README.md` (support table + behavioural notes) and a row in the `doc/library/README.md` table with recomputed totals. For any package, the README, the `doc/library/README.md` section and totals, `doc/library/subset<N>.md`, and the repo-root `README.md` **Standard library coverage** summary (overall %, package count, totals, `**Supported packages:**` list) all agree.
- **Deferrals:** when the PR body or its parent issue's task list defers README, tests or compiler checks to a named later task or PR, that's a one-line summary note ("deferred to <task/issue>"), not a finding. Check the task exists. A deferral with no issue or task behind it is a finding.
- **Sibling ports:** when several ports land together (tcp, udp, ldap), a bug class found in one is worth checking in the others.

Module-specific companions: [workflow-review.md](workflow-review.md) for `ballerina/workflow`.

## 7. Report additions

In the report, add a **Spec walk** table (section → status → evidence) and a **Compiler plugin rules** table (rule → enforced / documented / missing). Findings follow the main template. A spec gap that the README documents is a summary note, not a finding.
