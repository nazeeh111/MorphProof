# MORPHPROOF Studio

Studio turns a recorded verification run into a self-contained evidence browser. It runs locally without a frontend build, database, account, external font, or network request.

```python
from pathlib import Path
from morphproof.studio import render_studio, serve

page = render_studio(Path("run"))  # requires run/report.json
print(page)
serve(Path("run"))  # http://127.0.0.1:8765; Ctrl-C to stop
```

Open the generated `studio.html` directly, or use the local server. The server exposes only the HTML page and `report.json`; it does not offer directory browsing or writes. The HTML includes a snapshot of the report, so re-render it after the evidence changes. Source code and input strings are displayed as text, never executed by Studio. Loading the report does not run a candidate.

The interface shows recorded tests, mismatches, additional minimization executions, declared functions, function-specific claims, source code, minimal discovered counterexamples and run provenance. A report without counterexamples does not establish universal equivalence. Untested inputs, APIs and side effects remain explicit.

Optional `run/run.json` enriches the report:

```json
{
  "reference_source": "def sum_squares(values):\n    ...",
  "rust_source": "// Generated Rust source",
  "attempts": [
    {"label": "Initial candidate", "report": {}},
    {"label": "Repaired candidate", "report": {}}
  ],
  "benchmark": {
    "speedup": 1.0,
    "measurement_note": "Replace this illustrative schema with real measurements."
  }
}
```

Each attempt's `report` must be a complete verifier report. `reference_source`, `rust_source` and `benchmark` can also be attached to an individual attempt. A numeric positive `speedup` is shown as a headline only when present. Other benchmark fields appear alongside it; record input size, repeat count, environment and measurement method. Missing source, performance or counterexample data is labeled, not filled in.

Controls support function filtering, attempt selection, keyboard-accessible Python/Rust code tabs, expandable counterexamples and JSON export of the selected report. The layout adapts to narrow screens and respects reduced-motion preferences. Nonfinite numbers are shown as `NaN`, `+Infinity` and `-Infinity` strings in the browser; the original `report.json` remains unchanged.

Studio is an evidence viewer, not a security sandbox. Execute only trusted repository code. Binding to a non-loopback address can expose your report and source to other machines; the default is `127.0.0.1`.

When keyword API checks are recorded, Studio includes them in total tests and incompatibilities and labels their counterexamples separately. Optional native artifact hashes appear individually in provenance. Benchmarks with `rows` containing `function`, `length`, `python_median_ns`, `rust_median_ns`, and `speedup` appear in a compact comparison table; raw timing arrays remain available in the exported evidence rather than filling the interface.
