# Native JSON serialization operations

`CSerialization::serializeExpected(value)` returns owned `json` in a
`CSerializationResult<json>`. `deserializeExpected<T>(game, document)` borrows
`const json&` and returns `CSerializationResult<T>`. Errors carry a code, source,
property path, object type, and message. `serializationValueOrThrow` adapts a
result at existing exception-based Python or free-function boundaries.

Each default API call starts a fresh operation. This includes a Python override
or constructor re-entering the engine: it does not inherit an outer save loader's
strict policy or graph identities. For strict loading, construct
`CSerializationReadContext(true, source)` or `CSerialization::StrictScope(source)`
and pass it explicitly. `StrictScope` owns policy; constructing one does not alter
ambient state. Contexts cannot be copied or moved. Reusing a context after a
completed or failed top-level call starts a clean graph operation.

Recursive native codecs must pass the existing context. For example:

```cpp
CTypes::registerJsonType<ActorValue>(
    [](const ActorValue& value, CSerializationWriteContext& context)
        -> CSerializationResult<json> {
        auto actor = CSerialization::serializeExpected(value.actor, context);
        if (!actor) return std::unexpected(actor.error());
        return json{{"actor", std::move(*actor)}};
    },
    [](const std::shared_ptr<CGame>& game, const json& document,
       CSerializationReadContext& context) -> CSerializationResult<ActorValue> {
        auto actor = CSerialization::deserializeExpected<std::shared_ptr<CCreature>>(
            game, document.at("actor"), context);
        if (!actor) return std::unexpected(actor.error());
        return ActorValue{std::move(*actor)};
    });
```

Value-only codecs may omit the context argument. `registerJsonCodec<T>` registers
only a codec; `registerJsonType<T>` also registers a reflected property setter.
Encoded representation is always JSON. Registry storage is private; `findCodec`
returns an owning immutable handle and a missing lookup cannot insert an entry.
Registration is synchronized, and an existing handle remains usable after a
replacement. Callbacks own their captures.

Custom `CSerializerBase` implementations must implement the virtual methods that
take operation contexts. Its context-free methods are fresh-operation adapters;
they cannot be overridden to bypass the context contract.

Read contexts retain configured document owners while recursion and fixups are
pending. Configuration caches expose `shared_ptr<const json>`; registration from
a mutable JSON pointer seals a copy. The caller keeps a borrowed input document
alive for the duration of the synchronous operation. Decoders must not retain
borrowed JSON references after returning.

The on-disk save schema remains **2** and the effect graph version remains **1**.
Effect identities, detached actor links, clone behavior, legacy save migrations,
structural limits, notification batching, and primary/backup recovery keep their
existing contracts. Standalone object collections retain their per-entry graph
encoding; collections within an object or an explicitly nested codec share the
owning operation's graph.

A context-aware custom codec may return an array or scalar. When its operation
also records actors, the result owns this versioned envelope:

```json
{
  "$gameGraphEnvelope": {"version": 1, "value": ["the codec's original payload"]},
  "effectGraph": {"version": 1, "actors": []}
}
```

Readers validate the entire envelope with the existing document structure
limits, index actor definitions throughout it, then give the codec a borrowed
reference to `value`. The payload is never copied during unwrapping. The envelope
requires exactly the displayed fields, version 1, and a non-object payload;
malformed envelopes return `MalformedGraph`. `$gameGraphEnvelope` and `effectGraph`
are always reserved at codec roots, including value-only codecs that record no
actors; writers reject either collision with `InvalidInput`. The reservation does
not apply to nested JSON payload fields or authored object property names. Object
save roots retain their original `class`, `properties`, and `effectGraph` layout.
A non-object result without an operation-owned graph retains its original representation.
