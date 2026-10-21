"""Security's log signs "worth a look" (security.py `signs`, audit_security.py): gateway
errors (502, 503, 504) and requests for .php paths by UTC hour, and, where the log records
request_length=, POST sizes and the large ones; both roads read the optional field."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_lines, parse  # noqa: E402

from security_support import T, box, ln, put, stored  # noqa: E402


def lined(text: str, extra: str) -> str:
    return text.rstrip("\n") + f" {extra}\n"


def day() -> list[str]:
    out = []
    for i in range(30):                                    # workers crashing for a minute
        out.append(ln(T + timedelta(seconds=2 * i), "203.0.113.20", "/", status=502, size=150))
    for i in range(12):                                     # a PHP site's own scripts
        out.append(ln(T + timedelta(hours=2, seconds=i), "203.0.113.21", "/index.php", status=200))
    for i, size in enumerate((900, 2_400_000, 1_500)):
        out.append(lined(ln(T + timedelta(hours=3, seconds=i), "203.0.113.22", "/upload",
                            method="POST", status=200), f"request_length={size}"))
    out.append(lined(ln(T + timedelta(hours=4), "203.0.113.22", "/"), "request_length=-"))
    return sorted(out)


class Field(unittest.TestCase):
    def test_both_roads_read_request_length_anywhere_after_the_agent(self):
        base = ln(T, "203.0.113.22", "/upload", method="POST")
        for extra in ("request_length=2048", "request_length=2048 rid=" + "a" * 32,
                      "rsc_prefetch=- request_length=2048"):
            raw = lined(base, extra)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "access.log"
                path.write_text(raw)
                hit = next(iter(parse.read([path])))
            self.assertEqual(hit.request_length, 2048, extra)
            self.assertEqual(audit_lines.line_hit(raw).length, 2048, extra)
            self.assertEqual(hit.host, "example.com")
        self.assertIsNone(audit_lines.line_hit(base).length, "no field: not recorded")
        self.assertIsNone(audit_lines.line_hit(lined(base, "request_length=-")).length)


class Signs(unittest.TestCase):
    def setUp(self):
        self.box = box(day())
        code, _, err = self.box.run("--today", "2026-10-06", "collect")
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.box.close()

    def test_counted_and_audited(self):
        s = stored(self.box)["signs"]
        self.assertEqual(s["gateway"], {"requests": 30, "hours": {"2026-10-05T08": 30}})
        self.assertEqual(s["php"], {"requests": 12, "hours": {"2026-10-05T10": 12}})
        self.assertEqual(s["posts"], {"recorded": 3, "large": 1, "max": 2_400_000,
                                      "paths": {"/upload": 1}})
        code, _, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 0, err)

    def test_the_audit_catches_a_moved_hour(self):
        b = stored(self.box)
        b["signs"]["gateway"]["hours"] = {"2026-10-05T09": 30}
        put(self.box, b)
        code, _, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 1)
        self.assertIn("security.signs.gateway.hours", err)


class NotRecorded(unittest.TestCase):
    def test_no_field_is_not_recorded_never_zero(self):
        b = box([ln(T, "203.0.113.22", "/upload", method="POST")])
        try:
            self.assertEqual(b.run("--today", "2026-10-06", "collect")[0], 0)
            self.assertIsNone(stored(b)["signs"]["posts"])
            self.assertEqual(b.run("--today", "2026-10-06", "audit")[0], 0)
        finally:
            b.close()


if __name__ == "__main__":
    unittest.main()
