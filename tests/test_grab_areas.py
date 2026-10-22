import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

import rextracto


class GrabAreaOptionTests(unittest.TestCase):
    """Numeric grab areas work as in extrakto (#3)."""

    def test_accepted(self):
        for area in ["recent", "full", "window recent", "window full", "500", "window 500"]:
            self.assertEqual(rextracto.parse_args(["--grab-area", area, "s", "b"]).grab_area, area)

    def test_rejected(self):
        for area in ["", "window", "lots", "window -5", "screen"]:
            with self.subTest(area=area), mock.patch("sys.stderr"), self.assertRaises(SystemExit):
                rextracto.parse_args(["--grab-area", area, "s", "b"])

    def test_history_lines(self):
        self.assertEqual(rextracto.history_lines("recent"), 10)
        self.assertEqual(rextracto.history_lines("window recent"), 10)
        self.assertEqual(rextracto.history_lines("full"), None)
        self.assertEqual(rextracto.history_lines("window 500"), 500)

    def test_numeric_capture(self):
        content = "\n".join(f"line {index}" for index in range(1000))

        def block_call(session, block, method, params=None):
            return {"content": content} if method == "format" else {"rows": 20}

        with mock.patch.object(rextracto, "block_call", side_effect=block_call):
            lines = rextracto.capture("session:a", "block:b", "500").split("\n")
        self.assertEqual(len(lines), 520)
        self.assertEqual(lines[0], "line 480")


class GrabCycleTests(unittest.TestCase):
    """The grab key returns to a custom starting area, as in extrakto (#3)."""

    def cycle(self, start, single_pane, steps=5):
        area, seen = start, [start]
        for _ in range(steps):
            area = rextracto.next_grab_area(area, single_pane, start)
            seen.append(area)
        return seen

    def test_several_panes(self):
        self.assertEqual(self.cycle("recent", False, 4), ["recent", "window recent", "full", "window full", "recent"])

    def test_one_pane(self):
        self.assertEqual(self.cycle("recent", True, 2), ["recent", "full", "recent"])

    def test_custom_area_comes_back(self):
        self.assertEqual(self.cycle("500", False), ["500", "recent", "window recent", "full", "window full", "500"])
        self.assertEqual(self.cycle("500", True, 3), ["500", "recent", "full", "500"])


if __name__ == "__main__":
    unittest.main()
