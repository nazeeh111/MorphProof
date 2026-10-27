"""Rebuild the disclosed seeded-defect demonstration in a new directory.

This reproduction repairs the known seed by restoring pre-mutation source. The
recorded headline separately used the existing Codex CLI; see agent-repair.md.
"""
from pathlib import Path
import argparse
import json
from morphproof.transform import transform, build_candidate
from morphproof.oracle import verify, replay_cases
from morphproof.studio import render_studio


def main():
    p=argparse.ArgumentParser();p.add_argument('-o','--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists(): raise SystemExit('Choose a fresh output directory')
    root=Path(__file__).resolve().parents[1];out=a.output.resolve();contract=json.loads((root/'examples/contract.json').read_text())
    native=out/'native';transform(root/'examples/kernels.py',native,contract,build=False)
    rust=native/'src/lib.rs';correct=rust.read_text();initial=correct.replace('values.iter().copied()','values.iter().copied().skip(1)',1)
    assert initial!=correct
    print('Injecting a disclosed off-by-one defect in the generated sum_squares loop')
    rust.write_text(initial);build_candidate(native)
    failed=verify(root/'examples/kernels.py',native/'candidate.py',contract,out/'failed',budget=128,seed=23)
    assert failed['status']=='incompatible'
    rust.write_text(correct);build_candidate(native)
    repaired=verify(root/'examples/kernels.py',native/'candidate.py',contract,out/'repaired',budget=256,seed=97)
    assert repaired['status']=='compatible'
    assert replay_cases(root/'examples/kernels.py',native/'candidate.py',out/'failed/counterexamples.json',root/'examples/contract.json')
    run={'reference_source':(root/'examples/kernels.py').read_text(),'rust_source':correct,'attempts':[{'label':'Seeded defect','report':failed,'rust_source':initial},{'label':'Restored source, fresh verification','report':repaired,'rust_source':correct}]}
    (out/'repaired/run.json').write_text(json.dumps(run,indent=2)+'\n');print(render_studio(out/'repaired'))
if __name__=='__main__':main()
