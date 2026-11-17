MORPHPROOF: TRUSTED SYNTHETIC NATIVE WITNESS

This is an extracted worked artifact, not a repository checkout. All local paths
below are relative to this directory. No download-self link or external figure
manifest is needed to reopen it.

1. Verify the included bytes and replay the recorded native witness:

   python3.12 -I -B reopen.py

   Requires CPython 3.12 on macOS ARM64 for the included native snapshots.
   No Rust compiler, model, network service or package installation is needed.
   Only execute this known-source synthetic code. Process separation is not a
   filesystem or security sandbox. Review the source before execution.

2. Open the recorded Studio in a browser:

   repaired/studio.html

   This is a portable evidence viewer, not a running transformation editor.
   Select the deliberately seeded and restored attempts, inspect source and
   counterexamples, or export the selected report. No code-upload route exists.

INCLUDED LOCAL ENTRYPOINTS
- reopen.py
- MANIFEST.json
- kernel.py
- contract.json
- initial.rs
- repaired.rs
- failed/report.json
- failed/counterexamples.json
- failed/tested-cases.json
- repaired/report.json
- repaired/studio.html
- native/initial/candidate.py
- native/restored/candidate.py
- runtime/morphproof/oracle.py
- kernel_morphproof-0.1.0-cp310-abi3-macosx_11_0_arm64.whl
- LICENSE.txt
- DEPENDENCIES.md
- notices/

WHAT THE CASE SHOWS
The initial Rust loop has a deliberately inserted .skip(1). This is a synthetic
fault, not an original compiler defect. On [1.0, -1.0], Python returns 2.0 and
seeded Rust returns 1.0. Five bounded minimization calls retain [1.0], giving
Python 1.0 / seeded Rust 0.0. The restored native artifact returns 1.0.

The failed campaign records 32 positional comparisons with 17 differences,
plus 3 keyword checks with 1 difference. Deterministically restoring the loop
and using seed 97 records 64 positional comparisons and 3 keyword checks with
no observed difference. Each campaign contains 27 unique positional inputs.
These are finite observations, not universal equivalence, global minimality,
autonomous repair, adaptive-selection advantage or a performance measurement.
The maximum generated length 32 is a test-generation bound, not a runtime guard.

TOOLCHAIN, PLATFORM AND IDENTITIES
The actual build used Rust/cargo 1.100.0, PyO3 0.27.2, Python 3.12.13 and Maturin
1.16.0. The repository's Rust 1.99.1 pin was unchanged and was not exercised.
The wheel was separately built and tested on macOS ARM64/Python 3.12. Its abi3
tag does not establish every interpreter/platform. Other platforms must rebuild
from source with an explicitly stated toolchain; a new binary hash may differ.

MANIFEST.json hashes every included payload except itself. reopen.py checks
those hashes, calls the recorded native artifacts and replays all saved failures
against the restored candidate. The original report paths are provenance, not
required locations. Each native attempt retains its original nine declared
artifact identities. This replay does not compile a new artifact or re-establish
the original campaign under another compiler. No benchmark or study is rerun.

NOTICES AND EXTERNAL PROVENANCE
Preserve LICENSE.txt, DEPENDENCIES.md and all 37 Cargo notice payloads in notices/
with redistributed native artifacts. The original replay engine and synthetic
source retain the included MIT notice; dependency notices retain their licenses.

The full owning source, compiler and historical experiments are external:
https://github.com/nazeeh111/MorphProof/tree/80a0daaf3eec332642159971ac33b8c59e3d0eaf
The complete pinned source is needed for a fresh transformation/build. The
repository presentation figure manifest remains external because it hashes the
ZIP itself. The local member manifest above is sufficient for extracted bytes.
