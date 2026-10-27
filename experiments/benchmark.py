"""Time the actual Python API including native argument conversion."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import platform
import random
import statistics
import sys
import time


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def benchmark(reference,candidate,output,sizes=(16,1024,100000),repeats=11,iterations=30):
    output=Path(output)
    if output.exists(): raise ValueError('Choose a new benchmark output')
    ref=load(reference,'_bench_reference'); cand=load(candidate,'_bench_candidate')
    rng=random.Random(2147); rows=[]
    for size in sizes:
        values=[rng.uniform(-10,10) for _ in range(size)]
        for function in ('sum_squares','mean','positive_energy'):
            a,b=getattr(ref,function),getattr(cand,function)
            if a(values)!=b(values): raise RuntimeError('Benchmark candidate differs: '+function)
            for _ in range(5): a(values);b(values)
            timings={'python':[],'rust':[]}
            for repeat in range(repeats):
                for label,fn in ([('python',a),('rust',b)] if repeat%2==0 else [('rust',b),('python',a)]):
                    start=time.perf_counter_ns()
                    for _ in range(iterations): fn(values)
                    timings[label].append((time.perf_counter_ns()-start)/iterations)
            py=statistics.median(timings['python']); rs=statistics.median(timings['rust'])
            rows.append(dict(function=function,length=size,python_median_ns=py,rust_median_ns=rs,speedup=py/rs,raw_ns=timings))
    result=dict(schema=1,python=sys.version,platform=platform.platform(),machine=platform.machine(),repeats=repeats,iterations=iterations,reference_sha256=hashlib.sha256(Path(reference).read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256(Path(candidate).read_bytes()).hexdigest(),protocol='Same preallocated list, includes full Python-to-Rust Vec extraction and wrapper dispatch; 5 warmups; alternating order; median of 11 repeated batches; no tracing or IPC in timed calls; no universal speedup claim.',rows=rows)
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(result,indent=2)+'\n'); return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('reference',type=Path);p.add_argument('candidate',type=Path);p.add_argument('-o','--output',type=Path,required=True);a=p.parse_args(); print(json.dumps(benchmark(a.reference,a.candidate,a.output),indent=2))
