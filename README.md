# influence-trace-spec

**A design specification for response-level influence tracing and operationally reversible memory in agent memory systems.**

[Read the full spec →](./SPEC.md)

---

## What this is

Two primitives for agent memory that are missing across every major memory system in 2026:

1. **Response-level influence tracing.** Every generated response is bound to the exact memory facts that grounded it, with per-fact grounding scores. Given a response ID, you get back the facts, their ranks, their similarity scores, and whether they actually made it into the final prompt.
2. **Operationally reversible memory.** Every mutation writes a typed entry to an append-only op log. The system exposes `rollback(op_id)`, `query_at(timestamp)`, and `diff(memory_id, v1, v2)`, i.e. primitives today's memory vendors don't ship.

These are a layer above the audit trails that systems like Mem0 already expose. The audit trail is a solved problem; the operational layer above it is not.

## Why this exists

Three things are simultaneously true about agent memory in production today:

- Memory layers (Mem0, Zep, Letta, Cognee, Supermemory, LangMem) are the default, not the exception.
- Memory edits happen invisibly; most systems use LLM-arbitrated updates that mutate state on every write.
- There is no per-response attribution: you can ask "what's in memory?" but not "which memories caused *this* response?"

When an agent gives a wrong answer, debugging requires walking through application logs, vector store snapshots, and LLM trace dumps in three separate systems. It should require one API call.

The full argument, with comparison tables, worked examples, and the data model, is in [SPEC.md](./SPEC.md).

## Status

Draft v0.1, published as a request for comment. The spec will change with implementation experience and community feedback. Substantive disagreements (for example "this primitive is wrong" or "this signal is misweighted") are what actually improve the document.

A reference implementation (MemArray, Apache 2.0) is in development at [memarray/memarray](https://github.com/memarray/memarray).

## Contributing

Issues and PRs welcome. See [CONTRIBUTING.md](./CONTRIBUTING.md). Particularly interested in:

- Implementation experience from teams adopting these primitives in their own memory systems
- Counter-examples where the grounding-score formulation breaks down
- Edge cases in `rollback` semantics (cascading dependencies, multi-tenant federation)
- Bi-temporal query patterns from compliance and audit use cases

## License

Apache 2.0; see [LICENSE](./LICENSE).

## Author

Akhil Sanker ([@akhilmedvolt](https://github.com/akhilmedvolt)). Building MemArray full-time. Looking for design partners (especially voice-agent teams on LiveKit / Vapi / Retell) and a co-founder with GTM experience.
