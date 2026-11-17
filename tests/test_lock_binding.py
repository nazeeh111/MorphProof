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
    prior=run(candidate); native=Path(prior['native']); native.write_bytes(b'prior native'); native.chmod(0o751)
    real_write, real_replace = Path.write_text, Path.replace
    triggered=False
    def write_and_mutate(path,data,*args,**kwargs):
        nonlocal triggered
        result=real_write(path,data,*args,**kwargs)
        if phase=='manifest' and path==candidate/'manifest.json' and json.loads(data).get('built') is True:
            triggered=True
            with (candidate/'Cargo.lock').open('ab') as f:f.write(b'changed during publication')
        return result
    def replace_and_mutate(path,target):
        nonlocal triggered
        result=real_replace(path,target)
        if phase=='receipt' and Path(target)==candidate/'morphproof-build.json':
            triggered=True
            with (candidate/'Cargo.lock').open('ab') as f:f.write(b'changed during publication')
        return result
    with patch.object(Path,'write_text',write_and_mutate), patch.object(Path,'replace',replace_and_mutate):
        with pytest.raises(RuntimeError,match='changed during publication'):
            run(candidate)
    assert triggered
    assert native.read_bytes()==b'prior native' and native.stat().st_mode & 0o777==0o751
    assert json.loads((candidate/'manifest.json').read_text())['built'] is False
    assert json.loads((candidate/'morphproof-build.json').read_text())['built'] is False


@pytest.mark.parametrize('phase',['manifest','receipt'])
@pytest.mark.parametrize('prior',[True,False])
def test_publication_write_failure_restores_native_and_keeps_receipt_incomplete(candidate,phase,prior):
    first=run(candidate); native=Path(first['native'])
    if prior:
        native.write_bytes(b'previous native');native.chmod(0o751)
    else:
        native.unlink()
    real_write,real_replace=Path.write_text,Path.replace
    def fail_manifest(path,data,*args,**kwargs):
        if phase=='manifest' and path==candidate/'manifest.json' and json.loads(data).get('built') is True:
            raise OSError('injected manifest write failure')
        return real_write(path,data,*args,**kwargs)
    def fail_receipt(path,target):
        if phase=='receipt' and Path(target)==candidate/'morphproof-build.json':
            raise OSError('injected receipt publication failure')
        return real_replace(path,target)
    with patch.object(Path,'write_text',fail_manifest),patch.object(Path,'replace',fail_receipt):
        with pytest.raises(OSError,match='injected'):
            run(candidate)
    assert json.loads((candidate/'morphproof-build.json').read_text())['built'] is False
    if prior:
        assert native.read_bytes()==b'previous native' and native.stat().st_mode & 0o777==0o751
    else:
        assert not native.exists()
    assert not list(candidate.glob('.morphproof-native-backup-*'))
    assert run(candidate)['built']


def test_rollback_failure_reports_and_retains_previous_native(candidate):
    native=Path(run(candidate)['native']);native.write_bytes(b'previous native');native.chmod(0o751)
    real_write,real_replace=Path.write_text,Path.replace
    def fail_manifest(path,data,*args,**kwargs):
        if path==candidate/'manifest.json' and json.loads(data).get('built') is True:
            raise OSError('injected publication failure')
        return real_write(path,data,*args,**kwargs)
    def fail_restore(path,target):
        if path.name.startswith('.morphproof-native-backup-'):
            raise OSError('injected rollback failure')
        return real_replace(path,target)
    with patch.object(Path,'write_text',fail_manifest),patch.object(Path,'replace',fail_restore):
        with pytest.raises(RuntimeError,match='native rollback failed') as error:
            run(candidate)
    backup=list(candidate.glob('.morphproof-native-backup-*'))
    assert len(backup)==1 and str(backup[0]) in str(error.value)
    assert backup[0].read_bytes()==b'previous native' and backup[0].stat().st_mode & 0o777==0o751
    assert isinstance(error.value.__cause__,OSError)
    assert json.loads((candidate/'morphproof-build.json').read_text())['built'] is False


@pytest.mark.parametrize("method", ["replace", "in_place"])
def test_intervening_native_replacement_is_preserved_with_backup(candidate,method):
    native=Path(run(candidate)['native']); native.write_bytes(b'previous native')
    real_replace=Path.replace
    def replace_then_intervene(path,target):
        result=real_replace(path,target)
        if Path(target)==candidate/'morphproof-build.json':
            if method=='replace':
                other=candidate/'other-native';other.write_bytes(b'intervening writer')
                real_replace(other,native)
            else:
                native.write_bytes(b'intervening writer')
            with (candidate/'Cargo.lock').open('ab') as f:f.write(b'drift')
        return result
    with patch.object(Path,'replace',replace_then_intervene):
        with pytest.raises(RuntimeError,match='native rollback failed') as error:
            run(candidate)
    backup=list(candidate.glob('.morphproof-native-backup-*'))
    assert native.read_bytes()==b'intervening writer'
    assert len(backup)==1 and backup[0].read_bytes()==b'previous native'
    assert str(backup[0]) in str(error.value)
    assert json.loads((candidate/'morphproof-build.json').read_text())['built'] is False


