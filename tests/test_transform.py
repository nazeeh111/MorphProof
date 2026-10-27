import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from morphproof.transform import UnsupportedSource, build_candidate, generate, transform


CONTRACT = {"schema": 1, "functions": [{"name": "energy", "parameter": "values", "input": "list[float]", "output": "float"}]}
SOURCE = '''def energy(values: list[float]) -> float:
    total = 0.0
    for value in values:
        total += value * value
    return total
'''


class TransformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.reference = self.root / "reference.py"
        self.reference.write_text(SOURCE)

    def tearDown(self):
        self.temp.cleanup()

    def test_generates_real_pyo3_loop_and_frozen_sources(self):
        destination = self.root / "candidate"
        manifest = transform(self.reference, destination, CONTRACT, build=False)
        rust = (destination / "src" / "lib.rs").read_text()
        self.assertIn("values.iter().copied()", rust)
        self.assertIn("v_total = (v_total + (v_value * v_value))", rust)
        self.assertEqual((destination / "reference.py").read_text(), SOURCE)
        self.assertFalse(manifest["built"])
        self.assertEqual(len(manifest["reference_sha256"]), 64)
        self.assertEqual(json.loads((destination / "manifest.json").read_text())["schema"], 1)

    def test_build_does_not_follow_ambient_cargo_target_directory(self):
        destination = self.root / "candidate"
        transform(self.reference, destination, CONTRACT, build=False)
        external = self.root / "shared-target"

        def compile_fixture(command, **kwargs):
            target = Path(command[command.index("--target-dir") + 1]) if "--target-dir" in command else external
            suffix = ".dylib" if sys.platform == "darwin" else ".dll" if sys.platform == "win32" else ".so"
            library = target / "release" / (("" if sys.platform == "win32" else "lib") + "_morphproof_native" + suffix)
            library.parent.mkdir(parents=True)
            library.write_bytes(b"test compiled artifact")
            (destination / "Cargo.lock").write_text("# fixture lock\n")
            return subprocess.CompletedProcess(command, 0, "fixture compilation succeeded")

        with patch.dict(os.environ, {"CARGO_TARGET_DIR": str(external)}), \
                patch("morphproof.transform.shutil.which", return_value="fixture-cargo"), \
                patch("morphproof.transform.subprocess.run", side_effect=compile_fixture), \
                patch("morphproof.transform.platform.platform", return_value="fixture platform"), \
                patch("morphproof.transform.subprocess.check_output", return_value="fixture toolchain"):
            result = build_candidate(destination)
        self.assertTrue(result["built"])
        self.assertEqual(Path(result["native"]).read_bytes(), b"test compiled artifact")
        self.assertFalse(external.exists())

    def test_rejects_before_writing_partial_artifact(self):
        self.reference.write_text('def energy(values):\n    return sum(values)\n')
        destination = self.root / "candidate"
        with self.assertRaises(UnsupportedSource):
            transform(self.reference, destination, CONTRACT, build=False)
        self.assertFalse(destination.exists())

    def test_rejects_overwrite_and_explicit_bug_mode(self):
        destination = self.root / "candidate"
        transform(self.reference, destination, CONTRACT, build=False)
        with self.assertRaises(FileExistsError):
            transform(self.reference, destination, CONTRACT, build=False)
        with self.assertRaises(ValueError):
            transform(self.reference, self.root / "other", CONTRACT, buggy=True)

    def test_division_and_exceptions_preserve_guards(self):
        self.reference.write_text('def energy(values):\n    if len(values) == 0:\n        raise ValueError("empty input")\n    total = 0.0\n    for value in values:\n        total += value\n    return total / len(values)\n')
        rust = generate(self.reference, CONTRACT)
        self.assertIn('PyValueError::new_err("empty input")', rust)
        self.assertIn('mp_div(v_total, (values.len() as f64))?', rust)
        self.assertIn('PyZeroDivisionError::new_err("float division by zero")', rust)

    def test_definite_assignment_and_integer_semantics(self):
        for source in [
            'def energy(values):\n    if len(values) > 0:\n        x = 1.0\n    return x\n',
            'def energy(values):\n    x = 0\n    return x\n',
            'def energy(values):\n    return 2 / 3\n',
            'def energy(values):\n    for x in values:\n        pass\n    return 0.0\n',
            'GLOBAL = 1.0\ndef energy(values):\n    return GLOBAL\n',
        ]:
            with self.subTest(source=source):
                self.reference.write_text(source)
                with self.assertRaises(UnsupportedSource):
                    generate(self.reference, CONTRACT)

    def test_shadowed_builtins_are_rejected(self):
        for source in [
            'def energy(values):\n    total = len(values) / 1.0\n    len = 0.0\n    return total\n',
            'def energy(values):\n    return abs(values[0])\ndef abs(values):\n    return 0.0\n',
        ]:
            self.reference.write_text(source)
            with self.assertRaises(UnsupportedSource):
                generate(self.reference, CONTRACT)

    def test_integer_negative_zero_has_no_sign(self):
        self.reference.write_text('def energy(values):\n    return values[0] * -0\n')
        self.assertIn('(mp_index(&values, 0_i64)? * 0.0_f64)', generate(self.reference, CONTRACT))

    def test_annotation_and_default_side_effects_are_rejected(self):
        for source in [
            'def energy(values: print("side effect")):\n    return 0.0\n',
            'def energy(values):\n    return 0.0\ndef unused(value=print("side effect")):\n    return value\n',
        ]:
            self.reference.write_text(source)
            with self.assertRaises(UnsupportedSource):
                generate(self.reference, CONTRACT)

    def test_shadowed_exception_types_are_rejected(self):
        for source in [
            'def energy(values):\n    raise ValueError("empty")\ndef ValueError(values):\n    return 0.0\n',
            'def energy(values):\n    ValueError = 0.0\n    raise ValueError("empty")\n',
        ]:
            self.reference.write_text(source)
            with self.assertRaises(UnsupportedSource):
                generate(self.reference, CONTRACT)

    def test_mixed_package_preserves_public_module_and_keyword_wrapper(self):
        self.reference = self.root / "numerics.py"
        self.reference.write_text('def energy(data):\n    return data[0] * data[0]\n')
        contract = {"schema": 1, "functions": [{"name": "energy", "parameter": "data", "input": "list[float]", "output": "float"}]}
        destination = self.root / "candidate"
        manifest = transform(self.reference, destination, contract, build=False)
        project = (destination / "pyproject.toml").read_text()
        self.assertEqual(manifest["package_import"], "numerics")
        self.assertIn('name = "numerics-morphproof"', project)
        self.assertIn('module-name = "numerics._morphproof_native"', project)
        self.assertIn('python-source = "python"', project)
        package = (destination / "python/numerics/__init__.py").read_text()
        self.assertIn("def energy(data):", package)
        self.assertIn(".energy(data)", package)

    def test_invalid_filename_has_safe_package_name(self):
        self.reference = self.root / "not-a-module.py"
        self.reference.write_text(SOURCE)
        manifest = transform(self.reference, self.root / "candidate", CONTRACT, build=False)
        self.assertEqual(manifest["package_import"], "morphproof_candidate")
        self.assertEqual(manifest["distribution"], "not-a-module-morphproof")

    def test_wrapper_backend_does_not_collide_with_declared_parameter(self):
        self.reference.write_text('def energy(_morphproof_native_module):\n    return _morphproof_native_module[0] * 1.0\n')
        contract = {"schema": 1, "functions": [{"name": "energy", "parameter": "_morphproof_native_module", "input": "list[float]", "output": "float"}]}
        destination = self.root / "candidate"
        transform(self.reference, destination, contract, build=False)
        wrapper = (destination / "candidate.py").read_text()
        self.assertIn("return _morphproof_native_module_.energy(_morphproof_native_module)", wrapper)

    def test_index_slice_and_branch(self):
        self.reference.write_text('def energy(values):\n    result = values[0]\n    for value in values[1:]:\n        if value > result:\n            result = value\n    return result\n')
        rust = generate(self.reference, CONTRACT)
        self.assertIn('mp_index(&values, 0_i64)?', rust)
        self.assertIn('mp_slice(&values, Some(1_i64), None)', rust)


if __name__ == "__main__":
    unittest.main()
