# Workflow PR review

Use this in addition to the main checklist and [stdlib-review.md](stdlib-review.md) when a PR changes `lib/stdlibs/ballerina/workflow/`, the workflow compile-time checks, or the `balrt-workflow` runtime stub. These PRs usually target the `feat/workflow` branch, one task at a time.

The upstream module is `ballerina-platform/module-ballerina-workflow`. Its spec is `docs/spec/README.md`, not `spec.md`. The compiler plugin lives in `compiler-plugin/.../workflow/compiler/*Task.java`, and the Temporal-backed natives in `native/src/main/java/io/ballerina/lib/workflow/`. The design and task list are on the parent issue (#1477).

## 1. Scope against the task list

Read the parent issue's task list and its "known limitations" comments before raising anything about missing pieces.

- A piece a later task owns (README/support table, corpus tests, compile-time checks, `LOCAL`/Temporal mode, `balrt-workflow`, `configurable` config) is a one-line summary note ("deferred to <task>"), not a finding.
- A deviation from the jBallerina module that is listed on the issue or in the PR body is not a finding. One that is listed nowhere is.
- A declared extern the engine doesn't support must still be registered, and its stub's result must fit the declared return type. For `T|error` a plain error works. For `T|HumanTaskError` it must be one of the named error types. A dependently-typed `returns T` (e.g. `Context.await`) must not get an error back when the caller's `T` excludes `error`: panic with a clear message, or narrow the declaration. A call must never reach the runtime's "extern not found" path.

## 2. Engine: strands, blocking and panics

The in-memory engine runs each workflow on its own strand (`rt.AcquirePooledContext` in a goroutine). Activities run as direct calls on the workflow's strand.

- **No bare waits on a strand thread.** `waitForResult`, `ctx.sleep`, `await`, event futures, and anything that selects on `inst.done` or `time.After` loop on `<-ctx.Yield()` with a PAL clock deadline (`ctx.Env.Platform.Time.MonotonicNow()`, as `lang.runtime` `sleep` does). A bare wait can starve the strand that would call `sendData`, which hangs the program: **Important**. Probe it with a `start`ed waiter and a `main` that sends the data afterwards.
- **No `time.Sleep` / `time.After` / `time.Now`.** Time goes through PAL.
- **Panic isolation.** A Ballerina panic in the workflow or an activity must not crash the interpreter. The engine goroutine recovers around `InvokeFunctionValue`, marks the instance FAILED, and stores the error so reads return `InstanceFailedError`. Probe this with a workflow that panics and a `main` that then calls `getStatus` / `getResult`.
- **Activity failure parity.** jBallerina runs activities under `catch (Exception e)` and turns a panic into an activity failure that `callActivity` returns as an error to the workflow. Check that the port does the same and that the workflow can handle it, rather than the panic unwinding the workflow.
- **Instance state.** The instances map and per-instance fields (`result`, `events`, status) are shared between the engine goroutine, `sendData` callers and readers. Check that each access is locked, or ordered by closing `done` (write before `close`, read only after `<-done`). Run `-race` on a program with two concurrent instances.

## 3. Typed errors

`functions.bal` and `types.bal` document specific error types. For each public function, map every documented error to the native path that must produce it:

| Situation | Expected type |
|-----------|---------------|
| unknown instance id (`getStatus`, `getResult`, `waitForResult`, `sendData`) | `InstanceNotFoundError` |
| instance still running (`getResult`, `waitForResult` timeout) | `WorkflowInProgressError` |
| instance closed with an error or panic | `InstanceFailedError` |
| `runWithId` with a duplicate id, per `ifRunning` / `ifClosed` | the policy's documented error |

A plain `NewErrorWithMessage` where a type is documented is a finding, raised once per error type at the line that builds it. Verify each one with an `r is workflow:<Type>` program.

## 4. Inputs: `Duration`, data, and binding

- **`Duration`:** the fields are plain `int`s plus a `decimal` `seconds`. Negative values must not turn into an unbounded wait: clamp them to 0 so the timeout expires at once. `years`/`months` have no fixed length, so return an error for them. `()` alone means "no bound". Sum every field (`weeks`, `days`, `hours`, `minutes`, `seconds`) in both `ctx.sleep` and `waitForResult`.
- **Workflow parameter binding:** only `workflow:Context` gets the context object. Match it by the module's `Context` type, not by "is any object". The events record is a record of `future<T>` fields, and every other parameter is the input, converted with `CloneWithType`. An unrelated object parameter must be rejected, not silently given a `Context`.
- **`sendData`:** convert the payload to the event future's constraint (`FutureEventualType`) before completing the future, and return the conversion error to the caller. Check what happens on a second `sendData` to the same event, and on one sent after the instance closed.
- **`callActivity`:** named args bind to the activity's parameters by name. A missing required param and an unknown key are errors. Defaultable params are a documented limitation until `extern.FunctionSignature` carries defaults. Convert the result to the `typedesc` the caller passes.

## 5. Compile-time checks (when the PR adds them)

The upstream plugin's tasks define the contract. Compile-time checks are built into the compiler, not a plugin mechanism (#1477), and run in the semantic stages. For each rule the PR claims, add an `-e.bal` corpus test with `@error` markers and check the jBallerina diagnostic line with `bal build`:

- `ProcessFunctionAnalysisTask` / `WorkflowValidatorTask`: the `@Workflow` function shape (parameter kinds and order, `Context`, the events record of futures, return type) and the `@Activity` function shape
- `RunCallValidatorTask`, `SendDataValidatorTask`, `ResultReadValidatorTask`: call sites of `run`, `sendData`, `getResult`/`waitForResult` (function is a `@Workflow`, data name exists on the events record, payload and typedesc types fit)
- `ChildWorkflowCallValidatorTask`, `DurableAgent*Task`: child workflow and durable agent calls
- `CallSiteInjector` / `WorkflowCodeModifier`: step-id injection. Check that the injected id is stable across recompiles of unchanged source.
- `DisplayAnnotationValidatorTask`, `ConnectionVariableAnalysisTask`: annotations and connection variables used in workflow code

A rule the PR claims but that has no `-e` test is a finding. A rule it doesn't claim is a deferral note (section 1).

## 6. Temporal / `LOCAL` mode (when the PR adds it)

- Fallback: with no server reachable at the configured address, the runtime uses the in-memory engine, as #1477 describes. The probe goes through PAL networking and has a timeout.
- Determinism: workflow code replays, so `ctx.sleep`, time, randomness and activity calls go through Temporal APIs. A direct Go clock or a random value inside workflow execution is a finding.
- `balrt-workflow` is selected only when package resolution contains `ballerina/workflow`, and `bal`/`balrt` don't link the Temporal SDK (check with `go list -deps`). This is size-sensitive.
- The `js/wasm` build still compiles (the Playground runs the in-memory engine).

## 7. Tests

Standard library rules apply (`corpus/lib/subset3/` + `corpus/integration/lib/subset3/` goldens). Workflow programs end when `main` returns, so a test drives the instance to completion with `waitForResult` (bounded) before printing. The scenarios worth covering are: activity + data event, two concurrent instances, a timeout, a panicking workflow, an unknown id, and each typed error from section 3.

## 8. Report additions

Add a **Task scope** line (the parent issue's task this PR implements, and what it defers), and a **Typed errors** table (situation → expected type → produced type → evidence). When the PR adds checks, also add a **Compile-time rules** table (rule → enforced / deferred / missing).
