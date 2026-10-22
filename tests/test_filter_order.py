import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

import rextracto

DEFAULT_CONF = [os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "rextracto.conf")]


class FilterOrderTests(unittest.TestCase):
    """filter_order is checked before fzf opens (#5)."""

    def test_valid(self):
        self.assertEqual(rextracto.filter_modes("word all line", DEFAULT_CONF), ["word", "all", "line"])
        self.assertEqual(rextracto.filter_modes(" path  url ", DEFAULT_CONF), ["path", "url"])

    def test_empty(self):
        with self.assertRaisesRegex(rextracto.ExtraktoException, "filter_order is empty"):
            rextracto.filter_modes("  ", DEFAULT_CONF)

    def test_unknown(self):
        with self.assertRaisesRegex(rextracto.ExtraktoException, "unknown filter in filter_order: wrod"):
            rextracto.filter_modes("wrod line", DEFAULT_CONF)

    def test_pick_fails_before_fzf(self):
        with (
            mock.patch.object(rextracto, "window_blocks", return_value=["block:b"]),
            mock.patch.object(rextracto, "run_fzf") as run_fzf,
            self.assertRaises(rextracto.ExtraktoException),
        ):
            rextracto.pick(rextracto.parse_args(["--filter-order", "", "session:a", "block:b"]))
        run_fzf.assert_not_called()

    def test_help_lists_configured_order(self):
        answers = [("ctrl-h", []), ("esc", [])]
        with (
            mock.patch.object(rextracto, "window_blocks", return_value=["block:b"]),
            mock.patch.object(rextracto, "capture", return_value="some words here"),
            mock.patch.object(rextracto, "run_fzf", side_effect=lambda *args: ("", *answers.pop(0))),
            mock.patch.object(rextracto.subprocess, "run") as run,
        ):
            rextracto.pick(rextracto.parse_args(["--filter-order", "path url", "session:a", "block:b"]))
        self.assertIn("Ctrl-F order (filter_order): path url", run.call_args.kwargs["input"])


if __name__ == "__main__":
    unittest.main()
