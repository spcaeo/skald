"""The vendored spcaeo/ui components in Skald's colours: contrast, light and dark.

Upstream measures its own palette (tools/contrast.mjs in github.com/spcaeo/ui); in
Skald the colours come from app.css through vendor/spcaeo-ui/spcaeo-ui-skald.css, so
this re-runs the same idea on what Skald ships: it reads both stylesheets, resolves
each component variable in each theme, and checks the pairs upstream declares (its
component.json) plus the ones Skald's use adds. Text needs 4.5:1 (WCAG 1.4.3); a
focus ring or a boundary needs 3:1 (WCAG 1.4.11), and a boundary passes on its fills
or on the edge stroke drawn between them, as upstream's rule says.

    python3 tests/test_spcaeo_contrast.py --table    prints the table for VERSION.md
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "skald" / "webapp"
MAPPING = APP / "vendor" / "spcaeo-ui" / "spcaeo-ui-skald.css"

TAB_VARS = ("rail", "rail-fill", "rail-ink", "panel", "panel-ink", "edge", "ring", "ring-on-panel")
DG_VARS = ("bg", "fg", "muted", "muted-fg", "border", "control-border", "accent", "primary", "primary-fg",
           "popover", "ring", "danger")

# (label, fg, bg, need): text and focus rings. Upstream's pairs first, then Skald's own.
TEXT = {
    "tab": [
        ("label on inactive tab", "rail-ink", "rail-fill", 4.5),
        ("label on active tab", "panel-ink", "panel", 4.5),
        ("focus ring on inactive tab", "ring", "rail-fill", 3.0),
        ("focus ring on active tab", "ring-on-panel", "panel", 3.0),
    ],
    "dg": [
        ("body text on background", "fg", "bg", 4.5),
        ("muted text on background", "muted-fg", "bg", 4.5),
        ("column header on header fill", "muted-fg", "muted", 4.5),
        ("primary button label", "primary-fg", "primary", 4.5),
        ("error text on background", "danger", "bg", 4.5),
        ("focus ring on background", "ring", "bg", 3.0),
        ("focus ring on header fill", "ring", "muted", 3.0),
        # Skald's: chips and counts on the muted fill, hover and selection, the filter menu.
        ("text on muted fill (chips, counts)", "fg", "muted", 4.5),
        ("text on hover / selection fill", "fg", "accent", 4.5),
        ("text in the filter menu", "fg", "popover", 4.5),
        ("menu title in the filter menu", "muted-fg", "popover", 4.5),
    ],
}
# (label, a, b, edge or None, need): a boundary passes on a vs b, or on the edge vs both.
BOUNDARIES = {
    "tab": [
        ("inactive tab vs rail", "rail-fill", "rail", "edge", 3.0),
        ("active tab vs rail", "panel", "rail", "edge", 3.0),
        ("active tab vs inactive tab", "panel", "rail-fill", "edge", 3.0),
    ],
    "dg": [
        ("control border vs background", "control-border", "bg", None, 3.0),
        ("control border vs header fill", "control-border", "muted", None, 3.0),
        ("primary button vs background", "primary", "bg", "control-border", 3.0),
        ("active segment underline vs background", "primary", "bg", None, 3.0),
    ],
}
HOSTS = {"tab": "[data-folder-tabs]", "dg": ".dg"}
DARK_EXPLICIT = ':root[data-theme="dark"]'
DARK_SYSTEM = ':root:not([data-theme="light"])'


def rules(css: str, media: str = "") -> list[tuple[str, str, dict]]:
    """(media, selector, {property: value}) for every rule, @media blocks included."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out, i = [], 0
    while True:
        open_ = css.find("{", i)
        if open_ < 0:
            return out
        head = css[i:open_].strip()
        depth, j = 1, open_ + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(css[j], 0)
            j += 1
        body = css[open_ + 1:j - 1]
        if head.startswith("@media"):
            out += rules(body, head)
        else:
            decls = dict((k.strip(), v.strip()) for k, v in
                         (d.split(":", 1) for d in body.split(";") if ":" in d))
            out.append((media, " ".join(head.split()), decls))
        i = j


def tokens(theme: str) -> dict:
    """Skald's tokens in a theme: light, dark (data-theme) or system (the OS asks for dark)."""
    found = rules((APP / "app.css").read_text(encoding="utf-8"))
    pick = {"light": ("", ":root"), "dark": ("", DARK_EXPLICIT), "system": ("@media (prefers-color-scheme: dark)", DARK_SYSTEM)}[theme]
    out = {}
    if theme != "light":
        out.update(tokens("light"))
    for media, sel, decls in found:
        if (media, sel) == pick:
            out.update({k: v for k, v in decls.items() if k.startswith("--")})
    return out


def component(prefix: str, theme: str) -> dict:
    """The component's variables in a theme, as the cascade sets them on its host element."""
    host = HOSTS[prefix]
    wanted = {("", host)}
    if theme == "dark":
        wanted.add(("", f"{DARK_EXPLICIT} {host}"))
    if theme == "system":
        wanted.add(("@media (prefers-color-scheme: dark)", f"{DARK_SYSTEM} {host}"))
    out = {}
    # Later and more specific rules win; the dark ones come after the plain one in the file.
    for media, sel, decls in rules(MAPPING.read_text(encoding="utf-8")):
        if (media, sel) in wanted:
            out.update({k: v for k, v in decls.items() if k.startswith(f"--{prefix}-")})
    return out


