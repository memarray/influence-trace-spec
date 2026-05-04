# Response-Level Influence Tracing for Agent Memory

**A design specification for operationally reversible memory and per-response grounding attribution.**

Author: Akhil Sanker (`@akhilmedvolt`)
Status: Draft v0.1 — request for comment
License: Apache 2.0
Repository: `github.com/memarray/influence-trace-spec`

---

## TL;DR

Every production agent that uses a memory layer today can answer "what does the agent remember about the user?" but cannot answer two questions that matter more: *"which memories caused this specific response?"* and *"can I undo what the memory layer just did to my data?"*

This document specifies two primitives for agent memory systems that close those gaps:

1. **Response-level influence tracing.** Every generated response is bound to the exact set of memory facts that grounded it, with per-fact grounding scores. Given a response ID, you get back the facts, their ranks, their similarity scores, and whether they actually made it into the final prompt.
2. **Operationally reversible memory.** Every mutation (insert, update, supersede, invalidate, merge) writes a typed entry to an append-only operation log. From this log, the system exposes three primitives that today's memory vendors do not: `rollback(op_id)`, `query_at(timestamp)`, and `diff(memory_id, v1, v2)`.

These are not theoretical. They are implementable on top of Postgres 16/17 with `pgvector`, `tsvector`, and Apache AGE, with a sub-300ms P95 retrieval budget that fits inside a voice-agent turn. This spec defines the data model, the API surface, the grounding-score function, and the worked examples that demonstrate the primitives end-to-end.

This is a spec, not a product announcement. The reference implementation (MemArray) is in development. The point of publishing the spec first is to define the primitives publicly so that any memory system — open source or commercial — can adopt them, contest them, or extend them.

---

## 1. Why this spec exists

### 1.1 The problem in production

Three things are simultaneously true about agent memory in 2026:

**Memory layers are the default.** Most production agents now use Mem0, Zep, Letta, Cognee, Supermemory, LangMem, or a homegrown variant. Mem0 alone is the exclusive memory provider for the AWS Agent SDK, has 53k+ GitHub stars, and raised $24M in October 2025. The category is no longer experimental.

**Memory edits happen invisibly.** The dominant pattern across these systems is LLM-arbitrated update: at write time, the system retrieves similar existing memories, asks an LLM to decide whether to ADD, UPDATE, DELETE, or do nothing, and applies the decision. Mem0's open-source code does this explicitly. Zep does a temporal variant. The result is that on every `add()` call, your memory store can mutate in ways the calling code did not specify and cannot directly inspect.

**There is no per-response attribution.** When an agent says something wrong, the developer can ask the memory layer "what's in memory?" and "what did you change recently?" but cannot ask "which specific memories caused *this response*?" The memory layer and the LLM call are decoupled, and the link between them is reconstructed by hand, after the fact, with logs and luck.

These three facts compose into a real production problem. An agent gives a wrong answer. The developer wants to know: was the right fact in memory? Was it retrieved? Did it make it into the prompt? Was it overwritten last Tuesday by an LLM-arbitrated update no one approved? Today, answering those questions requires walking through application logs, vector store snapshots, and LLM trace dumps in three separate systems. It should require one API call.

### 1.2 What current systems give you, and what they don't

To be precise about the gap, here is what the most adopted system — Mem0 — exposes today, verified against `docs.mem0.ai` as of April 2026:

| Capability | Mem0 today | What this spec adds |
|---|---|---|
| Per-memory history (audit trail) | **Yes** — `GET /v1/memories/{memory_id}/history` returns `{old_memory, new_memory, event ∈ {ADD, UPDATE, DELETE}, created_at, updated_at}` | Same audit trail, but as a typed `op_log` with structured before/after diffs and reason codes |
| Rollback an operation | No | `POST /v1/memory/rollback` with an `op_id` |
| Time-travel query (read state as of T) | No | `GET /v1/memory/query_at?as_of=...` |
| Version diff between two states of one memory | No | `GET /v1/memory/diff/{memory_id}?from=v1&to=v2` |
| Per-response trace of which facts grounded the answer | No | `GET /v1/trace/{response_id}` |
| Grounding score per fact in a response | No | Returned by `/trace/{response_id}` |

