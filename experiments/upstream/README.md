# Independently selected upstream function fixtures

These are small function-level compatibility fixtures from two real open-source projects. They are **not** full-package migrations or a representative migration benchmark. Source selection was based on numerical API relevance, separately from the core verifier implementation and before reviewing its generated candidates.

| Project | Retained revision | Selected API | License |
| --- | --- | --- | --- |
| more-itertools | `4aeb4338ae1407d8da9723e86da99efeb446f719` | `recipes.sum_of_squares` | MIT, copyright Erik Rose |
| boltons | `d31d821d56c8f7756af9c30a864077f2e5855321` | `statsutils.mean` | BSD-3-Clause, copyright Mahmoud Hashemi |

The original modules and upstream LICENSE files are retained byte for byte. [provenance.json](provenance.json) records their immutable source URLs and SHA-256 checksums. The two `*_reference.py` files are new MORPHPROOF adapters, not upstream source. They load the original modules and forward one list argument. The admitted experiment domain is lists containing Python floats. Other upstream input types and APIs are outside the experiment's claim.

`more_itertools_reference.py:sum_of_squares` retains the original result, including integer `0` for empty input. Current upstream delegates to `math.sumprod` on Python 3.12 and later, with a fallback on older Python versions. It is not equivalent to an arbitrary left-fold Rust floating-point sum on every input.

`boltons_reference.py:mean` uses the upstream default `0.0` for empty input and retains the upstream `sum(data, 0.0) / len(data)` result for nonempty data. Python's summation algorithm varies by runtime version. A list such as `[1e16, 1.0, -1e16]` can reveal a naive accumulator's cancellation bug on modern Python.

Keep runtime version and original hashes in each experimental record. Do not rewrite these source files to make a candidate pass. Inspect the license files before redistributing these retained bytes.
