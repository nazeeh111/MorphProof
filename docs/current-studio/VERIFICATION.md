# Current verification and limits

The local checks use Python 3.12.13 on macOS ARM64 and the current source. The original Rust toolchain pin, compiler, verifier, minimizer, reports and recorded native artifacts are unchanged. The interface repair raises the desktop section-number contrast and makes the highlighted section follow anchor navigation and browser history.

## Executed checks

- The complete original pytest collection passes **37 tests and 12 subtests**. No original assertion was changed. Unittest discovery alone covers only 35 tests and is not the complete gate.
- Chromium, Firefox and WebKit each passed actual Studio input workflows at 1280 and 320 pixels: attempt selection, desktop section links and history, keyboard code tabs, function filtering, report download, restoration selection and reload. All six workflows fit horizontally and reported no page errors.
- A separate native Chrome session checked both attempts at 1280, 390 and 320 pixels: six accessibility scans reported zero violations and zero incomplete checks. Actual navigation/back/forward, code-tab arrows, filtering and download/reload also passed. These checks are not a complete assistive-technology audit.
- The downloaded selected report preserves every parsed JSON field of the failed report. Serializer formatting and numeric spelling differ, so the exported bytes are not claimed to be identical.
- The published worked-example ZIP was extracted to a fresh directory, with all 99 manifest members hash-checked. Actual recorded native replay produced Python **1.0**, faulty Rust **0.0** and restored Rust **1.0** for `[1.0]`. Every saved failure replayed against the restored native candidate.

A wheel and source distribution were also built. A fresh isolated wheel installation exercised inspection, contract discovery, source-only generation, mismatch/restored verification, Studio rendering and saved-failure replay. Existing-output and unsupported-source refusals preserved prior files. Those fresh challenge cases use Python candidates; source-only generation is not native compilation.

[Capture provenance](CAPTURES.md) identifies the exact views. The original native compilation record used Rust 1.100.0 and Python 3.12; its wheel tag does not establish compatibility on every admitted platform. The unchanged repository pin is Rust 1.99.1. No fresh local Rust build, timing experiment, autonomous repair trial or selector study was performed for this presentation repair.

## Reproduce the core checks

```sh
python -m pip install -e '.[test]'
python -m pytest -q
```

The existing CI workflow separately includes the Python matrix and native transformations on Linux, macOS and Windows. Consult the actual workflow run for the source revision being reviewed; local browser checks are not part of that workflow.

## Boundaries

Finite tests establish observations within the recorded contract and budget, not universal equivalence or global counterexample minimality. The viewer does not execute uploaded transformations and has no running-job cancellation control. Narrow browser viewports are not physical-device acceptance. Source execution is for trusted code only; separate processes do not provide a security sandbox. Historical evidence is retained rather than relabeled as a new build or measurement.
