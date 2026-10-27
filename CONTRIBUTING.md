# Contributing

Start with a minimal input showing a behavioral discrepancy, or a small supported
kernel that should compile and does not. Include Python/Rust versions, the explicit
contract and the recorded report. Never upload secrets or proprietary source.

```sh
python -m pip install -e '.[test]'
python -m pytest -q
morphproof transform examples/kernels.py --contract examples/contract.json -o runs/check
```

Keep new syntax fail-closed and add tests for consequential semantics. Keep test
selection independent of candidate outputs. Add experiments without replacing
previous evidence and preserve raw measurements. Claims should identify the exact
artifact, domain, budget and platform that support them.
