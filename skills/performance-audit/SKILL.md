---
name: performance-audit
description: Audit code for measurable performance and resource risks. Use when reviewing algorithmic cost, hot paths, allocations, repeated work, blocking I/O, N+1 behavior, memory lifetime, rendering loops, startup time, latency, copying, or serialization.
---

# Performance Audit

## Workflow

1. Identify the review scope and the workloads that matter.
2. Read local performance requirements, benchmarks, profiles, and framework guidance.
3. Find hot paths, repeated paths, scale-sensitive loops, and expensive boundaries.
4. Estimate cost from call frequency, input size, allocation behavior, and I/O count.
5. Run the narrowest useful benchmark or profiler when the repository supports one.
6. Separate proven problems from strong static evidence and speculative possibilities.
7. Recommend the smallest coherent correction that removes material cost.

## Routing Boundaries

- Use this skill for execution time, throughput, latency, allocation, memory, I/O, and scale costs.
- Use `correctness-reliability-audit` when a timeout, race, leak, or retry changes behavior or recovery.
- Use `code-quality-audit` when the concern is readability without a material runtime cost.
- Use `dependency-auditor` when dependency size or health is the primary concern.

## Audit Criteria

Check for:

- Algorithms whose time or memory growth conflicts with expected input size.
- Allocations, boxing, closures, reflection, or object churn inside hot loops.
- Repeated queries, parsing, serialization, copying, sorting, or recomputation.
- Blocking calls on latency-sensitive, update, render, request, or asynchronous paths.
- N+1 database, network, file, or component work.
- Unbounded caches, queues, buffers, collections, or retained object graphs.
- Resources that remain alive longer than their useful lifetime.
- Excessive startup work, eager initialization, or repeated asset loading.
- Render or update work that does not depend on changed state.
- Concurrency that adds contention, scheduling cost, or duplicated work.

## Evidence Rules

- Use high confidence for a profile, benchmark, measurement, or complete cost trace.
- Use medium confidence for strong static evidence, such as N+1 I/O or quadratic work on an expected large input.
- Put low-confidence possibilities under blind spots. Do not block the audit on them.
- Do not recommend a micro-optimization without a plausible workload and material cost.
- Preserve clear code when an optimization has no evidence-based benefit.

## Output Contract

Lead with findings in impact order:

- `P1`: The cost can break a required latency, memory, frame-time, or throughput limit.
- `P2`: The cost is material on a known or clearly implied workload.
- `P3`: The cost is smaller but supported by a repository requirement or measurement.

For each finding, include confidence, a tight file and line reference, the workload, the cost mechanism, evidence, and a concrete correction.

If no actionable findings exist, say so. Name the paths inspected, measurements or checks, and blind spots.

## Correction Guidance

If fixes are authorized, preserve behavior and add a focused benchmark or performance regression check when practical.

Do not trade clear ownership or correctness for an unmeasured speed claim.
