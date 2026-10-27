# Recorded coding-agent repair

The installed Codex CLI was invoked through its existing local configuration, with the workspace-write sandbox and no model override. It changed only the candidate Rust loop, removing the disclosed `.skip(1)` seed mutation. It was asked not to build or test. MORPHPROOF then rebuilt independently, replayed the saved failures, and ran a fresh seed97 campaign. No model API key was supplied by this project. This is one repair case study, not a benchmark of agent migration success.

Changed only [src/lib.rs:27](<candidate>/src/lib.rs:27):

```diff
-    for mp_item in values.iter().copied().skip(1) {
+    for mp_item in values.iter().copied() {
```

Removing `.skip(1)` includes the first value, restoring Python’s ordered sum of every item’s square. A single nonzero item now contributes its square instead of returning zero.

Source change verified by inspection. No build or tests run, as requested.
