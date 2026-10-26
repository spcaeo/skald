"""AI answers in the page (webapp/js/tabs/ai-answers*.js), found in the 2.14.0 QA:

  * Settings > AI answers printed "null" under its title: replaceChildren() writes a
    null argument as the text "null" (h() drops a null child; the DOM call does not).
    No replaceChildren() (nor append, prepend, before, after, replaceWith) in the app passes a bare "? null" / ": null" argument unless
    the list is filtered first (found the same in the column filter and Real time's legend).
  * A profile with questions but no assistant with a key said "add questions"; the
    cost line now says what is missing (run by node)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "skald" / "webapp" / "js"


def calls(src: str, name: str):
    """Each `name(` call's top-level arguments, as text."""
    at = 0
    while True:
        i = src.find(name + "(", at)
        if i < 0:
            return
        j = i + len(name) + 1
        depth, args, cur, quote = 0, [], [], None
        while j < len(src):
            c = src[j]
            if quote:
                cur.append(c)
                if c == "\\":
                    cur.append(src[j + 1])
                    j += 1
                elif c == quote:
                    quote = None
            elif c in "\"'`":
                quote = c
                cur.append(c)
            elif c in "([{":
                depth += 1
                cur.append(c)
            elif c in ")]}":
                if depth == 0:
                    args.append("".join(cur))
                    break
                depth -= 1
                cur.append(c)
            elif c == "," and depth == 0:
                args.append("".join(cur))
                cur = []
            else:
                cur.append(c)
            j += 1
        yield src[i:j + 1], args
        at = j


def top_level_null(arg: str) -> bool:
    """A ternary at the argument's top level with a null branch."""
    depth, quote, out = 0, None, []
    for c in arg:
        if quote:
            if c == quote:
                quote = None
            continue
        if c in "\"'`":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0:
            out.append(c)
    return bool(re.search(r"[?:]\s*null\b", "".join(out)))


class NoNullText(unittest.TestCase):
    def test_no_replace_children_writes_null(self):
        bad = []
        for path in sorted(JS.rglob("*.js")):
            src = path.read_text(encoding="utf-8")
            for name in ("replaceChildren", ".append", ".prepend", ".before", ".after", ".replaceWith"):
                for whole, args in calls(src, name):
                    if any(top_level_null(a) for a in args):
                        bad.append(f"{path.relative_to(JS)}: {whole[:90]}")
        self.assertEqual(bad, [], "a DOM call writes a null as the text \"null\"")

    def test_the_finder_sees_a_bare_null(self):
        _, args = next(calls("x.replaceChildren(a ? null : b, h('p', null, c ? null : d))", "replaceChildren"))
        self.assertEqual([top_level_null(a) for a in args], [True, False])


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class CostWords(unittest.TestCase):
    def words(self, **e):
        src = (JS / "tabs" / "ai-answers-edit.js").read_text(encoding="utf-8")
        usd = re.search(r"export const usd = .*?;\n", src).group(0).replace("export ", "")
        fn = re.search(r"export function costWords\(e\) \{.*?\n\}\n", src, re.S).group(0)
        body = {"answers": 0, "questions": 0, "tries": 1, "assistants": 0, "perRun": 0, "cap": 2,
                "fits": True, "days": 1, **e}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.mjs"
            path.write_text(usd + fn.replace("export ", "") +
                            f"console.log(JSON.stringify(costWords({json.dumps(body)}).cap));\n")
            out = subprocess.run(["node", str(path)], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_it_says_what_is_missing(self):
        self.assertEqual(self.words(questions=5),
                         "Nothing to ask yet: add an assistant with an API key (Settings › AI answers › API keys).")
        self.assertEqual(self.words(assistants=2), "Nothing to ask yet: add questions.")
        self.assertIn("questions and an assistant", self.words())
        self.assertEqual(self.words(answers=10, questions=5, assistants=2, cap=5),
                         "A run stays under the $5.00 daily cap.")


if __name__ == "__main__":
    unittest.main()
