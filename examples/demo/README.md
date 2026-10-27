# Retained native demonstration

This is an explicitly seeded off-by-one compatibility defect, not an organically
observed model error. `initial.rs` skips one value; `repaired.rs` contains the actual
Codex repair. The independent verifier discovered smaller failing inputs without
using candidate outputs in test selection. The agent was asked not to build/test;
MORPHPROOF rebuilt and verified separately.

- `failed/`: 384 positional comparisons,9 keyword checks,50+1 mismatches, minimized counterexamples and replay.
- `repaired/`: fresh seed97,768 positional comparisons,9 keyword checks,zero mismatches; portable Studio HTML.
- `repair.patch`: exact Rust change.
- `benchmark.json`: all repeated native API timings, including conversion overhead.
- `agent-repair.md`: actual coding-agent invocation case study.

Historical report paths identify the original local execution. Snapshots and
source/native hashes are retained; the native binary is platform-specific and
is rebuilt from source. Imported dependencies are not universally frozen.
To regenerate in a new folder:

```sh
python experiments/reproduce_demo.py -o runs/demo
```

The reproduction deterministically restores pre-mutation source, requiring no model.
It does not pretend to reproduce the historical agent's reasoning or timing.