This is not a knock on Mem0 specifically. Zep ships bi-temporal timestamps and a temporal knowledge graph (Graphiti), which is excellent for "when was this true?" — but it does not expose rollback, response-level attribution, or version diffs as first-class primitives either. Letta's `Context Repositories` (Feb 2026) introduce git-style memory snapshots for coding agents, which is the closest analog in the field, but the model is repository-scoped rather than fact-scoped and does not include response-level attribution.

The audit trail, in other words, is a solved problem. The *operational layer above the audit trail* — the layer that lets you roll back, time-travel, diff, and trace — is not.

### 1.3 Why voice agents force the issue

Most agent surfaces tolerate slow, opaque memory. Voice agents do not. A voice turn has a hard latency budget — typically 500–800ms end-to-end before the user perceives a stall — and memory retrieval has to fit inside roughly 150ms of that budget. Voice agents also surface memory failures viscerally: when a voice receptionist forgets a caller's name mid-call, the user notices in a way they do not when a text chatbot quietly drops a preference.

The voice-agent ecosystem is converging on a small set of platforms — LiveKit Agents, Vapi, Retell — none of which ship first-party persistent memory as of April 2026. All three direct users to third-party memory layers. This means the developer experience for voice memory is: pick Mem0/Zep/Supermemory, glue it in, hope it doesn't overwrite the wrong thing, and reconstruct what happened after the fact when something goes wrong.

The primitives in this spec are general — they are not voice-specific. But the design constraints (sub-300ms retrieval, op-log writes off the hot path, traces written asynchronously) are calibrated for voice because voice is the most demanding case. A memory system that fits inside a voice turn fits inside any other agent loop too.

### 1.4 What this spec is, and is not

This spec **is** a design document defining APIs, data shapes, and algorithms precisely enough that any team can implement them on any reasonable database stack (Postgres-centric, document-store-centric, or graph-native). It assumes familiarity with vector retrieval, hybrid search, and basic event-sourcing patterns.

This spec **is not** a product manual, a benchmark, or a comparison. It does not claim that any specific memory system is bad; it claims that a specific layer of functionality is missing across the category, and proposes a concrete shape for filling it.

---

## 2. Concepts

### 2.1 Fact, the atomic memory unit

A **fact** is the smallest piece of memory the system stores. It is a typed, structured record — not a raw text chunk. The intent is to make memory inspectable: a fact is a thing you can look at, edit, invalidate, or roll back, not a paragraph you have to parse.

A fact has:

- **Identity:** a `fact_id` (UUID), a `tenant_id` for multi-tenant isolation, and a `subject` (the entity the fact is about — usually a user, but can be any entity).
- **Predicate:** what kind of fact this is. Drawn from a small ontology (`person`, `preference`, `relationship`, `event`, `task`, `location`, `skill`, `belief`, `goal`, `constraint`, `artifact`, plus user-defined predicates). The predicate is what makes the fact typed; it is what lets the system reason about which facts contradict which other facts.
- **Object:** the content of the fact, as JSON. For `preference("Alice", "dietary", {value: "vegetarian"})`, the object is `{value: "vegetarian"}`. For `relationship("Alice", "spouse", {target: "Bob"})`, the object is `{target: "Bob"}`.
- **Confidence:** a float in `[0, 1]` from the extractor. Used at write time to gate whether the fact is auto-accepted, queued for human review, or dropped.
- **Source reference:** where this fact came from — the conversation ID, the message ID, the timestamp, the speaker.
- **Bi-temporal timestamps:** four of them. `valid_at` (when the fact became true in the world), `invalid_at` (when it stopped being true, NULL if still valid), `created_at` (when the system learned it), `expired_at` (when the system stopped believing it, NULL if still believed). The first two describe the world; the second two describe the system's knowledge of the world. This separation is what lets you ask "what did the system know about Alice's dietary preferences as of last Tuesday, given what we know now?"
- **Reversibility links:** `supersedes` (this fact replaces the fact with this ID) and `superseded_by` (this fact has been replaced by the fact with this ID).
- **Retrieval indexes:** an embedding (vector) for semantic similarity, and a `tsvector` for keyword matching.

Facts are append-only. A fact is never edited in place. An "edit" is the creation of a new fact that supersedes the old one; the old one's `superseded_by` is set, its `expired_at` is filled, and the new one's `supersedes` points back. This is what makes the system reversible: every state is recoverable by reading the op log forward or backward from any point in time.

### 2.2 Operation log

