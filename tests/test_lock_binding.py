"""Lock resolution and compiler/delivery binding controls; no real Cargo needed."""
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

import pytest

builder=importlib.import_module('morphproof.transform')
CONTRACT={'schema':1,'functions':[{'name':'energy','parameter':'values','input':'list[float]','output':'float'}]}
LIBRARY=('_morphproof_native.dll' if sys.platform=='win32' else 'lib_morphproof_native'+('.dylib' if sys.platform=='darwin' else '.so'))

@pytest.fixture
def candidate(tmp_path):
    ref=tmp_path/'source.py';ref.write_text('def energy(values):\n    return values[0] * values[0]\n')
    dest=tmp_path/'candidate with spaces';builder.transform(ref,dest,CONTRACT,build=False);return dest

def fake_cargo(candidate, *, mutate=None, metadata_update=b'resolved lock\n'):
    def run(command,**kwargs):
        if command[1]=='metadata':
            assert '--format-version=1' in command and '--no-deps' not in command
            assert kwargs['env']['CARGO_TARGET_DIR']==str(candidate/'target')
            if metadata_update is not None: (candidate/'Cargo.lock').write_bytes(metadata_update)
            if mutate=='during_resolution': (candidate/'src/lib.rs').write_text('// changed')
            return subprocess.CompletedProcess(command,0,'{}','resolved\n')
        assert command[1]=='build' and '--locked' in command
        library=candidate/'target'/'host'/'release'/LIBRARY;library.parent.mkdir(parents=True,exist_ok=True);library.write_bytes(b'compiled fixture')
        artifact={'reason':'compiler-artifact','manifest_path':str(candidate/'Cargo.toml'),'target':{'name':'_morphproof_native','crate_types':['cdylib'],'src_path':str(candidate/'src/lib.rs')},'filenames':[str(library)]}
        output='\n'.join([json.dumps(artifact),json.dumps({'reason':'build-finished','success':True})])
        if mutate=='after_compile':
            with (candidate/'Cargo.lock').open('ab') as f:f.write(b'changed')
        return subprocess.CompletedProcess(command,0,output)
    return run

def run(candidate,*,mutate=None,metadata_update=b'resolved lock\n'):
    with patch.object(builder.shutil,'which',return_value='cargo-fixture'), \
         patch.object(builder.subprocess,'run',side_effect=fake_cargo(candidate,mutate=mutate,metadata_update=metadata_update)), \
         patch.object(builder.subprocess,'check_output',return_value='toolchain'), \
         patch.object(builder.platform,'platform',return_value='fixture'):
        return builder.build_candidate(candidate)

@pytest.mark.parametrize('prior',[None,b'outdated lock\n'])
def test_resolved_lock_is_selected_before_locked_build(candidate,prior):
    if prior is not None:(candidate/'Cargo.lock').write_bytes(prior)
    result=run(candidate)
    receipt=json.loads((candidate/'morphproof-build.json').read_text())
    assert result['built'] and receipt['sha256']['Cargo.lock']==hashlib.sha256(b'resolved lock\n').hexdigest()

@pytest.mark.parametrize('when',['after_compile','during_copy'])
def test_lock_drift_refuses_before_delivery(candidate,when):
    prior=run(candidate);native=Path(prior['native']);old=native.read_bytes();real=shutil.copy2
    def changed(src,dst,*a,**kw):
        value=real(src,dst,*a,**kw)
        with (candidate/'Cargo.lock').open('ab') as f:f.write(b'changed')
        return value
    with patch.object(builder.shutil,'copy2',side_effect=changed if when=='during_copy' else real):
        with pytest.raises(RuntimeError,match='changed during compilation'):
            run(candidate,mutate='after_compile' if when=='after_compile' else None)
    assert native.read_bytes()==old
    assert json.loads((candidate/'morphproof-build.json').read_text())['built'] is False

def test_source_change_in_resolution_refuses_before_compilation(candidate):
    with pytest.raises(RuntimeError,match='changed during dependency resolution'):
        run(candidate,mutate='during_resolution')
    assert not list(candidate.glob('_morphproof_native.*'))
    assert json.loads((candidate/'morphproof-build.json').read_text())['built'] is False

def test_missing_resolver_lock_and_symlink_refuse(candidate,tmp_path):
    with pytest.raises(RuntimeError,match='missing|owned'):
        run(candidate,metadata_update=None)
    target=tmp_path/'outside';target.write_text('preserve');(candidate/'Cargo.lock').symlink_to(target)
    with pytest.raises(RuntimeError,match='symlink'):
        run(candidate)
    assert target.read_text()=='preserve'

@pytest.mark.parametrize('phase',['manifest','receipt'])
def test_lock_change_during_receipt_publication_invalidates_success(candidate,phase):
    run(candidate)
    real=Path.write_text
    triggered=False
    def write_and_mutate(path,data,*args,**kwargs):
        nonlocal triggered
        result=real(path,data,*args,**kwargs)
        selected=(path==candidate/'manifest.json' if phase=='manifest' else path==candidate/'morphproof-build.json')
        if selected and not triggered:
            try:success=json.loads(data).get('built') is True
            except (ValueError,AttributeError):success=False
            if success:
                triggered=True
                with (candidate/'Cargo.lock').open('ab') as f:f.write(b'changed during publication')
        return result
    with patch.object(Path,'write_text',write_and_mutate):
        with pytest.raises(RuntimeError,match='changed during publication'):
            run(candidate)
    assert triggered
    assert json.loads((candidate/'manifest.json').read_text())['built'] is False
    assert json.loads((candidate/'morphproof-build.json').read_text())['built'] is False
