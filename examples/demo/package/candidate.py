"""Load this candidate's compiled Rust extension by absolute path."""
import importlib.util as _util
from pathlib import Path as _Path
import sysconfig as _sysconfig
_path = _Path(__file__).parent / ("_morphproof_native" + (_sysconfig.get_config_var("EXT_SUFFIX") or ".so"))
_spec = _util.spec_from_file_location("_morphproof_native", _path)
_morphproof_native_module = _util.module_from_spec(_spec)
_spec.loader.exec_module(_morphproof_native_module)
def sum_squares(values):
    return _morphproof_native_module.sum_squares(values)

def mean(values):
    return _morphproof_native_module.mean(values)

def positive_energy(values):
    return _morphproof_native_module.positive_energy(values)

