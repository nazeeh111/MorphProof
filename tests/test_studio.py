import json
import math
import re

from morphproof.studio import render_studio


def test_portable_attempt_exports_keep_original_observation_values(tmp_path):
    root = {"status": "compatible", "observation": 1.0}
    first = {"status": "incompatible", "observation": -0.0, "note": "</script>"}
    (tmp_path / "report.json").write_text(json.dumps(root), encoding="utf-8")
    (tmp_path / "run.json").write_text(
        json.dumps({"attempts": [{"report": first}, {"report": root}]}),
        encoding="utf-8",
    )

    page = render_studio(tmp_path).read_text(encoding="utf-8")
    payload = json.loads(re.search(r'id="evidence-data" type="application/json">(.*?)</script>', page)[1])
    assert json.loads(payload["report_export"]) == root
    exported_first, exported_last = [
        json.loads(attempt["_report_export"]) for attempt in payload["run"]["attempts"]
    ]
    assert exported_first == first
    assert math.copysign(1.0, exported_first["observation"]) < 0
    assert exported_last == root
