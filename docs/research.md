# Research foundations and scope

Research reviewed on 2026-10-26. This document separates source-reported capabilities from MORPHPROOF's design decisions. It is a focused engineering review, not an exhaustive systematic literature review or a claim of first invention. Upstream links can change; retained experiment sources must be versioned separately.

## What the earlier work already establishes

[Harvest Agentic Translator](https://github.com/UW-HARVEST/harvest-agentic) translates C projects into Rust through staged coding-agent work. Its README describes external grading against GoogleTest suites derived from upstream C tests. This is a useful precedent for separating the implementation agent from acceptance evidence. It does not establish Python API preservation, nor do its reported C migration results transfer automatically to this project.

[RustPrint, Documentation-Guided Agentic Codebase Migration from C to Rust](https://arxiv.org/abs/2605.14634v3), by Minh Le-Anh and colleagues, uses architecture-aware documentation as a migration blueprint, checks output documentation, translates source tests, and uses runtime failures for repair. The cited version is v3, May 22, 2026. Its paper reports repository-level C-to-Rust experiments. Those reported results were not replicated here. The transferable idea is to preserve architectural intent, but generated documentation is supporting context rather than an independent behavioral oracle.

[C2Rust cross-checking](https://github.com/immunant/c2rust/blob/master/docs/cross-check-tutorial.md) instruments original and translated programs and compares execution traces. Its tutorial also describes nondeterminism as a source of interference. Migration validation by differential execution predates current coding agents.

[Syzygy](https://syzygy-project.github.io/) combines code/test generation with dynamic analysis and mines properties and input/output specifications from executions. Its argument translation and test translation illustrate how representation mapping becomes part of the trusted checking surface. MORPHPROOF should therefore keep its observation codec small and inspectable.

[RustAssure](https://arxiv.org/abs/2510.07604), by Yubo Bai and Tapti Palit, explicitly studies differential symbolic testing for LLM-transpiled C-to-Rust code. Symbolic comparison and a generate/test/repair loop are established prior work, not claims of novelty for MORPHPROOF.

[py2many](https://github.com/py2many/py2many) already transpiles Python to multiple languages, including Rust. A useful new product cannot be justified simply by emitting Rust from Python. Its value must come from supported semantics, independent challenge generation, reproducible evidence, and a workflow developers can actually use.

## Mature components and deliberate omissions

| Technology | Useful contribution | Decision for a bounded implementation |
| --- | --- | --- |
| [Hypothesis](https://hypothesis.readthedocs.io/en/latest/quickstart.html) | Python strategies, generated inputs, and minimized failing examples | Reuse as an optional testing component or a strong evaluation baseline. Compare actual executions rather than merely configured example limits. |
| [CrossHair](https://crosshair.readthedocs.io/en/latest/limitations.html) | Searches for violations of Python contracts using symbolic proxy values | Optional analysis for explicitly supported Python properties. Its documentation says no counterexample is not a guarantee, limits analysis to deterministic behavior, and warns that code actually executes. Native-extension behavior is not automatically a symbolic proof. |
| [PyO3](https://github.com/PyO3/pyo3) | Rust bindings for Python and native extension interfaces | Prefer mature bindings where dependencies are feasible; document conversions, Python version support, exceptions, and integer/float behavior. |
| [Maturin](https://github.com/PyO3/maturin) | Builds Rust-backed Python packages | Prefer a reproducible wheel build route when using PyO3. A successful Rust compile alone is insufficient: install the wheel into a fresh Python environment and call the public API. |
| [Tree-sitter](https://github.com/tree-sitter/tree-sitter) | Incremental parsing across languages | Useful for future cross-language inspection. Python's built-in `ast` is a smaller dependency for an initial Python-only discovery pass. Parsing is not semantic verification. |
| [PaperVizAgent](https://github.com/google-research/papervizagent) | Research-oriented visual generation workflow | Investigated, not required at runtime. Its quickstart configures model API keys or cloud settings. Repository-native diagrams avoid requiring a separately billed model service for this delivery. |

No dependency should be adopted solely because it appears in this table. Actual use, versions and licenses belong in the dependency and attribution records.

## A feasible supported contract

Start with deterministic Python numerical functions on explicitly declared scalar and list inputs, with a Rust-backed Python implementation behind the same declared function interface. Treat the contract as a frozen experiment artifact. Include argument names/defaults where supported, normal results, result types, exceptions, special floating-point values, and the admitted input domain.

Python-to-Rust semantic hazards are the main product opportunity: arbitrary-precision integers versus bounded integers, Python `sum` behavior, floating-point cancellation, NaN and signed-zero handling, sequence boundaries, return-type changes, exception class/message differences, truncating `zip`, and mutation. A type hint does not eliminate these hazards or define all permitted inputs by itself.

Only claim preservation for the declared supported surface. Native callbacks, arbitrary objects, generators, identity, global state, concurrency, I/O and undefined package behaviors require separate contracts and may be unsupported. Process separation and timeouts provide failure containment; they are not a security sandbox for hostile repository code.

## The defensible contribution

The contribution to evaluate is an inspectable, source-guided adaptive challenge selector for Python API compatibility. It can combine:

1. Structural hints from the original function, such as comparisons, constants, loops, reductions and indexing.
2. A shared pool of ordinary, boundary, invalid, special-float and structured sequence inputs.
3. Behavioral novelty observed from the reference implementation, such as a newly observed exception or result category.
4. A transparent exploration policy that revisits productive input families without eliminating less-observed families.
5. Differential checking and reduction of failing inputs into smaller reproducible counterexamples.

This is an engineering contribution assembled from established methods. Calling it adaptive requires scores or choices to change from observations; a fixed edge-case list should be called boundary testing. Calling it learned requires an actual training procedure and evaluation on separate held-out tasks. A deterministic heuristic is preferable unless experiments support the added learned-model complexity.

The generation agent may receive counterexamples for repair. It must not be able to edit the reference snapshot, domain, observation rules or final acceptance threshold as part of its candidate patch. Hashes make changes detectable, but are not access control or protection against a malicious agent running with the same operating-system privileges.

## Evaluation that can answer the research question

Use equal *observed execution* budgets. Count the original and candidate calls consistently across strategies, include timeout and crash outcomes, and disclose source-analysis/pool-construction overhead. Keep minimization executions separate from discovery-budget results. For sequential searches, report failures found by each budget and execution count to first counterexample. Multiple seeds should use the same task collection and budget accounting.

Compare against at least seeded random inputs, fixed boundary/ordinary unit-style cases, a nonadaptive sampler over the same input pool, and Hypothesis when available. A same-pool random baseline and an ablation that disables adaptation distinguish the adaptive policy from merely having good boundary inputs. Retain failures against the adaptive method too. An ordinary-agent migration baseline requires actual independently generated migrations and their costs; a synthetic mutant set is not a substitute.

Separate development examples from held-out implementations and fault families. Record how each known defect was selected and check it is reachable in the declared domain. Include unchanged implementations to estimate false positives. A generated counterexample should be replayed against the immutable reference before counting it as a defect. Do not count every mismatching input as a different bug.

Two independently selected open-source sources with suitable small numerical APIs are:

- [boltons `mathutils.clamp`](https://github.com/mahmoud/boltons/blob/master/boltons/mathutils.py). It validates bound order and otherwise composes Python `min`/`max`. This exposes bounds, type preservation and special-float behavior. BSD-3-Clause.
- [more-itertools recipes](https://github.com/more-itertools/more-itertools/blob/master/more_itertools/recipes.py), including `dotproduct` and `sum_of_squares`. `dotproduct` uses `sum(map(mul, ...))`; current `sum_of_squares` instead dispatches to `math.sumprod` on Python 3.12 and later. Precision, empty-result type and unequal-length behavior matter. MIT; the module identifies its Python itertools-recipes lineage.

The retained experiments use `boltons.statsutils.mean` and `more_itertools.recipes.sum_of_squares`, with exact source and licenses in [upstream fixtures](../experiments/upstream/README.md). The former preserves an empty default and runtime-specific summation. These were selected by source inspection for numerical API relevance, not demonstrated as full-package migrations. If used experimentally, pin the original source revision, retain applicable notices, declare adapter/domain restrictions, and distinguish translated functions from entire projects. Independently choosing projects is also different from independently writing candidate implementations.

Report transformation success and compatibility outcomes separately from performance. Time both public Python interfaces after warmup with the same data, retain repeated raw measurements, state environment/build settings and input sizes, and disclose conversion overhead. A Rust kernel speedup does not imply the whole application became faster. Maintainability measurements should identify the metric and its limits instead of assigning an unexplained quality score.

## What a passing report means

A passing finite campaign means no mismatch was observed for its recorded cases under its recorded comparison policy. It does not prove universal equivalence. A formal claim needs its own explicit property, model, assumptions and proof-producing tool evidence. Untested API features, skipped examples, unavailable tools and reference failures must remain visible in the report.
