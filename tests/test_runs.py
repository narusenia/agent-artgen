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



class WindowsTest(unittest.TestCase):
    def test_alive_never_signals_on_windows(self):
        from unittest import mock

        with mock.patch.object(runs.os, "name", "nt"), mock.patch.object(runs, "_alive_windows", return_value=True) as w, \
                mock.patch.object(runs.os, "kill") as kill:
            self.assertTrue(runs.alive(123))
        w.assert_called_once_with(123)
        kill.assert_not_called()

    def test_show_uses_startfile_on_windows(self):
        from unittest import mock

        from artgen import cli

        a = cli.parser().parse_args(["show", "a.png", "b.png"])
        with mock.patch.object(cli.platform, "system", return_value="Windows"), \
                mock.patch.object(cli.os, "startfile", create=True) as start, mock.patch.object(cli.subprocess, "run") as run:
            a.func(a)
        self.assertEqual(start.call_count, 2)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
