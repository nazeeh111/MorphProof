# MORPHPROOF launch demonstration

`morphproof-demo-v2.mp4` is a silent 26.5-second, 1280×720 walkthrough edited from actual Studio screenshots. The initial off-by-one defect was deliberately injected into the Rust implementation for this demonstration. The verifier independently discovered and minimized failures, including `[1]`, for which Python returned `1.0` and the faulty candidate returned `0.0`. After an agent repair, a fresh run recorded 768 positional comparisons and 9 keyword API checks with no observed mismatch.

The selected performance result is `sum_squares` on 100,000 floats: 1.96× locally, including Python-to-Rust argument conversion. Results vary by function and input size; one small-input case was slower. The clip does not claim universal equivalence or that the adaptive selector beats the baselines.

The walkthrough uses settled screenshot holds and editorial dips to black. It is not a real-time recording of compilation, agent execution or test speed. The original screenshots and evidence hashes are in `launch-v2/provenance.json`; source reports are in `examples/demo/`. No external audio, stock imagery, billed API, external font or synthetic UI result is used.

Re-edit the retained captures with:

```sh
python experiments/make_video.py --assets docs/media/launch-v2 --output docs/media/my-new-cut.mp4
```

FFmpeg and ffprobe must be on `PATH`. The script accepts `--font` for a local TrueType font, refuses an existing output path, stages rendering separately, validates dimensions/duration/no audio, and fully decodes the result before publishing the local file.

To capture fresh Studio states, serve the real repaired run, install the free Playwright development package, and run `experiments/record_demo.cjs` with a new capture directory. The original captures were made through Codex CUA Chrome controls. Keep the disclosed defect and measurement qualifiers visible in derivative edits.

The selected master is `morphproof-demo-v2.mp4`. Use v2 for release; earlier edits are kept outside the public deliverable.
