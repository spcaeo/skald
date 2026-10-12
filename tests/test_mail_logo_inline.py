"""The Skald mark in the HTML mail is an inline part, so Gmail shows it instead of a broken image."""
import sys
import unittest
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class LogoInline(unittest.TestCase):
    def test_related_image_is_inline(self):
        src = (Path(__file__).resolve().parent.parent / "skald" / "mailer.py").read_text()
        self.assertIn('disposition="inline"', src)
        m = EmailMessage()
        m.set_content("t")
        m.add_alternative("<img src='cid:skald-mark'>", subtype="html")
        m.get_body(("html",)).add_related(b"\x89PNG", maintype="image", subtype="png",
                                          cid="<skald-mark>", filename="skald.png", disposition="inline")
        img = [p for p in m.walk() if p.get_content_type() == "image/png"][0]
        self.assertTrue(img.get("Content-Disposition").startswith("inline"))


if __name__ == "__main__":
    unittest.main()
