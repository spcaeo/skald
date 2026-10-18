"""Tooltips stay inside the window, and a chart is one Tab stop (review, 2026-10-18).

webapp/js/place.js holds the pure parts: where a tooltip goes (tipBox) and which
slot a key moves to (stepKey). They run here in node. The source checks pin that
every chart draws through rove(): one tabindex="0" per chart, arrows inside.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "skald" / "webapp" / "js"


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TipBoxAndKeys(unittest.TestCase):

    def run_js(self, expr):
        script = ("const m = await import(process.argv[1]);"
                  f"console.log(JSON.stringify({expr}));")
        done = subprocess.run(["node", "--input-type=module", "-e", script, (JS / "place.js").as_uri()],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_a_tooltip_never_leaves_the_window(self):
        got = self.run_js("[m.tipBox(5, 400, 280, 120, 1440, 900),"      # at the left edge
                          " m.tipBox(1438, 400, 280, 120, 1440, 900),"   # at the right edge
                          " m.tipBox(700, 20, 200, 120, 1440, 900),"     # no room above: below
                          " m.tipBox(700, 890, 200, 120, 1440, 900),"    # at the bottom
                          " m.tipBox(195, 400, 280, 80, 390, 844),"      # a phone
                          " m.tipBox(700, 400, 200, 100, 1440, 900)]")   # in the open: centred above
        for box, (w, h, vw, vh) in zip(got, [(280, 120, 1440, 900), (280, 120, 1440, 900), (200, 120, 1440, 900),
                                            (200, 120, 1440, 900), (280, 80, 390, 844), (200, 100, 1440, 900)]):
            self.assertGreaterEqual(box["left"], 8)
            self.assertLessEqual(box["left"] + w, vw - 8)
            self.assertGreaterEqual(box["top"], 8)
            self.assertLessEqual(box["top"] + h, vh - 8)
        self.assertEqual(got[2]["top"], 36)                      # flipped below the point
        self.assertEqual(got[5], {"left": 600, "top": 288})       # centred, 12px above

    def test_keys_move_inside_a_chart(self):
        got = self.run_js("[['ArrowLeft',5],['ArrowRight',5],['ArrowLeft',0],['ArrowRight',29],['Home',12],"
                          "['End',3],['PageUp',3],['PageDown',25],['Tab',5],['Enter',5]].map(([k,i]) => m.stepKey(k, i, 30))")
        self.assertEqual(got, [4, 6, 0, 29, 0, 29, 0, 29, None, None])


class OneTabStopPerChart(unittest.TestCase):

    def test_every_chart_roves(self):
        charts = (JS / "charts.js").read_text()
        # slots() (columns, bars), the line chart and the request band each call rove().
        self.assertEqual(charts.count("rove("), 3)
        self.assertIn("rove(items)", charts)
        for name in ("hours.js", "quality.js"):
            self.assertIn("rove(", (JS / "tabs" / name).read_text(), name)

    def test_rove_leaves_one_tab_stop(self):
        place = (JS / "place.js").read_text()
        self.assertTrue(re.search(r'setAttribute\("tabindex", i === cur \? "0" : "-1"\)', place))


if __name__ == "__main__":
    unittest.main()
