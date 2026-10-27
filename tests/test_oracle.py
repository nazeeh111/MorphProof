import json
import math
from pathlib import Path
import tempfile
import unittest

from morphproof.inputs import Selector
from morphproof.oracle import equivalent, replay_cases, verify
from morphproof.worker import encode


CONTRACT = {"schema": 1, "functions": [{"name": "energy", "parameter": "values", "input": "list[float]", "output": "float", "max_length": 32, "rtol": 0.0, "atol": 0.0}]}
REFERENCE = "def energy(values):\n    total = 0.0\n    for value in values:\n        total += value * value\n    return total\n"


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ref, self.cand = self.root / "reference.py", self.root / "candidate.py"
        self.ref.write_text(REFERENCE)
        self.cand.write_text(REFERENCE)

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_and_nonfinite_comparison(self):
        observation = lambda value: {"kind": "return", "type": "float", "value": encode(value)}
        self.assertTrue(equivalent(observation(math.nan), observation(math.nan)))
        self.assertFalse(equivalent(observation(math.inf), observation(-math.inf)))
        self.assertFalse(equivalent(observation(-0.0), observation(0.0)))
        self.assertFalse(equivalent(observation(1.0), {"kind": "return", "type": "int", "value": 1}))
        self.assertFalse(equivalent({"kind": "timeout"}, {"kind": "timeout"}))
        self.assertFalse(equivalent({"kind": "exception", "type": "builtins.ValueError", "message": "empty"}, {"kind": "exception", "type": "builtins.ValueError", "message": "other"}))

    def test_compatible_has_hashes_and_reproducible_cases(self):
        report = verify(self.ref, self.cand, CONTRACT, self.root / "evidence", budget=24)
        self.assertEqual(report["status"], "compatible")
        self.assertEqual(report["totals"]["tested"], 24)
        self.assertTrue(report["provenance"]["sources_unchanged"])
        self.assertEqual(len(report["provenance"]["reference_sha256"]), 64)
        self.assertEqual(json.loads((self.root / "evidence/report.json").read_text()), report)
        self.assertEqual(report["functions"][0]["selection"]["feedback"], "reference-only")

    def test_discovers_minimizes_and_replays_real_bug(self):
        self.cand.write_text(REFERENCE.replace("value * value", "value"))
        evidence = self.root / "evidence"
        report = verify(self.ref, self.cand, CONTRACT, evidence, budget=24, seed=7)
        self.assertEqual(report["status"], "incompatible")
        examples = report["functions"][0]["counterexamples"]
        self.assertTrue(examples)
        self.assertTrue(any(len(item["minimized_input"]) <= 1 for item in examples))
        self.assertFalse(replay_cases(self.ref, self.cand, evidence / "counterexamples.json", evidence / "contract.snapshot.json"))
        self.cand.write_text(REFERENCE)
        self.assertTrue(replay_cases(self.ref, self.cand, evidence / "counterexamples.json", evidence / "contract.snapshot.json"))
        self.assertLessEqual(report["totals"]["shrink_executions"], 128)

    def test_import_error_is_not_compatibility(self):
        self.cand.write_text("raise RuntimeError('broken import')\n")
        report = verify(self.ref, self.cand, CONTRACT, self.root / "evidence", budget=4)
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["functions"][0]["errors"][0]["candidate"]["kind"], "load_error")

    def test_timeout_is_error_and_bounded(self):
        from morphproof.oracle import Worker
        self.cand.write_text("def energy(values):\n    while True: pass\n")
        worker = Worker(self.cand, timeout=.1)
        try:
            self.assertEqual(worker.call("energy", [1.0])["outcome"]["kind"], "timeout")
        finally:
            worker.close()

    def test_preserves_exception_semantics(self):
        self.ref.write_text("def energy(values):\n    if not values: raise ValueError('empty input')\n    return values[0]\n")
        self.cand.write_text("def energy(values):\n    if not values: raise ValueError('empty input')\n    return values[0]\n")
        self.assertEqual(verify(self.ref, self.cand, CONTRACT, self.root / "evidence", budget=12)["status"], "compatible")
        self.cand.write_text("def energy(values):\n    if not values: return 0.0\n    return values[0]\n")
        self.assertEqual(verify(self.ref, self.cand, CONTRACT, self.root / "bad", budget=12)["status"], "incompatible")

    def test_invalid_contracts_rejected(self):
        with self.assertRaises(ValueError):
            verify(self.ref, self.cand, {"schema": 1, "functions": []}, self.root / "evidence")
        with self.assertRaises(ValueError):
            verify(self.ref, self.cand, CONTRACT, self.root / "evidence", budget=0)
        with self.assertRaises(ValueError):
            verify(self.ref, self.ref, CONTRACT, self.root / "evidence")
        broken = json.loads(json.dumps(CONTRACT))
        broken["functions"][0]["atol"] = math.nan
        with self.assertRaises(ValueError):
            verify(self.ref, self.cand, broken, self.root / "evidence")
        for invalid in [[], {"schema": 1, "functions": [None]}, {"schema": 1, "functions": [{"name": None}]},
                        {"schema": 1, "functions": [{"name": "energy", "parameter": None}]}]:
            with self.subTest(contract=invalid), self.assertRaises(ValueError):
                verify(self.ref, self.cand, invalid, self.root / "invalid-contract")

    def test_selector_is_seeded_and_strategies_differ(self):
        one, two = Selector(REFERENCE, seed=12), Selector(REFERENCE, seed=12)
        for _ in range(10):
            a, b = one.next(), two.next()
            self.assertEqual(encode(a.values), encode(b.values))
            self.assertEqual(a.family, b.family)
        uniform = Selector(REFERENCE, strategy="uniform")
        self.assertEqual(uniform.next().family, "uniform")
        boundary = Selector(REFERENCE, strategy="boundary")
        self.assertEqual(boundary.next().values, [])

    def test_keyword_api_is_checked_separately(self):
        self.cand.write_text(REFERENCE.replace("values", "items"))
        report = verify(self.ref, self.cand, CONTRACT, self.root / "evidence", budget=4)
        self.assertEqual(report["totals"]["tested"], 4)
        self.assertEqual(report["totals"]["failures"], 0)
        self.assertEqual(report["totals"]["api_tested"], 3)
        self.assertEqual(report["totals"]["api_failures"], 3)
        self.assertEqual(report["status"], "incompatible")

    def test_declared_keyword_must_bind_reference_api(self):
        source = "def energy(items): return 0.0\n"
        self.ref.write_text(source)
        self.cand.write_text(source)
        report = verify(self.ref, self.cand, CONTRACT, self.root / "invalid-parameter", budget=2)
        self.assertEqual(report["status"], "error")
        error = report["functions"][0]["errors"][0]
        self.assertEqual(error["reason"], "invalid_reference_contract")
        self.assertIn("cannot bind declared parameter", error["message"])
        self.assertEqual(error["reference"]["kind"], "exception")

    def test_type_error_inside_valid_function_remains_subject_behavior(self):
        source = "def energy(values): raise TypeError('intentional subject behavior')\n"
        self.ref.write_text(source)
        self.cand.write_text(source)
        report = verify(self.ref, self.cand, CONTRACT, self.root / "intentional-type-error", budget=2)
        self.assertEqual(report["status"], "compatible")
        self.assertEqual(report["totals"]["api_tested"], 3)

    def test_preserves_existing_evidence_and_records_all_cases(self):
        output = self.root / "evidence"
        verify(self.ref, self.cand, CONTRACT, output, budget=4)
        records = json.loads((output / "tested-cases.json").read_text())
        self.assertEqual(len(records), 7)
        saved = (output / "report.json").read_bytes()
        with self.assertRaises(FileExistsError):
            verify(self.ref, self.cand, CONTRACT, output, budget=4)
        self.assertEqual((output / "report.json").read_bytes(), saved)

    def test_native_artifact_manifest_is_frozen_and_safe(self):
        artifact = self.root / "native.bin"
        artifact.write_bytes(b"compiled artifact")
        manifest = self.root / "morphproof-build.json"
        manifest.write_text(json.dumps({"artifacts": ["native.bin"]}))
        report = verify(self.ref, self.cand, CONTRACT, self.root / "evidence", budget=4)
        self.assertIn("native.bin", report["provenance"]["artifact_sha256"])
        self.cand.write_text("from pathlib import Path\nPath(__file__).with_name('native.bin').write_bytes(b'changed')\n" + REFERENCE)
        report = verify(self.ref, self.cand, CONTRACT, self.root / "changed", budget=4)
        self.assertEqual(report["status"], "error")
        self.assertFalse(report["provenance"]["sources_unchanged"])
        manifest.write_text(json.dumps({"artifacts": ["../outside"]}))
        with self.assertRaises(ValueError):
            verify(self.ref, self.cand, CONTRACT, self.root / "bad-manifest", budget=4)

    def test_same_length_repair_cannot_use_stale_bytecode(self):
        import importlib.util
        import os
        self.ref.write_text("def energy(values): return 1.0\n")
        self.cand.write_text("def energy(values): return 2.0\n")
        stamp = self.cand.stat().st_mtime
        spec = importlib.util.spec_from_file_location("stale_candidate", self.cand)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # Deliberately leave a valid stale .pyc.
        self.cand.write_text("def energy(values): return 1.0\n")
        os.utime(self.cand, (stamp, stamp))
        self.assertEqual(verify(self.ref, self.cand, CONTRACT, self.root / "evidence", budget=2)["status"], "compatible")

    def test_missing_noncallable_and_wrong_signature_are_api_errors(self):
        for index, source in enumerate(["def other(values): return 0.0\n", "energy = 0.0\n", "def energy(): return 0.0\n"]):
            with self.subTest(source=source):
                self.ref.write_text(source)
                self.cand.write_text(source)
                report = verify(self.ref, self.cand, CONTRACT, self.root / f"api-error-{index}", budget=2)
                self.assertEqual(report["status"], "error")
                self.assertEqual(report["functions"][0]["errors"][0]["reference"]["kind"], "api_error")
                self.assertEqual(report["functions"][0]["errors"][0]["candidate"]["kind"], "api_error")

    def test_attribute_error_inside_declared_function_is_subject_behavior(self):
        source = "def energy(values): raise AttributeError('inside subject')\n"
        self.ref.write_text(source)
        self.cand.write_text(source)
        report = verify(self.ref, self.cand, CONTRACT, self.root / "subject-error", budget=2)
        self.assertEqual(report["status"], "compatible")

    def test_reference_must_obey_declared_output_type(self):
        self.ref.write_text("def energy(values): return 0\n")
        self.cand.write_text("def energy(values): return 0\n")
        report = verify(self.ref, self.cand, CONTRACT, self.root / "invalid-baseline", budget=2)
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["functions"][0]["errors"][0]["reason"], "invalid_reference_contract")
        self.assertEqual(report["functions"][0]["errors"][0]["reference"]["value"], 0)
        self.ref.write_text("def energy(values): return 0.0\n")
        report = verify(self.ref, self.cand, CONTRACT, self.root / "wrong-candidate-type", budget=2)
        self.assertEqual(report["status"], "incompatible")

    def test_unsupported_observation_cannot_be_a_matching_subject_exception(self):
        source = "class Token: pass\ndef energy(values): return Token()\n"
        self.ref.write_text(source)
        self.cand.write_text(source)
        report = verify(self.ref, self.cand, CONTRACT, self.root / "unsupported-observation", budget=2)
        self.assertEqual(report["status"], "error")
        error = report["functions"][0]["errors"][0]
        self.assertEqual(error["reference"]["kind"], "observation_error")
        self.assertEqual(error["reference"]["result_type"], "Token")


if __name__ == "__main__":
    unittest.main()


def test_finite_contract_never_generates_infinite_threshold_neighbor():
    import math
    from morphproof.inputs import Selector
    for strategy in ('adaptive','boundary','random','uniform'):
        selector=Selector('def f(values): return 1.7976931348623157e308', max_length=8, strategy=strategy, allow_nonfinite=False)
        for _ in range(64):
            assert all(math.isfinite(v) for v in selector.next().values)
