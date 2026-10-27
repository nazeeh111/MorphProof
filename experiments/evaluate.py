"""Reproducible, budget-matched selector study. Run from repository root.

Fixtures are synthetic behavioral differences, plus two independently chosen
upstream functions. No outcome is a mathematical equivalence proof.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import random
import statistics
import sys
import tempfile
import time

from morphproof.inputs import Selector
from morphproof.oracle import Worker, equivalent
from morphproof.worker import encode

REFERENCE = '''def reduce(values):
    if len(values) == 0:
        raise ValueError("empty input")
    total = 0.0
    for value in values:
        if value > -3.0:
            total = total + value
    return total / len(values)
'''
# Authored evaluation fixtures, separate from the development examples.
# They are known behavioral differences, not a statistically independent corpus.
MUTATIONS = {
    'empty-return': REFERENCE.replace('raise ValueError("empty input")', 'return 0.0'),
    'exception-message': REFERENCE.replace('empty input', 'cannot divide'),
    'off-by-one': REFERENCE.replace('for value in values:', 'for value in values[:-1]:'),
    'threshold-inclusive': REFERENCE.replace('value > -3.0', 'value >= -3.0'),
    'threshold-zero': REFERENCE.replace('value > -3.0', 'value > 0.0'),
    'absolute-values': REFERENCE.replace('total + value', 'total + abs(value)'),
    'mean-denominator': REFERENCE.replace('total / len(values)', 'total / (len(values) + 1)'),
    'float32-rounding': REFERENCE.replace('return total / len(values)', 'return float(__import__("ctypes").c_float(total / len(values)).value)'),
    'nan-shortcut': REFERENCE.replace('total = 0.0', 'total = 0.0\n    if any(value != value for value in values):\n        return float("nan")'),
    'overflow-clamp': REFERENCE.replace('return total / len(values)', 'return min(total / len(values), 1e100)'),
    'length-31': REFERENCE.replace('return total / len(values)', 'return total / len(values) + (1.0 if len(values) == 31 else 0.0)'),
    'tiny-flush': REFERENCE.replace('total + value', 'total + (0.0 if abs(value) < 1e-200 else value)'),
    'reverse-order': REFERENCE.replace('for value in values:', 'for value in values[::-1]:'),
    'negative-zero': REFERENCE.replace('return total / len(values)', 'return -0.0 if total == 0.0 else total / len(values)'),
    'length-17': REFERENCE.replace('return total / len(values)', 'return total / len(values) + (1.0 if len(values) == 17 else 0.0)'),
    'equivalent-control': REFERENCE,
}
UNIT_CASES = [[], [0.0], [1.0], [-1.0], [1.0,2.0,3.0], [-4.0,-3.0,-2.0]]


def trial(refpath, candpath, function, source, method, budget, seed):
    reference, candidate = Worker(refpath), Worker(candpath)
    calls, first, errors = 0, None, 0
    started = time.perf_counter()
    def probe(values):
        nonlocal calls, first, errors
        calls += 1
        a = reference.call(function, values, trace=method=='adaptive')
        b = candidate.call(function, values)
        if any(o['outcome']['kind'] not in {'return','exception'} for o in (a,b)):
            errors += 1
        elif not equivalent(a['outcome'], b['outcome']) and first is None:
            first = calls
        return a
    try:
        if method == 'hypothesis':
            from hypothesis import given, settings, strategies as st, seed as hseed, Phase, HealthCheck
            @hseed(seed)
            @settings(max_examples=budget, database=None, deadline=None, phases=[Phase.generate], suppress_health_check=[HealthCheck.too_slow])
            @given(st.lists(st.floats(width=64, allow_nan=True, allow_infinity=True), max_size=64))
            def check(values):
                probe(values)
            check()
        elif method == 'unit':
            for i in range(budget):
                probe(UNIT_CASES[i % len(UNIT_CASES)])
        else:
            selector = Selector(source,max_length=64,seed=seed,strategy='adaptive' if method in {'no-feedback','pool-random'} else method)
            for _ in range(budget):
                case=selector.pool.pop(selector.rng.randrange(len(selector.pool))) if method=='pool-random' else selector.next()
                observed=probe(case.values)
                if method not in {'no-feedback','pool-random'}: selector.observe(case,observed)
    finally:
        reference.close(); candidate.close()
    return dict(method=method,seed=seed,budget=budget,calls=calls,detected=first is not None,first_detection=first,errors=errors,seconds=time.perf_counter()-started)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,default=Path('experiments/results.json')); p.add_argument('--seeds',type=int,default=10); p.add_argument('--budgets',type=int,nargs='+',default=[8,32,128]); p.add_argument('--skip-upstream',action='store_true'); p.add_argument('--methods', nargs='+', default=['adaptive','no-feedback','random','boundary','uniform','unit','hypothesis']); p.add_argument('--selector-source',type=Path,help='Optional frozen selector source, e.g. experiments/selector-v1.py'); a=p.parse_args()
    global Selector
    if a.selector_source:
        spec=importlib.util.spec_from_file_location('morphproof_study_selector',a.selector_source)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);Selector=module.Selector
    if a.output.exists(): raise SystemExit('Choose a new output path to preserve prior evidence')
    methods=a.methods
    rows=[]
    selector_path=a.selector_source or Path(__import__('morphproof.inputs',fromlist=['x']).__file__)
    selector_hash=hashlib.sha256(selector_path.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='morphproof-study-') as td:
        td=Path(td); ref=td/'ref.py'; ref.write_text(REFERENCE)
        for name, source in MUTATIONS.items():
            cand=td/(name+'.py'); cand.write_text(source)
            for budget in a.budgets:
                for seed in range(a.seeds):
                    for method in methods:
                        row=trial(ref,cand,'reduce',REFERENCE,method,budget,seed)
                        rows.append(dict(fixture=name,group='synthetic',is_control=name=='equivalent-control',**row))
            print(name,flush=True)
            a.output.with_suffix('.partial.json').write_text(json.dumps(rows))
        if not a.skip_upstream:
            upstream=Path(__file__).parent/'upstream'
            for project,function,body in [('more_itertools','sum_of_squares','total = 0.0\n    for value in values:\n        total = total + value * value\n    return total'),('boltons','mean','if not values:\n        return 0.0\n    total = 0.0\n    for value in values:\n        total = total + value\n    return total / len(values)')]:
                ref=upstream/(project+'_reference.py')
                cand=td/(project+'_naive.py'); cand.write_text('def '+function+'(values):\n    '+body+'\n')
                for budget in a.budgets:
                    for seed in range(a.seeds):
                        for method in methods:
                            row=trial(ref,cand,function,ref.read_text(),method,budget,seed)
                            rows.append(dict(fixture=project+'-naive-fold',group='upstream',is_control=False,**row))
                print(project,flush=True)
    summary=[]
    for group in ['synthetic','upstream']:
        for budget in a.budgets:
            for method in methods:
                selected=[r for r in rows if r['group']==group and r['budget']==budget and r['method']==method and not r['is_control']]
                if not selected: continue
                controls=[r for r in rows if r['group']==group and r['budget']==budget and r['method']==method and r['is_control']]
                summary.append(dict(group=group,budget=budget,method=method,trials=len(selected),detections=sum(r['detected'] for r in selected),rate=sum(r['detected'] for r in selected)/len(selected),false_positives=sum(r['detected'] for r in controls),control_trials=len(controls),errors=sum(r['errors'] for r in selected),seconds=sum(r['seconds'] for r in selected)))
    result=dict(schema=1,python=sys.version,platform=platform.platform(),seeds=a.seeds,budgets=a.budgets,reference_sha256=hashlib.sha256(REFERENCE.encode()).hexdigest(),selector_sha256=selector_hash,protocol='Fixed candidate-call budgets; no shrinking. Adaptive traces only reference; no-feedback ablation keeps structural/input novelty but removes reference outcome/coverage rewards. Unit tests repeat 6 ordinary cases; boundary is strong fixed edge-case baseline; random samples same families without prioritization; uniform bounded floats; Hypothesis native float lists generate phase only. Synthetic fixtures are not independent real defects; upstream adapters selected by separate research task. No tuning after results.',limitations=['Small authored mutation suite, not representative migration success.', 'Upstream naive candidates are deliberately simple Python semantic models of Rust folds, not full package translations.', 'No agent-migration aggregate baseline measured; headline repair is a separate case study.', 'Reference source analysis sees wrapper only for upstream, not vendored dependencies.', 'Hypothesis may use fewer distinct cases under max_examples; calls recorded.'],summary=summary,rows=rows)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+'\n')
    for r in summary: print(r)
if __name__=='__main__': main()
