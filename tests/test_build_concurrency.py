"""Verify ownership and failure receipts independently of Cargo availability."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest
from morphproof.transform import _build_lock, _invalidate_build, build_candidate, transform

CONTRACT = {'schema': 1, 'functions': [{'name':'energy','parameter':'values','input':'list[float]','output':'float'}]}

@pytest.fixture
def candidate(tmp_path):
    reference=tmp_path/'reference.py'
    reference.write_text('def energy(values):\n    return values[0] * values[0]\n')
    result=tmp_path/'candidate with spaces'
    transform(reference,result,CONTRACT,build=False)
    return result

def test_separate_process_owner_blocks_second_build_without_changing_receipts(candidate):
    receipt=candidate/'morphproof-build.json'
    receipt.write_text(json.dumps({'schema':1,'built':True,'artifacts':['candidate.py']}))
    manifest=(candidate/'manifest.json').read_bytes(); previous=receipt.read_bytes()
    script='from pathlib import Path; from morphproof.transform import _build_lock; import sys\nwith _build_lock(Path(sys.argv[1])):\n print("locked",flush=True)\n sys.stdin.read(1)\n'
    child=subprocess.Popen([sys.executable,'-c',script,str(candidate)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=os.environ.copy())
    try:
        assert child.stdout.readline().strip()=='locked'
        with pytest.raises(RuntimeError,match='another build'):
            build_candidate(candidate)
        assert (candidate/'manifest.json').read_bytes()==manifest
        assert receipt.read_bytes()==previous
    finally:
        child.communicate(input='x',timeout=10)
    assert child.returncode==0
    with _build_lock(candidate):
        pass
    assert (candidate/'.morphproof-build.lock').is_file()

def test_receipt_invalidated_before_manifest_failure(candidate):
    receipt=candidate/'morphproof-build.json'
    receipt.write_text(json.dumps({'schema':1,'built':True,'artifacts':['candidate.py']}))
    real=Path.write_text
    def fail_manifest(path,*args,**kwargs):
        if path == candidate/'manifest.json': raise OSError('injected write failure')
        return real(path,*args,**kwargs)
    with patch.object(Path,'write_text',fail_manifest),pytest.raises(OSError,match='injected'):
        _invalidate_build(candidate)
    assert json.loads(receipt.read_text())['built'] is False

def test_symlinked_lock_refused_without_touching_link_target(candidate,tmp_path):
    target=tmp_path/'unrelated.txt'; target.write_text('preserve')
    (candidate/'.morphproof-build.lock').symlink_to(target)
    with pytest.raises(RuntimeError,match='lock'):
        build_candidate(candidate)
    assert target.read_text()=='preserve'

def test_transform_does_not_overwrite_later_build_invalidation(tmp_path):
    reference=tmp_path/'reference.py'
    reference.write_text('def energy(values):\n    return values[0] * values[0]\n')
    candidate=tmp_path/'candidate'
    def later_build_already_started(path):
        manifest=path/'manifest.json'
        state=json.loads(manifest.read_text());state['built']=False
        manifest.write_text(json.dumps(state))
        return {'built':True}
    with patch('morphproof.transform.build_candidate',side_effect=later_build_already_started):
        transform(reference,candidate,CONTRACT,build=True)
    assert json.loads((candidate/'manifest.json').read_text())['built'] is False
