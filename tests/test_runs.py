import tempfile
import unittest
from pathlib import Path

from artgen import runs


class RunsTest(unittest.TestCase):
    def test_wait_collects_folders_of_finished_runs(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t)
            with runs.marker(out, {}) as record:
                record(out / "a")
                self.assertEqual(len(runs.running(out)), 1)
            self.assertEqual(runs.running(out), [])
            self.assertEqual(runs.wait(out, timeout=1, poll=0), [str(out / "a")])
            self.assertEqual(runs.wait(out, timeout=1, poll=0), [])

    def test_marker_of_dead_process_is_dropped(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t)
            (out / ".runs").mkdir()
            (out / ".runs/999999.json").write_text('{"pid": 999999, "dests": []}')
            self.assertEqual(runs.running(out), [])


if __name__ == "__main__":
    unittest.main()
