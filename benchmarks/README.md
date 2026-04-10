# Benchmark Catalog

Bundled benchmarks live here and can be referenced with:

```yaml
research:
  evaluation:
    benchmark_id: bench-003
```

Each benchmark YAML can define:

- `benchmark_id`
- `title`
- `description`
- `expected_dimensions`
- `required_keywords`

## Current bundled benchmarks

- `bench-001` — Python orchestration smoke benchmark
- `bench-002` — Python orchestration coverage benchmark
- `bench-003` — Vendor comparison decision benchmark
- `bench-004` — Compliance methodology benchmark
- `bench-005` — Performance architecture benchmark

These are lightweight expectations, not full gold-answer datasets. They are
intended to provide repeatable structural checks while the benchmark suite
continues to grow.