def hex_rgb(value: str) -> tuple:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise ValueError(f"not a colour: #{value}")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def resolve(value: str, scope: dict, depth: int = 0) -> tuple:
    """A colour value to (r, g, b): hex, var(--x), color-mix(in srgb, A p%, B)."""
    if depth > 10:
        raise ValueError(f"var() loop at {value}")
    value = value.strip()
    m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*\)", value)
    if m:
        if m.group(1) not in scope:
            raise KeyError(f"{m.group(1)} is not defined")
        return resolve(scope[m.group(1)], scope, depth + 1)
    m = re.fullmatch(r"color-mix\(\s*in srgb\s*,\s*(.+?)(?:\s+(\d+(?:\.\d+)?)%)?\s*,\s*(.+?)(?:\s+(\d+(?:\.\d+)?)%)?\s*\)", value)
    if m:
        a, pa, b, pb = m.groups()
        pa = float(pa) / 100 if pa else (1 - float(pb) / 100 if pb else 0.5)
        ca, cb = resolve(a, scope, depth + 1), resolve(b, scope, depth + 1)
        return tuple(round(x * pa + y * (1 - pa)) for x, y in zip(ca, cb))
    if value.startswith("#"):
        return hex_rgb(value)
    raise ValueError(f"cannot read the colour {value!r}")


def luminance(rgb: tuple) -> float:
    lin = [(c / 255) / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: tuple, b: tuple) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def colours(prefix: str, theme: str) -> dict:
    scope = {**tokens(theme), **component(prefix, theme)}
    return {name: resolve(scope[f"--{prefix}-{name}"], scope)
            for name in (TAB_VARS if prefix == "tab" else DG_VARS)}


def measure(theme: str):
    """Every pair in a theme: (component, label, measured, need, ok)."""
    for prefix in ("tab", "dg"):
        c = colours(prefix, theme)
        for label, fg, bg, need in TEXT[prefix]:
            r = ratio(c[fg], c[bg])
            yield prefix, label, f"{r:.2f}", need, r >= need
        for label, a, b, edge, need in BOUNDARIES[prefix]:
            fill = ratio(c[a], c[b])
            if fill >= need or not edge:
                yield prefix, label, f"{fill:.2f}", need, fill >= need
            else:
                stroke = min(ratio(c[edge], c[a]), ratio(c[edge], c[b]))
                yield prefix, label, f"{fill:.2f} fill, {stroke:.2f} edge", need, stroke >= need


class Contrast(unittest.TestCase):
    def test_every_variable_is_set_from_skald(self):
        # Nothing falls back to upstream's own palette.
        for prefix, names in (("tab", TAB_VARS), ("dg", DG_VARS)):
            got = component(prefix, "light")
            self.assertEqual(sorted(f"--{prefix}-{n}" for n in names), sorted(k for k in got if k != "--dg-radius"), prefix)

    def test_both_dark_selectors_say_the_same(self):
        # Skald's theme switch (data-theme) and the OS setting must give one dark look.
        self.assertEqual(tokens("dark"), tokens("system"))
        for prefix in ("tab", "dg"):
            self.assertEqual(colours(prefix, "dark"), colours(prefix, "system"), prefix)

    def test_pairs_meet_the_bar_in_both_themes(self):
        for theme in ("light", "dark", "system"):
            for prefix, label, got, need, ok in measure(theme):
                with self.subTest(theme=theme, pair=f"{prefix}: {label}"):
                    self.assertTrue(ok, f"{theme} {prefix} {label}: {got} < {need}")

    def test_the_active_tab_stays_the_lightest_fill(self):
        # Upstream's dark-mode warning: the active tab IS the panel, so it must not read as pressed in.
        for theme in ("light", "dark"):
            c = colours("tab", theme)
            self.assertGreater(luminance(c["panel"]), luminance(c["rail-fill"]), theme)
            self.assertGreater(luminance(c["rail-fill"]), luminance(c["rail"]), theme)

    def test_the_reader_reads_what_it_should(self):
        self.assertEqual(resolve("color-mix(in srgb, #000000 50%, #ffffff)", {}), (128, 128, 128))
        self.assertAlmostEqual(ratio((0, 0, 0), (255, 255, 255)), 21.0, places=2)
        self.assertEqual(resolve("var(--a)", {"--a": "var(--b)", "--b": "#102030"}), (16, 32, 48))


if __name__ == "__main__":
    if "--table" in sys.argv:
        print("| Component | Pair | Light | Dark | Needs |\n| --- | --- | --- | --- | --- |")
        light, dark = list(measure("light")), list(measure("dark"))
        for (prefix, label, lg, need, lok), (_, _, dg, _, dok) in zip(light, dark):
            name = "Folder Tabs" if prefix == "tab" else "Data Grid"
            print(f"| {name} | {label} | {lg}{'' if lok else ' FAIL'} | {dg}{'' if dok else ' FAIL'} | {need:g} |")
    else:
        unittest.main()
