# Asynchronous desktop runtime

Native engine flows return lazy, move-only `vstd::task<T>` values. Creating a
task does not execute its body. Spawn it through `CGameContext::spawnTask`
to start inline and capture the main-loop scheduler, or `co_await` it from an
existing task to inherit that task's scheduler and cancellation. Own parameters
and callable captures across suspension; a lazy task must never depend on a
temporary coroutine lambda's capture object.

`task_handle<T>` is copyable and supports multiple readers and awaiters for
`void` and copyable values. `ready()` and `get()` describe result settlement.
`finished()`, execution joins, and group completion additionally require the
coroutine body and frame destruction to finish. Cancellation can settle a
result before execution finishes; teardown must wait for execution completion.
`whenAll` retains input order and, after failure, cancels and drains remaining
children before propagating the error.

Use `vstd::post`, `work`, `sleepFor`, `until`, and `nextFrame` for suspension.
Posted work keeps queue snapshot ordering; conditions, timers, and frames retain
their established phases. Continuations resume through the captured scheduler.
Scheduler rejection is an error. One-shot owned callbacks use
`std::move_only_function<void()>`; reusable observers retain owning captures.

Synchronous Python entry points retain their existing names and return types.
Only these boundaries call `game_async::wait` or `run` and pump the main loop.
Normal modal boundaries drive frames; the synchronous map-turn boundary uses
`WaitMode::PostedWork` to avoid recursive rendering. Blocking boundary sleeps
release the GIL. Native coroutine callers await asynchronous APIs directly.

Gameplay uses `controlAsync`, `findNextStepAsync`, and `CMap::moveAsync`.
Controller plans start together, then the main thread commits in actor order
after checking origin, identity, map, and transition generation. GUI movement
uses bounded loops that await turns. Deferred signals and refreshes remain
batched, and queued work cancelled before execution skips its body.

Every game context owns its tasks. Shutdown marks it inactive, advances its
transition generation, rejects new work, disconnects observers, and requests
cooperative cancellation. Running work finishes or observes its stop token.
Shutdown from a task, including a task beneath a synchronous nested boundary,
defers final teardown rather than joining itself. Independent teardown state
retains GUI, maps, providers, and scripting owners until execution finishes;
Python and Lua state are released afterward. Repeated shutdown is harmless.

GUI modal methods expose `*Async` counterparts. Their coroutine frames own
panels, close them on cancellation or failure, and release text-input state.
Detached deferred widget initialization uses weak ownership. Linked widgets
always use the context task group; standalone widgets own a fallback group.
`showMessageLater` starts an owned modal task without pumping and rejects closed
contexts, including calls through retained Python wrappers. Python `CGame.post`
and `runUiFlowLater` defer owned callbacks through the session; callback flows
may return generators, and shutdown cancels queued captures before invocation.

Pause, save, defeat recovery, and prepared campaign callbacks use a `CScriptFlow` driven
by `CGuiHandler::runScriptFlowAsync`. Python generators yield owned JSON modal
requests; native code awaits each modal and sends its answer back. Ordinary
modal failures enter the generator's existing exception branches. Cancellation
and scheduler rejection propagate. Flow state holds a weak game reference and
closes the generator under the GIL. Save-status text belongs to the native GUI
handler so temporary Python wrappers do not shorten its session lifetime.

Python scripts post session work through `CGame.post(callback)` or
`runUiFlowLater(callback)`. Both defer the callback to a posted task, retain its
captures, reject a closed session, and release cancelled callbacks without
invoking them. UI callbacks return a generator that yields modal requests;
ordinary callbacks return `None`. Artifact choices use this generator path,
while the global event-loop adapter remains available to external consumers.
