"""2026-10-22: the 07:15 run failed on one site and never ran the sites after it, and the
failure itself came from one redraw deleting another's temp file in the shared _app folder."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from skald import multisite, webapp


class RunEach(unittest.TestCase):
    def ctx(self, site, run):
        return SimpleNamespace(site=site, args=SimpleNamespace(command="run-daily", run=run))

    def test_a_crashing_site_does_not_stop_the_sites_after_it(self):
        ran = []

        def ok(c):
            ran.append(c.site)
            return 0

        def boom(c):
            ran.append(c.site)
            raise FileNotFoundError("a temp file went away")

        codes = multisite.run_each([self.ctx("a.example", ok), self.ctx("b.example", boom),
                                    self.ctx("c.example", ok), self.ctx("d.example", ok)])
        self.assertEqual(ran, ["a.example", "b.example", "c.example", "d.example"])
        self.assertEqual(codes, [0, 2, 0, 0])
        self.assertEqual(max(codes), 2)

    def test_an_interrupt_still_stops_the_run(self):
        def stop(c):
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            multisite.run_each([self.ctx("a.example", stop)])


class SharedAppFiles(unittest.TestCase):
    def test_install_keeps_another_runs_temp_file_and_drops_old_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            webapp.install(out, ["example.com"])
            js = out / webapp.SHARED / "js"
            busy = js / ".table.js.abc123.tmp"          # another run is writing it now
            busy.write_text("half written")
            old = js / ".table.js.zzz999.tmp"           # left by a crash an hour ago
            old.write_text("left over")
            hour_ago = time.time() - 2 * 3600
            os.utime(old, (hour_ago, hour_ago))
            stray = js / "removed-module.js"            # a file the app no longer ships
            stray.write_text("// gone")
            webapp.install(out, ["example.com"])
            self.assertTrue(busy.exists(), "a running write's temp file must survive")
            self.assertFalse(old.exists(), "a stale temp file is cleaned up")
            self.assertFalse(stray.exists(), "files the app no longer ships are removed")


if __name__ == "__main__":
    unittest.main()
