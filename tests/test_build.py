"""Cargo protocol/ownership controls; native compilation is checked separately."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from unittest.mock import patch

builder = importlib.import_module("morphproof.transform")
from morphproof.oracle import _artifact_hashes

CONTRACT = {"schema": 1, "functions": [
    {"name": "energy", "parameter": "values", "input": "list[float]", "output": "float"}]}
SOURCE = "def energy(values):\n    return values[0] * values[0]\n"
LIBRARY = ("_morphproof_native.dll" if sys.platform == "win32" else
           "lib_morphproof_native" + (".dylib" if sys.platform == "darwin" else ".so"))


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.reference = self.root / "reference.py"
        self.reference.write_text(SOURCE)
        self.destination = self.root / "candidate with spaces"
        builder.transform(self.reference, self.destination, CONTRACT, build=False)

    def message(self, library, **changes):
        return {
            "reason": "compiler-artifact",
            "manifest_path": str(self.destination / "Cargo.toml"),
            "target": {"name": "_morphproof_native", "crate_types": ["cdylib"],
                       "src_path": str(self.destination / "src/lib.rs")},
            "filenames": [str(library)], "fresh": False,
            **changes,
        }

    def output(self, *messages, success=True):
        return "\n".join([*(json.dumps(m) for m in messages),
                          json.dumps({"reason": "build-finished", "success": success})])

    def library(self, layout="release", data=b"fresh compiled fixture"):
        path = self.destination / "target" / layout / LIBRARY
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def build(self, compile):
        def dispatch(command, **kwargs):
            if command[1] == "metadata":
                lock = self.destination / "Cargo.lock"
                if not lock.exists():
                    lock.write_text("# fixture lock\n")
                return subprocess.CompletedProcess(command, 0, "{}", "")
            return compile(command, **kwargs)
        with patch.object(builder.shutil, "which", return_value="fixture-cargo"), \
             patch.object(builder.subprocess, "run", side_effect=dispatch), \
             patch.object(builder.subprocess, "check_output", return_value="fixture toolchain"), \
             patch.object(builder.platform, "platform", return_value="fixture platform"):
            return builder.build_candidate(self.destination)

    def compile(self, command, **kwargs):
        self.assertIn("--message-format=json-render-diagnostics", command)
        target = Path(command[command.index("--target-dir") + 1])
        self.assertEqual(target, self.destination / "target")
        library = self.library("host-triple/release")
        (self.destination / "Cargo.lock").write_text("# fixture lock\n")
        return subprocess.CompletedProcess(command, 0, self.output(self.message(library)))

    def test_build_ignores_ambient_target_directory_and_binds_delivered_bytes(self):
        external = self.root / "external target"
        self.library(data=b"STALE local library")
        with patch.dict(os.environ, {"CARGO_TARGET_DIR": str(external)}):
            result = self.build(self.compile)
        self.assertTrue(result["built"])
        self.assertEqual(Path(result["native"]).read_bytes(), b"fresh compiled fixture")
        self.assertFalse(external.exists())
        self.assertTrue(_artifact_hashes(self.destination / "candidate.py"))
        receipt = json.loads((self.destination / "morphproof-build.json").read_text())
        self.assertIs(receipt["built"], True)
        self.assertIn(Path(result["native"]).name, receipt["sha256"])

    def test_default_explicit_host_and_valid_cargo_cache_messages(self):
        for layout in ("release", "aarch64-apple-darwin/release"):
            with self.subTest(layout=layout):
                library = self.library(layout)
                message = self.message(library, fresh=True)
                self.assertEqual(builder._native_library(
                    self.destination, self.output(message)), library)

    def test_no_guessing_without_a_successful_matching_artifact_message(self):
        library = self.library()
        message = self.message(library)
        wrong_target = dict(message["target"], src_path=str(self.root / "unrelated.rs"))
        invalid = [
            "Finished release profile",
            self.output(message, success=False),
            json.dumps(message),
            self.output({"reason": "compiler-artifact"}),
            self.output(dict(message, manifest_path=str(self.root / "dependency/Cargo.toml"))),
            self.output(dict(message, target=wrong_target)),
            self.output(dict(message, target=dict(message["target"], crate_types=["rlib"]))),
            self.output(dict(message, filenames=[str(library.with_name("other.dylib"))])),
            self.output(dict(message, filenames="not an array")),
            self.output(dict(message, filenames=[None, 42])),
        ]
        for output in invalid:
            with self.subTest(output=output), self.assertRaises(RuntimeError):
                builder._native_library(self.destination, output)

    def test_ambiguous_and_outside_paths_refuse_even_with_a_valid_local_library(self):
        library = self.library()
        other = self.library("other/release")
        outside = self.root / LIBRARY
        outside.write_bytes(b"outside")
        for paths in ([str(library), str(other)], [str(outside)],
                      [str(library), str(outside)]):
            with self.subTest(paths=paths), self.assertRaises(RuntimeError):
                builder._native_library(self.destination, self.output(
                    self.message(library, filenames=paths)))

    def test_symlinked_library_and_symlinked_target_are_not_owned_artifacts(self):
        outside = self.root / LIBRARY
        outside.write_bytes(b"outside")
        library = self.destination / "target/release" / LIBRARY
        library.parent.mkdir(parents=True)
        try:
            library.symlink_to(outside)
        except OSError as error:
            self.skipTest(f"Host cannot create symlink fixture: {error}")
        with self.assertRaises(RuntimeError):
            builder._native_library(self.destination, self.output(self.message(library)))
        library.unlink()
        library.parent.rmdir()
        library.parent.parent.rmdir()
        (self.destination / "target").symlink_to(self.root, target_is_directory=True)
        with patch.object(builder.subprocess, "run") as compile, self.assertRaises(RuntimeError):
            self.build(compile)
        compile.assert_not_called()
        self.assertEqual(outside.read_bytes(), b"outside")

    def test_failure_preserves_previous_native_bytes_but_invalidates_build_claim(self):
        result = self.build(self.compile)
        native = Path(result["native"])
        before = native.read_bytes()

        def fail(command, **kwargs):
            return subprocess.CompletedProcess(command, 101, self.output(success=False))

        with self.assertRaisesRegex(RuntimeError, "Rust build failed"):
            self.build(fail)
        self.assertEqual(native.read_bytes(), before)
        self.assertIs(json.loads((self.destination / "manifest.json").read_text())["built"], False)
        self.assertIs(json.loads((self.destination / "morphproof-build.json").read_text())["built"], False)
        with self.assertRaisesRegex(ValueError, "not.*successful|incomplete"):
            _artifact_hashes(self.destination / "candidate.py")

    def test_timeout_and_wrong_artifact_cannot_deliver_seeded_stale_library(self):
        self.library(data=b"STALE")
        native = self.destination / ("_morphproof_native" + sysconfig.get_config_var("EXT_SUFFIX"))
        native.write_bytes(b"previous delivered bytes")

        def timeout(command, **kwargs):
            raise subprocess.TimeoutExpired(command, 0.01, output=b"partial diagnostics")

        def no_artifact(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, self.output())

        for compile in (timeout, no_artifact):
            with self.subTest(compile=compile.__name__), self.assertRaises(RuntimeError):
                self.build(compile)
            self.assertEqual(native.read_bytes(), b"previous delivered bytes")
            self.assertFalse(json.loads((self.destination / "manifest.json").read_text())["built"])

    def test_source_guard_still_refuses_before_native_delivery(self):
        def mutate(command, **kwargs):
            result = self.compile(command, **kwargs)
            (self.destination / "src/lib.rs").write_text("// changed while compiling\n")
            return result

        with self.assertRaisesRegex(RuntimeError, "source or build configuration changed"):
            self.build(mutate)
        self.assertFalse(list(self.destination.glob("_morphproof_native.*")))

    def test_success_receipt_refuses_later_source_or_artifact_replacement(self):
        result = self.build(self.compile)
        for filename in ("src/lib.rs", Path(result["native"]).name):
            path = self.destination / filename
            before = path.read_bytes()
            path.write_bytes(b"replacement")
            with self.subTest(filename=filename), self.assertRaisesRegex(ValueError, "identity|hash"):
                _artifact_hashes(self.destination / "candidate.py")
            path.write_bytes(before)
