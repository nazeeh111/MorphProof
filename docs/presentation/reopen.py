"""Verify complete bundle bytes and replay this trusted synthetic native witness.
Python3.12/macOS ARM64 is required for the recorded native wrappers; the wheel is
separately tagged abi3 and tested only on Python3.12 here. No Rust build occurs.
"""
from pathlib import Path
import json,hashlib,sys,os
P=Path(__file__).resolve().parent
for name,h in json.loads((P/'MANIFEST.json').read_text()).items():
 if hashlib.sha256((P/name).read_bytes()).hexdigest()!=h:raise ValueError('Changed bundle member: '+name)
sys.path.insert(0,str(P/'runtime'));os.environ['PYTHONPATH']=str(P/'runtime');os.environ['PYTHONDONTWRITEBYTECODE']='1'
from morphproof.oracle import Worker,equivalent,replay_cases
workers=[Worker(P/'kernel.py'),Worker(P/'native/initial/candidate.py'),Worker(P/'native/restored/candidate.py')];reference,initial,restored=workers
try:
 a=reference.call('energy',[1.])['outcome'];b=initial.call('energy',[1.])['outcome'];c=restored.call('energy',[1.])['outcome'];assert a['value']==1. and b['value']==0. and c['value']==1.;assert not equivalent(a,b)and equivalent(a,c)
finally:
 for worker in workers:worker.close()
assert replay_cases(P/'kernel.py',P/'native/restored/candidate.py',P/'failed/counterexamples.json',P/'contract.json')
print(json.dumps({'recorded_native_witness':[a,b,c],'all_saved_failures_replay_against_restored_native':True,'scope':'Trusted synthetic case; current replay checks source/observations, not universal equivalence or a fresh compiler build'},indent=2))
