import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

import rextracto


class OpenArgsTests(unittest.TestCase):
    """Ctrl-O opens each selected entry on its own, with ~ expanded (#2)."""

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

    def test_open_each_entry_with_tilde_expanded(self):
        with mock.patch.object(rextracto.subprocess, "Popen") as popen:
            self.pick("ctrl-o", ["~/notes/todo.txt", "https://example.com/x"], "--open-tool", "xdg-open")
        self.assertEqual(
            [call.args[0] for call in popen.call_args_list],
            [["xdg-open", "/home/user/notes/todo.txt"], ["xdg-open", "https://example.com/x"]],
        )
        self.assertEqual(popen.call_args.kwargs["cwd"], "/tmp")


if __name__ == "__main__":
    unittest.main()
