"""Countries are shown as a flag and the ISO 3166-1 alpha-3 code (owner, 2026-10-18).

"🇺🇸 USA" on screen, in mails and in drills; the full name ("United States")
in the tooltip, for a screen reader, in a table's search and in a CSV (with
a "Code" column beside it). Stored values stay the alpha-2 code. Pinned here:

  * the alpha-3 table is complete for every country name the app knows,
    and the Python and JavaScript twins (countries.py, js/countries.js) agree;
  * the Python label is "🇺🇸 USA", the full name is name();
  * a country cell (js/tabs/readers.js countryWords, which every country
    link and label draws) shows the code and carries the full name in its
    title and its screen-reader text, and never shows the name;
  * a table's CSV writes the full name and the code (js/table.js).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skald import countries  # noqa: E402

JS = ROOT / "skald" / "webapp" / "js"
NOT_COUNTRIES = {"EU", "AP"}   # old GeoIP groupings: no alpha-3, shown as they are


def js_table(name: str) -> dict:
    src = (JS / "countries.js").read_text(encoding="utf-8")
    block = re.search(r"export const %s = \{(.*?)\};" % name, src, re.S).group(1)
    return dict(re.findall(r'([A-Z]{2}):"((?:[^"\\]|\\.)*)"', block))


class Tables(unittest.TestCase):

    def test_every_country_has_an_alpha3(self):
        missing = sorted(set(countries.NAMES) - set(countries.ALPHA3) - NOT_COUNTRIES)
        self.assertEqual(missing, [])
        self.assertEqual(sorted(set(countries.ALPHA3) - set(countries.NAMES)), [])
        for a2, a3 in countries.ALPHA3.items():
            self.assertRegex(a3, r"^[A-Z]{3}$", a2)
        self.assertEqual(len(set(countries.ALPHA3.values())), len(countries.ALPHA3), "codes are unique")
        # Every country a continent is worked out for has a name and a code.
        self.assertEqual(sorted(set(countries.CONTINENT) - set(countries.ALPHA3)), [])

    def test_the_two_twins_agree(self):
        self.assertEqual(js_table("ALPHA3"), countries.ALPHA3)
        self.assertEqual(js_table("NAMES"), countries.NAMES)

    def test_python_says_flag_and_code(self):
        self.assertEqual(countries.label("US"), "\U0001F1FA\U0001F1F8 USA")
        self.assertEqual(countries.label("gb"), "\U0001F1EC\U0001F1E7 GBR")
        self.assertEqual(countries.label("XK"), "\U0001F1FD\U0001F1F0 XKX")
        self.assertEqual(countries.label("Unknown"), "Not recorded")
        self.assertEqual(countries.label("(all others)"), "(all others)")
        self.assertEqual(countries.name("US"), "United States")
        self.assertEqual(countries.name("Unknown"), "Not recorded")
        self.assertEqual(countries.code3("DE"), "DEU")


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TheApp(unittest.TestCase):
    """countryWords and table.js's CSV, run by node with h() stubbed as plain objects."""

    def run_node(self, body: str):
        readers = (JS / "tabs" / "readers.js").read_text(encoding="utf-8")
        words = re.search(r"export function countryWords\(.*?\n\}\n", readers, re.S).group(0)
        flag = re.search(r"export function flag\(code\) \{.*?\n\}\n", readers, re.S).group(0)
        table = (JS / "table.js").read_text(encoding="utf-8")
        cell = re.search(r"function cell\(v\) \{.*?\n\}\n", table, re.S).group(0)
        country_csv = re.search(r"const COUNTRY_CSV = .*?\]\)\);\n", table, re.S).group(0)
        csv = re.search(r"export function csv\(columns, rows\) \{.*?\n\}\n", table, re.S).group(0)
        src = "\n".join([
            f'import {{ code3, countryName }} from {json.dumps((JS / "countries.js").as_uri())};',
            "const h = (tag, attrs, ...kids) => ({ tag, attrs: attrs || {}, kids: kids.flat().filter((k) => k != null) });",
            "const shownText = (s) => s;",
            flag.replace("export ", ""),
            "const flagEl = (code) => { const f = flag(code); return f ? h('span', { class: 'flag', 'aria-hidden': 'true' }, f) : null; };",
            words.replace("export ", ""), cell, country_csv, csv.replace("export ", ""),
            "const text = (n) => (typeof n === 'string' ? n : n.kids.map(text).join(''));",
            body])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.mjs"
            path.write_text(src, encoding="utf-8")
            out = subprocess.run(["node", str(path)], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_a_country_cell_shows_the_code_and_titles_the_name(self):
        got = self.run_node("""
const el = countryWords("US");
const short = el.kids.find((k) => k.attrs && k.attrs.class === "nm");
const vh = el.kids.find((k) => k.attrs && k.attrs.class === "vh");
const none = countryWords("Unknown");
console.log(JSON.stringify({ title: el.attrs.title, short: text(short), shortHidden: short.attrs["aria-hidden"],
  reader: text(vh), all: text(el), none: text(none), noneTitle: none.attrs.title || null }));
""")
        self.assertEqual(got["title"], "United States")
        self.assertEqual(got["short"], "USA")
        self.assertEqual(got["shortHidden"], "true", "a screen reader reads the name, not the code")
        self.assertEqual(got["reader"], "United States")
        self.assertIn("\U0001F1FA\U0001F1F8", got["all"])
        # The text a table searches holds both, so "united" and "usa" both find the row.
        self.assertIn("USA", got["all"])
        self.assertIn("United States", got["all"])
        self.assertEqual(got["none"], "Not recorded")
        self.assertIsNone(got["noneTitle"])

    def test_the_csv_writes_the_name_and_the_code(self):
        got = self.run_node("""
const cols = [{ key: "label", label: "Country", country: (r) => r.k }, { key: "v", label: "Visitors" }];
console.log(JSON.stringify(csv(cols, [{ k: "US", label: "USA", v: 3 }, { k: "Unknown", label: "Not recorded", v: 1 }])));
""")
        self.assertEqual(got, "Country,Code,Visitors\r\nUnited States,USA,3\r\nNot recorded,,1\r\n")

    def test_every_country_label_goes_through_country_words(self):
        drill = (JS / "drill.js").read_text(encoding="utf-8")
        self.assertRegex(drill, r'if \(dim === "country"\) return countryWords\(value\);')
        self.assertIn('dim === "country" ? countryWords(v, { flag: false })', drill)


if __name__ == "__main__":
    unittest.main()
