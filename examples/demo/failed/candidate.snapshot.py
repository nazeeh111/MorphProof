"""Load this candidate's compiled Rust extension by absolute path."""
import importlib.util as _util
from pathlib import Path as _Path
import sysconfig as _sysconfig
_path = _Path(__file__).parent / ("_morphproof_native" + (_sysconfig.get_config_var("EXT_SUFFIX") or ".so"))
_spec = _util.spec_from_file_location("_morphproof_native", _path)
_native = _util.module_from_spec(_spec)
_spec.loader.exec_module(_native)
def sum_squares(values):
    return _native.sum_squares(values)

def mean(values):
    return _native.mean(values)

def positive_energy(values):
    return _native.positive_energy(values)

