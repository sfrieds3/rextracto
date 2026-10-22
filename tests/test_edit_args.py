import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

import rextracto


class ShellWordTests(unittest.TestCase):
    def test_quoting(self):
        self.assertEqual(rextracto.shell_word("/tmp/a b.txt"), "'/tmp/a b.txt'")
        self.assertEqual(rextracto.shell_word("plain.txt"), "plain.txt")
        self.assertEqual(rextracto.shell_word("$(touch x)"), "'$(touch x)'")

    def test_tilde_stays_expandable(self):
        self.assertEqual(rextracto.shell_word("~/notes/todo.txt"), "~/notes/todo.txt")
        self.assertEqual(rextracto.shell_word("~/my notes/a.txt"), "~/'my notes/a.txt'")
        self.assertEqual(rextracto.shell_word("~"), "~")
        self.assertEqual(rextracto.shell_word("~other/x"), "'~other/x'")


class EditArgsTests(unittest.TestCase):
    """Ctrl-E quotes each selected entry on its own and keeps ~/ expandable (#1)."""

    def setUp(self):
        self.calls = []
        patches = [
            mock.patch.object(rextracto, "window_blocks", return_value=["block:b"]),
            mock.patch.object(rextracto, "capture", return_value="~/notes/todo.txt /tmp/b.txt https://example.com/x"),
            mock.patch.object(rextracto, "block_call", side_effect=lambda *args: self.calls.append(args)),
            mock.patch.object(rextracto, "block_cwd", return_value="/tmp"),
            mock.patch.dict(os.environ, {"HOME": "/home/user"}),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def pick(self, key, selection, *argv, mode_keys=()):
        answers = [("ctrl-f", [])] * len(mode_keys) + [(key, selection)]
        with mock.patch.object(rextracto, "run_fzf", side_effect=lambda *args: ("", *answers.pop(0))):
            rextracto.pick(rextracto.parse_args([*argv, "session:a", "block:b"]))

    def test_edit_several_entries(self):
        self.pick("ctrl-e", ["~/notes/todo.txt", "/tmp/b c.txt"], "--editor", "nvim")
        self.assertEqual(self.calls[-1][2], "write")
        self.assertEqual(self.calls[-1][3], {"data": "nvim -- ~/notes/todo.txt '/tmp/b c.txt'\r"})

    def test_edit_strips_all_labels(self):
        self.pick("ctrl-e", ["path: ~/notes/todo.txt", "url: https://example.com/x"], "--editor", "vi", mode_keys=[1])
        self.assertEqual(self.calls[-1][3], {"data": "vi -- ~/notes/todo.txt https://example.com/x\r"})


if __name__ == "__main__":
    unittest.main()