The `op_log` is the spine of the system. Every mutation — every insert, every supersession, every invalidation, every merge, every rollback — writes one row to `op_log`. The schema is:

```
op_id        UUID           primary key
tenant_id    UUID           who owns this op
op_type      enum           INSERT | INVALIDATE | SUPERSEDE | MERGE | ROLLBACK
target_id    UUID           the fact_id this op affected
before       JSONB          the fact's state before the op (null for INSERT)
after        JSONB          the fact's state after the op (null for some INVALIDATE forms)
reason       enum           CONTRADICTED | SUPERSEDED | EXPIRED_WORLD | USER_EDIT |
                            DEDUPE_MERGE | TENANT_PURGE | ROLLBACK | INSERT_NEW
actor        text           who initiated this op (system, user_id, agent_id)
ts           timestamptz    when this op happened
parent_op    UUID           NULL except for ROLLBACK ops (points at the op being undone)
```

The log is append-only — there is no `UPDATE op_log SET ...` anywhere in the system. Once written, an op is permanent. Rollback does not delete an op; it appends a new ROLLBACK op whose `before`/`after` are the inverse of the target op.

The two invariants the implementation must enforce, with property tests:

1. **Append-only.** No code path mutates `op_log` rows. Enforced at the database level with `REVOKE UPDATE, DELETE ON op_log` for the application role.
2. **Round-trip reversibility.** For any op `x`, applying `rollback(x)` and then re-reading the affected fact's state must produce the state that existed before `x`. Equivalently: `invalidate(rollback(x)) ≡ x`.

### 2.3 Response trace

When the agent calls the memory system to retrieve facts for a query, the system returns both the facts *and* a `response_id`. After the agent runs the LLM and emits its response, the agent (or the SDK) reports back which facts were actually included in the final prompt. The system records this as a **response trace**:

```
response_id    UUID
tenant_id      UUID
query          text
model          text
ts             timestamptz
latency_ms     int
prompt_tokens  int
completion     text   -- optional; not stored by default
```

And, for each fact the retrieval returned, a **response–fact link**:

```
response_id    UUID
fact_id        UUID
rank           int      -- position in the retrieval result
similarity     float    -- raw vector cosine similarity to the query
in_prompt      bool     -- did the SDK confirm this fact made it into the final prompt?
grounding      float    -- combined score, defined in section 3
```

A response trace is the answer to "which memories caused this answer?" It is written off the hot path — the response trace insert does not block the agent's response — but it is durable, indexed by `response_id`, and exposed via `GET /v1/trace/{response_id}`.

### 2.4 Bi-temporal semantics

Memory has two time axes, not one:

- **Valid time** is when a fact was true in the world. "Alice lived in Bangalore" was valid from 2020 to 2024.
- **Transaction time** is when the system knew it. The system might have learned Alice lived in Bangalore on March 5th 2024; if she actually moved away on January 1st 2024, then the fact's `valid_at` is in 2020, its `invalid_at` is January 1st 2024, but its `created_at` is March 5th 2024.

Most memory systems collapse these into a single `created_at`/`updated_at` pair, which is why they cannot answer questions like "what did the system believe about Alice's location as of February 2024, before we learned she had moved?" This is exactly the question a compliance auditor or a debugging engineer asks when investigating an agent's bad decision.

