"""docs/CLI.md names every command and every argument of the real parser.

tools/cli-reference.py writes it from the parser; this fails when a command or
a flag is added without running it (or the file is edited by hand).
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skald import cli  # noqa: E402

DOC = ROOT / "docs" / "CLI.md"


def _walk(p: argparse.ArgumentParser, prefix=()):
    for a in p._actions:
        if isinstance(a, argparse._SubParsersAction):
            for name, sub in a.choices.items():
                path = prefix + (name,)
                flags = [o for x in sub._actions if not isinstance(x, (argparse._SubParsersAction,
                                                                       argparse._HelpAction))
                         for o in (x.option_strings or [x.dest])]
                yield path, flags
                yield from _walk(sub, path)


class CliReference(unittest.TestCase):
    def setUp(self):
        self.text = DOC.read_text()

    def test_every_command_and_argument_is_in_the_reference(self):
        missing = []
        for path, flags in _walk(cli.parser()):
            if len(path) == 1:
                head = f"### skald {path[0]}" if f"### skald {path[0]}" in self.text else None
                if head is None:
                    missing.append(" ".join(path))
                    continue
            elif f"| `{' '.join(path)}` |" not in self.text:
                missing.append(" ".join(path))
                continue
            section = self.text.split(f"### skald {path[0]}\n", 1)[1].split("\n### ", 1)[0]
            missing += [f"{' '.join(path)} {f}" for f in flags
                        if f not in ("action",) and f"`{f}`" not in section]
        self.assertEqual(missing, [], "run python3 tools/cli-reference.py")

    def test_the_file_is_what_the_tool_writes(self):
        spec = importlib.util.spec_from_file_location("cli_reference",
                                                      ROOT / "tools" / "cli-reference.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.render(), self.text, "run python3 tools/cli-reference.py")

    def test_under_the_file_size_limit(self):
        self.assertLess(len(self.text.splitlines()), 1000)


if __name__ == "__main__":
    unittest.main()
