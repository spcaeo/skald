"""The visual system (2.41, docs/UI-RULES.md, css/ui.css, js/ui/*.js).

- tests/js/ui.mjs in node: the pills, the "?" popover, the folds, the one primary and
  "Who will do it?" (the address round trip, the remembered choice, each path calling
  the flow Skald already has).
- css/ui.css sets no colour of its own: every colour is a token from app.css, mixed.
- Its text pairs meet WCAG 1.4.3 (4.5:1) in the light and the dark theme: the accent
  button's words on the accent, and each pill's words on its own tint.
- index.html links it; the components' files stay under the file-size limit.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "skald" / "webapp"
UI_CSS = APP / "css" / "ui.css"
JS = ROOT / "tests" / "js" / "ui.mjs"


def _block(css: str, selector: str) -> dict[str, str]:
    """The custom properties set in the first block whose selector is exactly `selector`."""
    at = css.index(selector + " {")
    body = css[at + len(selector) + 2:css.index("}", at)]
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", body))


def themes() -> dict[str, dict[str, str]]:
    app = (APP / "app.css").read_text()
    ui = UI_CSS.read_text()
    light = {**_block(app, ":root"), **_block(ui, ":root")}
    dark = {**light, **_block(app, ':root[data-theme="dark"]'), **_block(ui, ':root[data-theme="dark"]')}
    return {"light": light, "dark": dark}


def _hex(text: str) -> tuple[float, float, float]:
    text = text.strip().lstrip("#")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def colour(expr: str, env: dict[str, str]) -> tuple[float, float, float]:
    """A colour expression as ui.css writes them: a hex, var(--x), black/white, or
    color-mix(in srgb, A p%, B) (srgb mixing is linear in the 0-255 channels)."""
    expr = expr.strip()
    if expr.startswith("var("):
        return colour(env[expr[4:-1].strip()], env)
    if expr.startswith("#"):
        return _hex(expr)
    if expr in ("black", "white"):
        return (0.0, 0.0, 0.0) if expr == "black" else (255.0, 255.0, 255.0)
    m = re.fullmatch(r"color-mix\(in srgb,\s*(.+?)\s+(\d+)%,\s*(.+)\)", expr)
    if not m:
        raise ValueError(expr)
    a, p, b = colour(m.group(1), env), int(m.group(2)) / 100, colour(m.group(3), env)
    return tuple(x * p + y * (1 - p) for x, y in zip(a, b))  # type: ignore[return-value]


def luminance(rgb) -> float:
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def pill_pairs(css: str) -> dict[str, tuple[str, str]]:
    out = {}
    for kind, body in re.findall(r"\.ui-pill\.(\w+) \{([^}]*)\}", css):
        fg = re.search(r"(?<![-\w])color:\s*([^;]+);", body).group(1)
        bg = re.search(r"background:\s*([^;]+);", body).group(1)
        out[kind] = (fg, bg)
    return out


class UiSystem(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_components_in_node(self):
        done = subprocess.run(["node", str(JS)], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("ui: all passed", done.stdout)

    def test_no_colour_of_its_own(self):
        css = re.sub(r"/\*.*?\*/", "", UI_CSS.read_text(), flags=re.S)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", css), [], "ui.css uses app.css's tokens only")
        self.assertEqual(re.findall(r"rgba?\(", css), [])

    def test_text_pairs_meet_the_bar_in_both_themes(self):
        css = UI_CSS.read_text()
        pairs = {f"pill {k}": v for k, v in pill_pairs(css).items()}
        self.assertEqual(sorted(k.split()[1] for k in pairs), ["bad", "good", "info", "off", "warn"])
        pairs["primary button"] = ("var(--accent-ink)", "var(--accent)")
        for theme, env in themes().items():
            surface = env["--surface"]
            env = {**env, "--surface": surface}
            for name, (fg, bg) in pairs.items():
                ratio = contrast(colour(fg, env), colour(bg, env))
                self.assertGreaterEqual(ratio, 4.5, f"{name} in {theme}: {ratio:.2f}:1")

    def test_linked_and_small(self):
        self.assertIn('href="../_app/css/ui.css"', (APP / "index.html").read_text())
        for f in [UI_CSS, *sorted((APP / "js" / "ui").glob("*.js"))]:
            self.assertLessEqual(len(f.read_text().splitlines()), 1000, f.name)
        self.assertTrue((ROOT / "docs" / "UI-RULES.md").exists())


if __name__ == "__main__":
    unittest.main()
