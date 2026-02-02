## Benchmarks

This page summarizes where to find and how to run performance benchmarks for the Contract Knowledge Graph system.

### Current Benchmark Sources

- **Performance Improvements Summary (root)**  
  The file `PERFORMANCE_IMPROVEMENTS.md` in the repository root contains:
  - A chronological list of optimizations.
  - Reported before/after timings for key workloads.
  - Recommended metrics to monitor (execution time, cache hit rate, DB load, memory, I/O).

- **Optimization Guide (MkDocs)**  
  The page `performance/optimizations.md` (linked in the left nav as **Optimization Guide**) includes:
  - A consolidated table of optimizations and their impact.
  - Query and resource benchmarks (per-query and concurrent-load tables).

### How to Run Benchmarks

From the project root:

```bash
# Run system benchmark suite
make benchmark

# Run evaluation with timing against YAML test cases
make test-evaluate YAML=tests/test_cases/test_cases_simple.yaml
```

These commands exercise the ingestion and retrieval pipelines and record timing information that you can inspect via:

- Phoenix UI at `http://localhost:6006` (LLM and pipeline traces).
- Retrieval logs at `agents/logs/retrieval/retrieval.log`.

### Adding New Benchmarks

When adding new performance tests:

1. Implement the benchmark logic under an appropriate script in `scripts/` or `agents/tests/`.
2. Wire it into the Makefile (e.g., `make benchmark-<name>`).
3. Update:
   - `PERFORMANCE_IMPROVEMENTS.md` with a short description and measurements.
   - This page with how to run the new benchmark.

