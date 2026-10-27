# Independent correctness and release review

Reviewed 2026-10-26. Implementation was read only for this reviewer. Builder changes occurred during the review; final verification below uses the updated source captured in `review-source-sha256.json`.

## Reviewed scope

- Python-to-Rust lowering, generated Python wrappers and package metadata, build artifact hashes, and fail-closed source restrictions.
- Differential oracle, worker protocol, declared API/result validation, reference-only challenge selection, minimization and replay.
- CLI paths, contract discovery/loading, coding-agent acceptance snapshots, Studio rendering/serving, repository tests, and current contract/integration/security documentation.

## Findings and final status

1. **Missing declared API incorrectly accepted: fixed and independently rechecked.** Two modules exporting only `other` originally received `compatible` for a declared `energy` function because equal `getattr` failures were counted as equivalent subject exceptions. Final reproduction produces `error` with `api_error`. Evidence: `missing/evidence-final/report.json`.
2. **Invalid declared keyword parameter incorrectly accepted: fixed and independently rechecked.** Identical `energy(items)` functions originally passed a contract declaring parameter `values`, including three matching unexpected-keyword failures. Final reproduction produces `error` with `invalid_reference_contract`. Evidence: `invalid-parameter/evidence-final/report.json`.
3. **Compiler exception shadowing changed behavior: fixed and independently rechecked.** A module defining `ValueError` could previously lower a call through that function to the builtin Rust/Python exception. Current generation rejects the source before artifact creation. The builder added local/parameter shadow rejection as well.
4. **Generated backend name could shadow a valid parameter: fixed and independently rechecked.** `energy(_native)` previously generated `_native.energy(_native)`, accessing the input list as a module. Current generation chooses a noncolliding backend name; reproduced wrapper uses `_morphproof_native_module.energy(_native)`.
5. **Malformed contract JSON produced uncaught CLI tracebacks: fixed and independently rechecked.** Top-level arrays, null function entries, and null names now exit 2 with concise `morphproof:` validation errors.

No remaining consequential correctness finding was identified in the reviewed source. This is a bounded review, not proof of absence of defects.

## Checks and evidence

- `work/venv/bin/python -m pytest outputs/MorphProof/tests -q`: **35 passed, 12 subtests passed**, 4.64 seconds in the final run. An earlier baseline was 24 tests plus 5 subtests; fixes added coverage during review.
- Independently authored reproductions are retained under `work/review/`: `missing`, `invalid-parameter`, `invalid-return`, `exception-shadow`, `reserved`, and `bad-contract`.
- Final missing-API and invalid-parameter runs each used budget 2 and a fresh evidence directory, avoiding reuse of earlier reports.
- Final malformed-contract CLI checks returned exit 2 for all three malformed input shapes.
- `review-source-sha256.json` records exact SHA-256 identities for reviewed package source, tests, package metadata, documentation, and security guidance. Any later change requires proportionate rechecking of that change.

## Material limits

- Tests ran locally on macOS using the task's Python environment. This reviewer did not independently run Linux or Windows CI, install the generated native wheel, benchmark performance, validate publication, or inspect credentials.
- Native/package end-to-end verification was being performed separately by the builder. Source inspection of package layout is not evidence of a successful wheel installation.
- The agent handoff checksum file is advisory against accidental drift. Current documentation accurately states that a process able to alter both acceptance data and hashes can bypass it; it is not hostile-agent isolation.
- Source/artifact hashes and subprocess response limits do not provide filesystem/network/memory isolation or freeze undeclared imported dependencies. Current documentation states those boundaries.
- Finite differential results establish only observed compatibility under the declared sampling conditions. They do not establish universal equivalence or a formal proof.
