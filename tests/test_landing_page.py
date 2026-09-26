"""Unit tests for lib/landing_page.py
Verifies password strength evaluation, structure, and auth validation routines.
Strict zero-emoji compliance.
"""
import unittest
from lib.landing_page import calculate_password_strength


class TestLandingPage(unittest.TestCase):
    """Test cases for landing page utilities and password strength engine."""

    def test_empty_password(self):
        res = calculate_password_strength("")
        self.assertEqual(res["score"], 0)
        self.assertEqual(res["label"], "Empty")
        self.assertEqual(res["pct"], 0)

    def test_weak_password(self):
        res = calculate_password_strength("abc")
        self.assertEqual(res["score"], 1)
        self.assertEqual(res["label"], "Weak")
        self.assertEqual(res["pct"], 20)

    def test_fair_password(self):
        res = calculate_password_strength("secretpass")
        self.assertIn(res["label"], ["Fair", "Good"])
        self.assertGreaterEqual(res["score"], 2)

    def test_strong_password(self):
        res = calculate_password_strength("SuperSecret123!@#")
        self.assertEqual(res["score"], 4)
        self.assertEqual(res["label"], "Strong")
        self.assertEqual(res["pct"], 100)
        self.assertEqual(res["color"], "#00A651")

    def test_module_importable(self):
        import lib.landing_page as lp
        self.assertTrue(hasattr(lp, "render_landing_page"))
        self.assertTrue(hasattr(lp, "render_auth_view"))
        self.assertTrue(hasattr(lp, "calculate_password_strength"))


if __name__ == "__main__":
    unittest.main()
