## Performance Architecture

This page describes how performance concerns are handled at the architectural level in the Contract Knowledge Graph system and links to the detailed optimization guides and benchmarks.

### High-Level Design

- **Multi-layered optimization**:
  - Storage: SPARQL query caching, text index in Fuseki, Milvus vector index tuning.
  - Retrieval: template-based SPARQL generation, routing (SPARQL vs vector vs hybrid), ReAct orchestration.
  - LLM: batching, synthesis optimization, and Phoenix-based profiling.
- **Separation of concerns**:
  - Core architecture pages (`overview`, `agents`, `hybrid-rag`, `knowledge-graph`) focus on functionality.
  - Performance pages (`performance/optimizations`, `PERFORMANCE_IMPROVEMENTS.md`) focus on concrete speedups and measurements.

### Where to Read More

- **Optimization Guide (MkDocs)**  
  See the detailed, continuously updated guide:
  - `Performance → Optimization Guide` in the left navigation, or
  - `performance/optimizations.md` directly.

- **Performance Improvements Summary (Repo Root)**  
  The historical, code-level summary lives in:
  - `PERFORMANCE_IMPROVEMENTS.md` (tracked in the repo root).

That document explains:

- What was optimized (I/O, caching, routing, vector search, LLM calls, etc.).
- Which files were changed for each optimization.
- Before/after timings where available.

