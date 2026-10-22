import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

import rextracto as module


class ClipboardTests(unittest.TestCase):
    """Copies survive the pane closing right after (rextracto#6, rex-thumbs#10)."""

    def test_tools_run_in_their_own_session(self):
        env = {"WAYLAND_DISPLAY": "wayland-0", "PATH": os.environ.get("PATH", "")}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(module.shutil, "which", side_effect=lambda name: name == "wl-copy" or None),
            mock.patch.object(module.subprocess, "run") as run,
        ):
            module.copy_text("hello")
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["wl-copy"])
        self.assertEqual(run.call_args.kwargs["input"], "hello")
        self.assertTrue(run.call_args.kwargs["start_new_session"])

    def test_osc52_is_flushed_before_exit(self):
        tty = mock.mock_open()
        with (
            mock.patch.dict(os.environ, {"PATH": ""}, clear=True),
            mock.patch.object(module.shutil, "which", return_value=None),
            mock.patch("builtins.open", tty),
            mock.patch.object(module.time, "sleep") as sleep,
        ):
            module.copy_text("hi")
        tty().write.assert_called_once_with("\x1b]52;c;aGk=\a")
        tty().flush.assert_called_once()
        sleep.assert_called_once_with(module.OSC52_SETTLE)

    def test_clip_tool_runs_in_its_own_session(self):
        with mock.patch.object(module.subprocess, "run") as run:
            module.copy_text("hello", "my-copy --flag")
        self.assertEqual(run.call_args.args[0], "my-copy --flag")
        self.assertTrue(run.call_args.kwargs["shell"])
        self.assertTrue(run.call_args.kwargs["start_new_session"])


if __name__ == "__main__":
    unittest.main()
