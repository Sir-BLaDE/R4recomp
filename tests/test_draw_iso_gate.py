"""Acceptance must not turn truncated or unobserved runs into a passing gate."""
import contextlib
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import draw_iso_gate as gate


class GateComparison(unittest.TestCase):
    def test_wrapped_ring_alignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "fingerprint.json").write_text(json.dumps(
                {"total": 40000, "available": 32768, "entries": [{"wc": 7}]}))
            self.assertEqual(gate.load_fp(tmp), {7232: {"wc": 7}})

    def test_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "base", Path(tmp) / "iso"
            for path, mode in ((a, "base"), (b, "iso")):
                path.mkdir()
                (path / "run.json").write_text(json.dumps(dict(
                    mode=mode, race_ended_frame=100, miss_total=0)))
                (path / "fingerprint.json").write_text(json.dumps(
                    {"entries": [{"ws": mode}]}))
                with (path / "ticks.csv").open("w", newline="") as out:
                    writer = csv.DictWriter(out, fieldnames=["seq"] + gate.JUDGE)
                    writer.writeheader()
                    writer.writerow(dict(seq=0, **dict.fromkeys(gate.JUDGE, 1)))

            def verdict():
                with contextlib.redirect_stdout(io.StringIO()):
                    return gate.compare(a, b)

            self.assertEqual(verdict(), 0)  # isolated dead-stack writes allowed
            run = json.loads((b / "run.json").read_text())
            run["race_ended_frame"] = None
            (b / "run.json").write_text(json.dumps(run))
            self.assertEqual(verdict(), 3)  # incomplete race is not a pass
            run.update(race_ended_frame=100, mode="nest")
            (b / "run.json").write_text(json.dumps(run))
            self.assertEqual(verdict(), 1)  # nested stock must match writes
            run.update(mode="iso", miss_total=None)
            (b / "run.json").write_text(json.dumps(run))
            self.assertEqual(verdict(), 4)  # missing miss telemetry fails closed
            run["miss_total"] = 0
            (b / "run.json").write_text(json.dumps(run))
            text = (b / "ticks.csv").read_text()
            (b / "ticks.csv").write_text(text.replace("0,1,", "0,2,", 1))
            self.assertEqual(verdict(), 1)


if __name__ == "__main__":
    unittest.main()
