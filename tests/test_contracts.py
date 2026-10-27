import json
from pathlib import Path
import tempfile
import unittest
from morphproof.contracts import discover, load_contract
from morphproof.agents import prepare, check

class ContractTests(unittest.TestCase):
    def test_discovery_requires_review(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ref.py'; p.write_text('def energy(values):\n return 0.0\n')
            self.assertTrue(discover(p)['discovery']['requires_review'])

    def test_changed_acceptance_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); ref=d/'ref.py'; ref.write_text('def f(v): return 1.0')
            con=d/'c.json'; con.write_text('{}')
            task=prepare(ref, con, d/'candidate', d/'handoff')
            check(task)
            (task/'acceptance/reference.py').write_text('def f(v): return 2.0')
            with self.assertRaisesRegex(ValueError, 'Acceptance input changed'):
                check(task)

    def test_contract_rejects_invalid_domains(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'c.json'
            p.write_text(json.dumps({'schema':1,'functions':[{'name':'f','input':'any','output':'float'}]}))
            with self.assertRaisesRegex(ValueError, 'Supported contract'):
                load_contract(p)

    def test_malformed_contract_has_clear_error(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'c.json'
            for data in [[], {'schema':1,'functions':[None]}, {'schema':1,'functions':[{'name':None}]}]:
                p.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    load_contract(p)
