# Generated Rust-backed kernels package

This is the complete generated source for the supported example. The Rust source
matches the repaired demonstration. Build a distributable wheel:

```sh
python -m pip install maturin
maturin build --release -o wheels
```

Install the resulting platform wheel and `import kernels`. For file-based oracle
verification before installation, run `morphproof.transform.build_candidate` on
this directory to compile and refresh native artifact hashes. No prebuilt binary
is committed here. The release contains the core MORPHPROOF wheel and a macOS
ARM64 example wheel; other platforms should build their own candidate wheel.
