import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

import rextracto


class GrabCycleTests(unittest.TestCase):
    """The grab key follows extrakto's order (#4)."""

    def cycle(self, start, single_pane, steps):
        area, seen = start, [start]
        for _ in range(steps):
            area = rextracto.next_grab_area(area, single_pane, start)
            seen.append(area)
        return seen

    def test_several_panes(self):
        self.assertEqual(self.cycle("recent", False, 4), ["recent", "window recent", "full", "window full", "recent"])

    def test_one_pane_skips_window_areas(self):
        self.assertEqual(self.cycle("recent", True, 2), ["recent", "full", "recent"])


if __name__ == "__main__":
    unittest.main()
