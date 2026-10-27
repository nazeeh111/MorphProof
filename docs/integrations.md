# Coding agents with independent acceptance

MORPHPROOF does not require a model API key. Its bounded AST backend is deterministic.
For transformations beyond that subset, or targeted repairs, let your existing
coding agent write the candidate and keep verification in a separate process.
The generator does not choose acceptance or edit reference tests.

## Codex

```sh
morphproof prepare-agent examples/kernels.py runs/native \
  --contract examples/contract.json -o runs/agent-task
# Read runs/agent-task/TASK.md; give it to your current Codex session, or:
cd runs/native
codex exec --sandbox workspace-write "Read ../agent-task/TASK.md and repair this candidate. Do not modify acceptance files."
```

Run with your existing supported Codex authentication and permission settings.
The [official non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
describes `codex exec`. MORPHPROOF neither handles credentials nor overrides your
model, permissions, or spending choices. Do not use permission-bypass flags.

Then return to the repository root:

```sh
morphproof check-agent runs/agent-task
morphproof verify runs/agent-task/acceptance/reference.py runs/native/candidate.py \
  --contract runs/agent-task/acceptance/contract.json -o runs/repaired --budget 256
python runs/failed/replay.py runs/agent-task/acceptance/reference.py runs/native/candidate.py
```

When changing Rust, rebuild using `morphproof.transform.build_candidate(Path(...))`
before verification. Loading an old binary is not verification of edited Rust.
`morphproof-build.json` lists native/source files whose hashes the verifier records.

## Claude Code and other agents

Open only the candidate working directory and provide the generated `TASK.md`,
the failed report and counterexamples. The same `check-agent`, `verify` and
`replay.py` commands apply. No model-specific protocol is required. This file
handoff is the supported integration; MORPHPROOF does not invoke Claude Code
or require a separate account.

## Acceptance boundaries

`prepare-agent` copies the reference and contract and records SHA-256 checksums.
`check-agent` detects changes to those snapshots. Verification rejects source or
listed build-artifact changes during a run. This protects against accidental
acceptance drift, not a malicious agent with access to both evidence and hashes.
Use a separate user/container with read-only acceptance mounts for hostile code.
A sibling task folder is organizational isolation, not a security boundary.

Existing repository tests remain valuable. Run them separately in the original
and candidate environments, preserve their commands and outputs, and attach them
to your review. MORPHPROOF does not silently modify or replace your test suite.