A bi-temporal query against the system specifies two parameters: `as_of` (the valid-time point you want to read about) and `known_by` (the transaction-time point you want the system's knowledge state to be from). The default for both is `now()`.

---

## 3. The grounding score

The grounding score is a single float in `[0, 1]` per `(response_id, fact_id)` pair that says, roughly, how much this specific fact is responsible for the response. The score has to be cheap to compute (it runs on every retrieved fact, on every query), interpretable (a developer should be able to look at it and reason about it), and defensible (it should not be a black box).

### 3.1 Definition

The grounding score combines four signals, in order of how cheaply they are available:

- **Rank signal `r`:** `1 / (k_const + rank)` where `rank` is the fact's position in the fused retrieval result. `k_const` defaults to 60 (matching reciprocal rank fusion conventions). The intuition: facts that appear high in the retrieval result are more likely to have been the basis for the answer than facts that barely made the cutoff.
- **Similarity signal `s`:** the raw cosine similarity between the query embedding and the fact embedding, clipped to `[0, 1]`. The intuition: a fact that is semantically close to the query is more likely to be relevant than one that is distant.
- **Prompt-presence signal `p`:** `1.0` if the fact made it into the final prompt sent to the LLM, `0.0` if it was retrieved but truncated out before the LLM saw it. The intuition: a fact the LLM never saw cannot have grounded the response, regardless of how well it matched.
- **Attention signal `a`** (optional, V1): if the LLM exposes attention weights or per-token logprobs over the prompt, the system aggregates the attention mass that landed on the tokens belonging to this fact. Defaults to `null` and is omitted from the score when not available.

The base score is:

```
grounding = w_p · p · (w_r · r̂ + w_s · s)
```

where `r̂` is `r` rescaled to `[0, 1]` via `r̂ = r / (1 / (k_const + 1))`, and the default weights are `w_p = 1.0`, `w_r = 0.4`, `w_s = 0.6`. The leading `w_p · p` factor means: if the fact was not in the prompt, its grounding score is zero. This is deliberate — a fact the LLM did not see did not ground the response, and the score reflects that exactly.

When the attention signal is available, the V1 score becomes:

```
grounding_v1 = w_p · p · (w_r · r̂ + w_s · s + w_a · a)
```

with `w_a = 0.3` and the other weights renormalized so the sum is 1. The defaults are tunable per tenant.

### 3.2 Why these four and not something fancier

Two reasons. First, cheap signals are what make this implementable inside a voice-turn budget. Computing `r` and `s` adds zero latency on top of retrieval (they fall out of retrieval for free), `p` is reported asynchronously by the SDK after the LLM returns, and `a` is opt-in. None of this requires a second model call.

Second, the goal of a grounding score is not to predict the LLM's behaviour — that is what evals are for. The goal is to give a developer a defensible answer to "which fact caused this?" The four signals are auditable: a developer can look at the rank, the similarity, the in-prompt flag, and reason about whether the score makes sense. A learned grounding model would be more accurate and less defensible — when an auditor asks why a fact got a 0.87 score, "because the model said so" is not an answer.

The system MAY ship a learned reranker that produces a richer grounding signal, but the spec requires the four-signal version to be available as the default, with weights inspectable and tunable per tenant.

### 3.3 What grounding does not claim

The score is correlational, not causal. It says "given this query, this fact was retrieved at this rank with this similarity and made it into the prompt." It does not claim the LLM actually used the fact. It does not claim the fact is *true*. It does not claim the response is *correct*. It is the strongest local evidence available without re-running the LLM with that fact removed.

The honest causal version is: rerun the LLM with the fact removed and observe whether the response changes. The system supports this — `POST /v1/trace/{response_id}/counterfactual` re-runs the response with a specified fact omitted from the prompt, and returns the new completion alongside the original. This is too expensive to run on every response, but cheap enough to run on the responses a developer is investigating.

---

## 4. The reversibility primitives

This section specifies the three operational primitives that distinguish the system from a plain audit trail: `rollback`, `query_at`, and `diff`. Each is defined first by what it does, then by its semantics under edge cases.

### 4.1 `rollback(op_id)`

**Behaviour.** Given an `op_id`, the system computes the inverse operation and applies it. The original op is not deleted from `op_log`; instead, a new op of type `ROLLBACK` is appended, with `parent_op = op_id` and `before`/`after` swapped from the original op.

**Inverses by op type:**

- `INSERT` → emit an `INVALIDATE` with `reason = ROLLBACK` on the inserted fact.
- `INVALIDATE` → emit an `INSERT`-equivalent that re-validates the fact (set `expired_at = NULL`).
- `SUPERSEDE` → re-validate the superseded fact and invalidate the superseding fact.
- `MERGE` → split the merged fact back into its constituents.
- `ROLLBACK` → emit a ROLLBACK of the rollback. Yes, you can roll back a rollback. This is the "undo undo" case and the system has to handle it cleanly.

**Edge cases.**

- **Cascading dependencies.** If op `A` superseded fact `f1` with fact `f2`, and op `B` later superseded `f2` with `f3`, then `rollback(A)` cannot trivially restore `f1` because `f2` no longer exists in its original form. The system MUST refuse the rollback with `409 ROLLBACK_CONFLICT` and return the dependency chain `[A, B]`. The caller can either roll back `B` first, then `A`, or call `force_rollback` which cascades automatically. The default is to refuse, because cascading rollback is destructive and should require explicit consent.
- **Rollback after invalidation by a different actor.** If a fact was invalidated for `TENANT_PURGE` (a deliberate compliance deletion) and a separate op then tried to be rolled back over it, the rollback MUST refuse with `409 IMMUTABLE_REASON`. Some invalidation reasons are designed to be permanent.
- **Rollback of a write that was the basis for a later response.** A response trace that depended on a fact that has since been rolled back is annotated, on read, with `rollback_affected: true`. The trace itself is never modified — traces are historical records of what the system actually did, even if what it did has since been undone.

### 4.2 `query_at(as_of, known_by)`

**Behaviour.** Given a valid-time point `as_of` and a transaction-time point `known_by` (both default to `now()`), return the set of facts that were valid at `as_of` from the perspective of the system's knowledge as of `known_by`. The SQL predicate, on the underlying `facts` table, is:

```sql
WHERE valid_at <= :as_of
  AND (invalid_at IS NULL OR invalid_at > :as_of)
  AND created_at <= :known_by
  AND (expired_at IS NULL OR expired_at > :known_by)
```

**Why both axes matter.** Compliance and debugging often require asking "what did the system believe at the moment it made the decision?" — which is `as_of = decision_time`, `known_by = decision_time`. But sometimes the question is "given everything we now know, what was actually true at the decision time?" — which is `as_of = decision_time`, `known_by = now()`. These are different questions and produce different answers, and a memory system that collapses them into a single timestamp cannot tell them apart.

**Performance.** Time-travel queries hit the same indexes as live queries (`pgvector` HNSW for semantic, `tsvector` for keyword), with the temporal predicate as a secondary filter. P95 latency for `query_at` on a 1M-fact tenant should be within 1.5x of the equivalent live query.

### 4.3 `diff(memory_id, from_version, to_version)`

**Behaviour.** Given a `memory_id` (which, in this system, is a `subject` together with a `predicate` — e.g. `("alice", "dietary_preference")`), and two version anchors, return a structured diff of the fact's state between those anchors. Version anchors can be:

- A specific `op_id`, meaning "the state immediately after this op."
- A timestamp, resolved against `expired_at` to find the right version.
- A literal version number `vN`, where `v0` is the first INSERT and each subsequent op increments.

**Diff shape.** The diff is JSON, not text:

```json
{
  "memory_id": ["alice", "dietary_preference"],
  "from": {"version": "v2", "op_id": "...", "ts": "..."},
  "to":   {"version": "v3", "op_id": "...", "ts": "..."},
  "changes": [
    {"path": "object.value", "from": "vegetarian", "to": "vegan"},
    {"path": "confidence",   "from": 0.92,        "to": 0.78},
    {"path": "valid_at",     "from": "2024-01-01T00:00:00Z", "to": "2026-03-15T00:00:00Z"}
  ],
  "ops_between": ["op_id_1", "op_id_2"]
}
```

**Why structured.** A text diff of two fact JSON blobs would be human-readable but not programmatic. Compliance tooling, audit dashboards, and downstream alerting all need to ask "did the `value` field change?" or "did `confidence` drop more than 0.2 in one op?" — questions that require a structured diff, not a text one.

---

## 5. Worked examples

### 5.1 Voice receptionist forgets a caller's name

**Setup.** A voice receptionist agent for a dental clinic. A returning patient calls. The agent should retrieve the patient's name, last visit, and known allergies, then greet them by name.

**The bug.** The agent greets the caller as "the patient" instead of by name. The developer needs to know why.

**Investigation, today.** Pull application logs. Find the LLM call ID. Pull the LLM trace. See the prompt. Notice the prompt did not contain the patient's name. Pull the memory layer's logs. See that an `add()` call from yesterday triggered an LLM-arbitrated update. Manually compare yesterday's memory state to today's by reconstructing both from history. Spend 45 minutes determining that an irrelevant `add()` of a new appointment caused the LLM arbitrator to overwrite the patient's name field. File a bug. Hope it doesn't happen again.

**Investigation, with this spec.**

```python
trace = client.trace.get(response_id="resp_abc123")
# trace.facts is a list of (fact_id, rank, similarity, in_prompt, grounding)
# for each fact retrieved for this response
```

The trace shows that the patient's name fact was *not* retrieved at all — it had been superseded yesterday. One more call:

```python
history = client.memory.history(memory_id=("patient_42", "name"))
# returns the list of versions, with op_ids and reasons
```

The developer sees: `v1` was the original name, `v2` was a SUPERSEDE op from yesterday with `reason=CONTRADICTED`, where the LLM arbitrator decided a new appointment fact "contradicted" the name. The fix is one call:

```python
client.memory.rollback(op_id="op_xyz789")
```

The name is restored. The op log records the rollback. Total time: under five minutes.

### 5.2 Compliance audit on a financial-services agent

**Setup.** A bank's customer-service agent gives a customer incorrect information about their account on March 10th. On April 5th, a regulator asks: "what did your agent know about this customer on March 10th, and what facts did the agent's response on that date rely on?"

**With this spec.**

```python
# What did the system believe about the customer on March 10th, as of March 10th?
state_at_decision = client.memory.query_at(
    subject="customer_99",
    as_of="2026-03-10T14:00:00Z",
    known_by="2026-03-10T14:00:00Z"
)

# What did the agent's response on March 10th depend on?
trace = client.trace.get(response_id="resp_march10")
# Returns the exact facts retrieved, their grounding scores, and which ones were in the prompt
```

The regulator gets a complete, signed answer in two API calls. The op log proves nothing was edited after the fact. The `known_by` parameter is the proof: even if facts were corrected later (as `as_of=2026-03-10, known_by=now()`), the system can also produce the state the agent actually saw (`as_of=2026-03-10, known_by=2026-03-10`).

### 5.3 Debugging a regression after a prompt change

**Setup.** A team changes the system prompt for their support agent. Recall on a private eval set drops by 8 points. They suspect the new prompt is causing the LLM to ignore retrieved facts, but they want to confirm.

**With this spec.** For each failing eval case, pull the response trace and examine the `in_prompt` and `grounding` columns. If facts are being retrieved (high similarity, good rank) but `in_prompt = false`, the issue is prompt truncation — the new prompt's added preamble is pushing facts out. If facts are `in_prompt = true` with high `grounding` but the response still ignores them, the issue is the prompt's instruction style — the facts are present but the model is being told to weight them differently.

The trace turns a vague "regression somewhere in the stack" into a localized "prompt truncation at this token offset" or "instruction conflict at this section."

---

## 6. Reference architecture

The spec is implementation-agnostic, but a reference shape helps. The MemArray reference implementation uses:

- **Postgres 16/17** as the single durable store. `pgvector` (HNSW indexes) for vector retrieval, `tsvector` (GIN indexes) for keyword retrieval, Apache AGE 1.6/1.7 for the optional graph layer. Apache AGE shipped on Postgres 17 in March 2026, so the graph capability does not require a separate database.
- **Redis 7** for the semantic cache (query → result, with a similarity-key check), rate limiting, and distributed locks.
- **A co-located embedding model** running in-process via ONNX (BGE-small, 384 dimensions, ~12ms per query on commodity hardware). Co-located because the network round-trip to a remote embedder is itself larger than the voice-turn budget allows.
- **FastAPI** (async, uvicorn workers, one per core) for the API surface.
- **Background workers** (arq on Redis) for extraction, dedup, invalidation propagation, and benchmark runs.

The architecture fits on three commodity servers — one for the API + embedder + workers, one as a hot standby plus benchmark runner, one for Postgres + Redis. This is deliberate: the reference implementation is meant to be runnable by a small team without a dedicated platform org.

A representative latency budget for the voice fast path on this stack:

| Step | Budget |
|---|---|
| Auth + parse | 2 ms |
| Semantic cache lookup (hit returns immediately) | 3 ms |
| Local embed (BGE-small ONNX) | 12 ms |
| Bi-temporal query rewrite | 1 ms |
| Parallel retrieval (vector + graph + keyword, gathered) | 25 ms |
| Reciprocal rank fusion | 2 ms |
| Trace write (off the hot path) | 0 ms |
| Serialize + return | 5 ms |
| **Total P95 target** | **~80–120 ms** |

A 25–40% cache hit rate on realistic voice workloads — measured on prototype workloads, not yet benchmarked publicly — brings the effective P95 well under 150ms.

---

## 7. API surface

This is a partial enumeration; the full OpenAPI spec lives in `/openapi.yaml` in the reference repository.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/memory/add` | Ingest raw text or structured facts; returns `op_ids` |
| `POST` | `/v1/memory/search` | Hybrid retrieval; returns `response_id` + facts |
| `GET`  | `/v1/memory/profile/{subject}` | Current-state profile of an entity |
| `POST` | `/v1/memory/edit` | Explicit edit (creates SUPERSEDE op) |
| `POST` | `/v1/memory/invalidate` | Explicit invalidate with reason code |
| `POST` | `/v1/memory/rollback` | Rollback by `op_id` |
| `GET`  | `/v1/memory/query_at` | Time-travel query |
| `GET`  | `/v1/memory/diff/{memory_id}` | Diff between two versions of one memory |
| `GET`  | `/v1/memory/history/{memory_id}` | Full version history |
| `GET`  | `/v1/trace/{response_id}` | Per-response influence trace |
| `POST` | `/v1/trace/{response_id}/counterfactual` | Re-run with a fact omitted |
| `GET`  | `/v1/ops` | Op-log query (audit) |
| `GET`/`POST` | `/v1/ontology/predicates` | List or define predicates |

---

## 8. Open questions

The following are deliberately not specified yet, because they require implementation experience or community input before being locked.

**Q1. Should grounding scores be normalized per-response or absolute?** Per-response (where scores in one response sum to 1) is more interpretable but loses information about overall retrieval quality. Absolute (where each score is independent) is more honest but harder to compare across responses. The current draft uses absolute; this may change.

**Q2. How should the system handle facts that span tenants in a federated deployment?** Cross-tenant memory (e.g. an enterprise where multiple sub-orgs share a knowledge base) is real, but the bi-temporal model interacts non-trivially with tenant-scoped op logs. Out of scope for v1; flagged for v2.

**Q3. Should `query_at` support transaction-time ranges, not just points?** The current spec is point-in-time. A range query ("show me everything the system believed about Alice between Tuesday and Thursday") is useful for change-detection use cases but adds query complexity. Possible v2.

**Q4. What is the right unit for `memory_id`?** The current spec uses `(subject, predicate)` because that aligns with the ontology. An alternative is to give every "memory" (semantically distinct piece of knowledge) a stable UUID, where supersession links versions of the same UUID. The two approaches are isomorphic but the ergonomics differ. Open for community input.

---

## 9. Prior art and acknowledgements

This work builds on:

- **Mem0** (Chhikara et al., 2025) for the LLM-arbitrated extraction pattern and the open-source memory category overall. The history endpoint that the system exposes is the right base layer; this spec is a proposal for the operational layer above it.
- **Zep / Graphiti** (Zep AI, 2024) for the bi-temporal knowledge graph model. The four-timestamp formulation in this spec is consistent with Graphiti's.
- **Letta** for `Context Repositories`, which is the closest existing analog to repository-scoped reversible memory.
- **The event-sourcing literature** (Fowler, "Event Sourcing"; Young, "CQRS Documents") for the append-only op-log pattern.
- **Bi-temporal database research**, specifically Snodgrass's *Developing Time-Oriented Database Applications in SQL*, for the four-timestamp convention.

This spec is published as a request for comment, not a finished standard. It will change in response to implementation experience, community feedback, and pull requests against the reference implementation. The intent is that any memory system — open source or commercial — can adopt the primitives, contest them, or extend them.

---

## 10. Status, license, and how to contribute

**Status:** Draft v0.1, published [DATE TO INSERT]. Subject to revision based on community feedback. No backwards-compatibility guarantees until v1.0.

**License:** This spec is released under Apache 2.0. The reference implementation (MemArray) is also Apache 2.0.

**Contributing:** Issues and PRs welcome at `github.com/memarray/influence-trace-spec`. Substantive disagreements with the spec — especially "this primitive is wrong" or "this signal in the grounding score is misweighted" — are the kind of feedback that changes the document.

**Reference implementation status:** The MemArray reference implementation is in development. A v0.1 demo (showing `add`, `search`, response tracing on toy data, and rollback) is targeted for [DATE TO INSERT]. Track progress at `github.com/memarray/memarray`.

---

*Author: Akhil Sanker, founder of MemArray. Reach me at [contact] or on GitHub at [@akhilmedvolt](https://github.com/akhilmedvolt). I am building MemArray full-time and looking for design partners (especially teams running voice agents on LiveKit / Vapi / Retell) and a co-founder with a GTM background. If either describes you, I'd genuinely love to talk.*