def test_invalidation_failure_does_not_skip_native_restoration(candidate):
    native=Path(run(candidate)['native']); native.write_bytes(b'previous native')
    real_write=Path.write_text
    def fail_manifest_and_invalidation(path,data,*args,**kwargs):
        if path==candidate/'manifest.json':
            raise OSError('injected metadata failure')
        return real_write(path,data,*args,**kwargs)
    # Initial invalidation must succeed; fail only after replacement.
    calls=0
    def fail_after_initial(path,data,*args,**kwargs):
        nonlocal calls
        if path==candidate/'manifest.json':
            calls+=1
            if calls>=2: return fail_manifest_and_invalidation(path,data,*args,**kwargs)
        return real_write(path,data,*args,**kwargs)
    with patch.object(Path,'write_text',fail_after_initial):
        with pytest.raises(RuntimeError,match='receipt invalidation failed') as error:
            run(candidate)
    assert isinstance(error.value.__cause__,OSError)
    assert native.read_bytes()==b'previous native'
    assert json.loads((candidate/'morphproof-build.json').read_text())['built'] is False


def test_keyboard_interrupt_restores_prior_native(candidate):
    native=Path(run(candidate)['native']);native.write_bytes(b'previous native')
    real_write=Path.write_text
    def interrupt_manifest(path,data,*args,**kwargs):
        if path==candidate/'manifest.json' and json.loads(data).get('built') is True:
            raise KeyboardInterrupt()
        return real_write(path,data,*args,**kwargs)
    with patch.object(Path,'write_text',interrupt_manifest):
        with pytest.raises(KeyboardInterrupt): run(candidate)
    assert native.read_bytes()==b'previous native'
    assert json.loads((candidate/'morphproof-build.json').read_text())['built'] is False


def test_successful_build_survives_backup_cleanup_failure(candidate):
    run(candidate)
    real_unlink=Path.unlink
    def fail_backup(path,*args,**kwargs):
        if path.name.startswith('.morphproof-native-backup-'):
            raise OSError('injected cleanup failure')
        return real_unlink(path,*args,**kwargs)
    with patch.object(Path,'unlink',fail_backup),pytest.warns(RuntimeWarning,match='successful build left'):
        assert run(candidate)['built']
    assert json.loads((candidate/'morphproof-build.json').read_text())['built'] is True
    assert len(list(candidate.glob('.morphproof-native-backup-*')))==1


@pytest.mark.parametrize('prior',[True,False])
@pytest.mark.parametrize('phase',['before','after'])
def test_interrupted_native_rename_observes_actual_effect(candidate,prior,phase):
    built=run(candidate); native=Path(built['native'])
    if prior:
        native.write_bytes(b'old native differs');native.chmod(0o751)
    else:
        native.unlink()
    real_replace=Path.replace
    def interrupted(path,target):
        if Path(target)==native and path.name.startswith('.morphproof-native-') and not path.name.startswith('.morphproof-native-backup-'):
            if phase=='after':
                real_replace(path,target)
                assert native.read_bytes()==b'compiled fixture'
            raise KeyboardInterrupt()
        return real_replace(path,target)
    with patch.object(Path,'replace',interrupted):
        with pytest.raises(KeyboardInterrupt):run(candidate)
    if prior:
        assert native.read_bytes()==b'old native differs' and native.stat().st_mode & 0o777==0o751
    else:
        assert not native.exists()
    assert json.loads((candidate/'morphproof-build.json').read_text())['built'] is False
    assert not list(candidate.glob('.morphproof-native-backup-*'))
    assert run(candidate)['built']


@pytest.mark.parametrize('prior',[True,False])
def test_interrupted_rename_preserves_intervening_writer(candidate,prior):
    native=Path(run(candidate)['native'])
    if prior:native.write_bytes(b'old native differs')
    else:native.unlink()
    real_replace=Path.replace
    def interrupted(path,target):
        if Path(target)==native and path.name.startswith('.morphproof-native-') and not path.name.startswith('.morphproof-native-backup-'):
            real_replace(path,target)
            other=candidate/'intervening';other.write_bytes(b'intervening writer')
            real_replace(other,native)
            raise KeyboardInterrupt()
        return real_replace(path,target)
    with patch.object(Path,'replace',interrupted):
        with pytest.raises(RuntimeError,match='native rollback failed') as error:run(candidate)
    assert isinstance(error.value.__cause__,KeyboardInterrupt)
    assert native.read_bytes()==b'intervening writer'
    backups=list(candidate.glob('.morphproof-native-backup-*'))
    if prior:
        assert len(backups)==1 and backups[0].read_bytes()==b'old native differs'
        assert str(backups[0]) in str(error.value)
    else:assert not backups
    assert json.loads((candidate/'morphproof-build.json').read_text())['built'] is False
