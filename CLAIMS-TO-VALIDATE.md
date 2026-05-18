# Claims to validate (from SPEC.md)

Statements to verify against **competitor docs, public APIs, or source code** before treating them as settled.

This file records **how** each claim can be checked. Methods are complementary: “code” reduces drift; “docs” and “judgment” still matter where APIs are opaque or features are renamed.

---

## How verification works (legend)

| Method | What it means | Limits |
|--------|----------------|--------|
| **Code / static analysis** | Clone a pinned tag of an OSS repo; trace call paths, grep for orchestration (LLM calls, ADD/UPDATE/DELETE branches). | Only where source is public and you pin a revision. |
| **Machine-readable API surface** | OpenAPI/Swagger, protobuf/gRPC defs, or SDK source in GitHub: search paths, operation IDs, client methods. | Proves **artifact** presence/absence at that revision, not every deployment tier; renamed features need human mapping. |
| **Live HTTP / integration** | Call documented endpoints with test credentials; expect 200 vs 404 for specific routes. | Needs keys, stable env, and a defined “surface” (e.g. `v1` REST only). |
| **Docs + dated evidence** | Archive links, changelog, or snapshots; cite date and URL. | Docs can lag code; still the right evidence for positioning. |
| **Manual / comparative** | Decide whether a third-party feature is **equivalent** to this spec’s primitives (semantics, fields, guarantees). | Cannot be fully automated; needs a short rubric tied to SPEC.md. |

---

## Mem0

### Capability gap vs this spec

**Claim:** No rollback-by-`op_id`, no `query_at`-style time-travel read, no version `diff` primitive, no per-response trace / grounding API **as specified in this repo’s SPEC**.

| Verify with | How |
|-------------|-----|
| Machine-readable API surface | Obtain Mem0’s published OpenAPI or SDK (pinned version). Search for routes/methods matching rollback, time-travel read, memory diff, response trace; record commit/tag or package version. |
| Live HTTP / integration | Optional: with a test project + API key, probe documented base URL for paths analogous to SPEC (`/rollback`, `/query_at`, `/diff`, `/trace/{response_id}` or vendor equivalents). Record HTTP status and response shape—not just 404 (could be auth or different base path). |
| Docs + dated evidence | Link to `docs.mem0.ai` (or official API reference) with **retrieval date** and screenshot or archived page if policy allows. |
| Manual / comparative | If something exists under another name, map fields to SPEC § APIs and decide “same primitive” vs “adjacent feature”; document the call in one sentence. |

**Note:** Absence in OpenAPI is strong evidence for *that published surface*; it is not a proof of absence across all products/tiers without scoping what you checked.

---

### Write path (LLM-arbitrated updates)

**Claim:** Open-source Mem0 implements LLM-arbitrated updates explicitly: retrieve similar memories → model decides ADD / UPDATE / DELETE / nothing → apply.

| Verify with | How |
|-------------|-----|
| **Code / static analysis** | Primary method. Clone [mem0ai/mem0](https://github.com/mem0ai/mem0) (or canonical org/repo) at a **pinned tag**. Trace default add/update ingestion: find retrieval of similar memories, LLM or structured “memory action” decision, and apply path. Grep for decision enums, tool schemas, or prompt templates that list add/update/delete. Point to file:line in notes or a short appendix. |
| Docs + dated evidence | Cross-check official docs or README description of “how writes work” against what the code does at the same tag. |

---

## Zep

### Write pattern (temporal, model-mediated memory)

**Claim:** Zep does a **temporal** variant of LLM-arbitrated (or model-mediated) memory writes relative to Mem0-style flow.

| Verify with | How |
|-------------|-----|
| Code / static analysis | If Graphiti / Zep write pipeline is in a **public** repo, pin a tag and trace ingestion: timestamps / validity intervals, graph writes, and any LLM or policy step that chooses merge/update/invalidation. |
| Docs + dated evidence | Zep and Graphiti public docs: architecture pages, “how memory is written,” temporal model. Cite URLs + date. |
| Manual / comparative | Summarize in one paragraph how write-time decisions differ from Mem0’s flow (what is “temporal” in code or docs). |

---

### Product shape (bi-temporal / graph vs this spec’s primitives)

**Claim:** Strong bi-temporal model and temporal knowledge graph (Graphiti) for “when was this true?”, but **no first-class** primitives matching this spec for: rollback, response-level attribution, or version diff.

| Verify with | How |
|-------------|-----|
| Machine-readable API surface | Pin Zep’s published OpenAPI/SDK if available; search for rollback, point-in-time read, diff, response-level trace or attribution. |
| Live HTTP / integration | Optional: same caveats as Mem0—scoped surface, credentials, document base URL and version. |
| Docs + dated evidence | Public API reference and product pages; cite what is first-class vs beta vs dashboard-only. |
| Manual / comparative | “First-class” and “matches SPEC” are judgment calls; state explicitly if a feature is **renamed** or **partial** (e.g. audit log without `rollback(op_id)`). |

---

## Letta

### Context Repositories (Feb 2026)

**Claim:** Closest field analog in SPEC: **repository-scoped** (not fact-scoped), and **without** response-level attribution **as specified here**.

| Verify with | How |
|-------------|-----|
| Docs + dated evidence | Letta announcements, blog, and docs for Context Repositories; cite date and URL. |
| Code / static analysis | If Letta exposes a **public** client or server repo for repositories, pin a tag and inspect data model (repository vs fact granularity) and any trace/attribution hooks. |
| Manual / comparative | Map Letta’s model to SPEC’s fact + `/trace/{response_id}` story; explicitly list what is missing or different (granularity, binding to a single generated response, per-fact grounding scores). |

---

## Summary

| Claim area | Best automated signal | Still needs human/doc pass |
|------------|----------------------|----------------------------|
| Mem0 write path | **Yes** — OSS static analysis at pinned tag | Align wording with docs for same tag |
| Mem0 / Zep “missing SPEC primitives” | **Partial** — OpenAPI/SDK grep + optional HTTP probes | Renamed features, tier differences, semantic equivalence |
| Zep temporal writes | **Partial** — OSS if public; else docs | Comparative summary |
| Letta Context Repositories | **Weak** — OSS only if model is in public code | Docs + comparative rubric vs SPEC |

---

*Trimmed list—only competitor technical claims from SPEC.md that need external validation.*
